from playwright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.cakeresume.com/users/sign_in"
SEARCH_URL = "https://www.cakeresume.com/jobs?q={term}&remote=true&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.cakeresume.com/jobs?q={term}&page={page}"


class CakeResumeScraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["cakeresume_email"]
        self._password = secrets["cakeresume_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        page.goto(LOGIN_URL)
        page.wait_for_selector('[name="email"]')
        page.fill('[name="email"]', self._email)
        page.fill('[name="password"]', self._password)
        page.click('[type="submit"]')
        page.wait_for_load_state("networkidle")
        human_delay(1.5, 3.0)

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        links: list = []
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=search_term.replace(" ", "+"), page=p)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.5)
            anchors = page.query_selector_all('a[href*="/companies/"][href*="/jobs/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                full = href.split("?")[0]
                if not full.startswith("http"):
                    full = f"https://www.cakeresume.com{full}"
                if full not in links:
                    links.append(full)
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            # Step 1: Click "Apply Now" button or "Reapply" link
            apply_btn = page.query_selector('button:has-text("Apply Now"), a:has-text("Apply Now"), a:has-text("Reapply")')
            if not apply_btn or not apply_btn.is_visible():
                return ApplyResult(status="skipped")

            # External ATS links open in a new tab — can't automate, skip
            href = apply_btn.get_attribute("href") or ""
            target = apply_btn.get_attribute("target") or ""
            if target == "_blank" or (href and "cakeresume.com" not in href):
                return ApplyResult(status="skipped")

            apply_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.5, 2.5)

            # Step 2: Personal info page — just click Next (info is cached)
            next_btn = page.wait_for_selector('button:has-text("Next")', timeout=10000)
            next_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            # Step 3: Resume template page — click Select Template, pick topmost radio, confirm
            template_btn = page.wait_for_selector('button:has-text("Select Template")', timeout=10000)
            template_btn.click()
            human_delay(0.5, 1.0)

            radios = page.wait_for_selector('input[type="radio"]', timeout=5000)
            all_radios = page.query_selector_all('input[type="radio"]')
            if all_radios:
                all_radios[0].click()
                human_delay(0.3, 0.6)

            confirm_btn = page.wait_for_selector('button:has-text("Confirm")', timeout=5000)
            confirm_btn.click()
            human_delay(0.5, 1.0)

            # Step 4: Click Next, then Submit Application
            next_btn2 = page.wait_for_selector('button:has-text("Next")', timeout=10000)
            next_btn2.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            submit_btn = page.wait_for_selector('button:has-text("Submit Application")', timeout=10000)
            submit_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            # If we landed on a new page it means there are extra questions — flag for manual review
            if "application" not in page.url and "thank" not in page.url.lower():
                return ApplyResult(status="skipped", screening_links=[url])

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

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
            human_delay(3.0, 4.0)

            # Step 1: Derive apply URL from job slug — avoids button-finding entirely
            # e.g. https://www.cake.me/companies/acme/jobs/senior-dev -> /apply-for-job/senior-dev
            slug = url.rstrip("/").split("/jobs/")[-1]
            apply_url = f"https://www.cake.me/apply-for-job/{slug}"

            ap = page.context.new_page()
            ap.goto(apply_url)
            ap.wait_for_load_state("networkidle")
            human_delay(1.5, 2.5)

            # If redirected to an external ATS, skip
            if "cake.me" not in ap.url and "cakeresume.com" not in ap.url:
                ap.close()
                return ApplyResult(status="skipped", error=f"external ATS: {ap.url}")

            # Step 2: Personal info page — just click Next (info is cached)
            next_btn = ap.wait_for_selector('button:has-text("Next")', timeout=10000)
            next_btn.click()
            ap.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            # Step 3: Resume template page — click Select Template, pick topmost radio, confirm
            template_btn = ap.wait_for_selector('button:has-text("Select Template")', timeout=10000)
            template_btn.click()
            human_delay(0.5, 1.0)

            # Custom radio divs (no <input type="radio">) — wait for modal to render
            first_radio = ap.wait_for_selector('[class*="radioOuter"]', timeout=5000)
            first_radio.click()
            human_delay(0.3, 0.6)

            confirm_btn = ap.wait_for_selector('button:has-text("Confirm")', timeout=5000)
            confirm_btn.click()
            human_delay(0.5, 1.0)

            # Step 4: Click Next — may land on Submit or Screening Questions
            next_btn2 = ap.wait_for_selector('button:has-text("Next")', timeout=10000)
            next_btn2.click()
            ap.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            submit_btn = ap.query_selector('button:has-text("Submit Application")')
            if not submit_btn:
                # Screening questions or unknown step — flag for manual review
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn.click()
            ap.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            if not ap.query_selector('*:has-text("Successfully Applied")'):
                return ApplyResult(status="skipped", screening_links=[url])

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

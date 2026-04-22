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
            anchors = page.query_selector_all('a[href*="/jobs/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/jobs/" in href and not href.endswith("/jobs/"):
                    full = href if href.startswith("http") else f"https://www.cakeresume.com{href}"
                    if full not in links:
                        links.append(full)
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            apply_btn = page.query_selector('button:has-text("Apply"), a:has-text("Apply now")')
            if not apply_btn:
                return ApplyResult(status="skipped")

            apply_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            question_els = page.query_selector_all('textarea[name*="question"], input[name*="question"]')
            if question_els and self._ai_screening:
                questions = [el.get_attribute("placeholder") or "" for el in question_els]
                answers = answer_screening_questions(questions, resume_text, self._claude_api_key)
                for el, answer in zip(question_els, answers):
                    el.fill(answer)
                    human_delay(0.3, 0.8)
            elif question_els and not self._ai_screening:
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn = page.query_selector('button[type="submit"]:has-text("Submit"), button:has-text("Send application")')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle")
                human_delay(1.0, 2.0)
                return ApplyResult(status="applied")

            return ApplyResult(status="skipped")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

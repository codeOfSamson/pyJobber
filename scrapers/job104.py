import urllib.parse
from playwright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://signin.104.com.tw/"
SEARCH_URL = "https://www.104.com.tw/jobs/search/?keyword={term}&remoteWork=1&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.104.com.tw/jobs/search/?keyword={term}&page={page}"


class Job104Scraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["job104_email"]
        self._password = secrets["job104_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector('[name="identity"]', timeout=15000)
        page.fill('[name="identity"]', self._email)
        submit = page.query_selector('button[type="submit"], button:has-text("下一步"), button:has-text("Next")')
        if submit:
            submit.click()
        page.wait_for_timeout(1500)
        password_field = page.query_selector('[name="password"], input[type="password"]')
        if password_field:
            password_field.fill(self._password)
            page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        human_delay(2.0, 4.0)

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list[str]:
        links: list[str] = []
        encoded = urllib.parse.quote(search_term)
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=encoded, page=p)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.5, 3.0)
            anchors = page.query_selector_all('a[href*="/job/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/job/" in href:
                    full = href if href.startswith("http") else f"https://www.104.com.tw{href}"
                    full = full.split("?")[0]
                    if full not in links:
                        links.append(full)
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            apply_btn = page.query_selector('a.btn-apply, button.btn-apply, a:has-text("我要應徵")')
            if not apply_btn:
                return ApplyResult(status="skipped")

            apply_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            question_els = page.query_selector_all('textarea.apply-question, input.apply-question')
            if question_els and self._ai_screening:
                questions = [el.get_attribute("placeholder") or "" for el in question_els]
                answers = answer_screening_questions(questions, resume_text, self._claude_api_key)
                for el, answer in zip(question_els, answers):
                    el.fill(answer)
                    human_delay(0.3, 0.8)
            elif question_els and not self._ai_screening:
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn = page.query_selector('button[type="submit"].btn-submit, button:has-text("送出")')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle")
                human_delay(1.0, 2.0)
                return ApplyResult(status="applied")

            return ApplyResult(status="skipped")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

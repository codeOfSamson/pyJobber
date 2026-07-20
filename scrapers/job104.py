import json
import os
import re
import urllib.parse
import boto3
from patchright.sync_api import Page
from browser.browser import human_delay, bypass_cloudflare_challenge
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.104.com.tw/"
SEARCH_URL = "https://www.104.com.tw/jobs/search/?keyword={term}&remoteWork=1&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.104.com.tw/jobs/search/?keyword={term}&page={page}"

AUTH_LOCAL = "auth_104.json"
AUTH_ECS = "/tmp/auth_104.json"
AUTH_S3_KEY = "auth_104.json"


def _auth_path() -> str:
    return AUTH_ECS if os.environ.get("ENV") == "production" else AUTH_LOCAL


def _download_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.download_file(os.environ["CONFIG_BUCKET"], AUTH_S3_KEY, AUTH_ECS)
        print("[104] auth file downloaded from S3")
    except Exception:
        pass


def _upload_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.upload_file(AUTH_ECS, os.environ["CONFIG_BUCKET"], AUTH_S3_KEY)
        print("[104] auth file uploaded to S3")
    except Exception:
        pass


class Job104Scraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["job104_email"]
        self._password = secrets["job104_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        if os.environ.get("ENV") == "production":
            _download_auth()

        auth = _auth_path()
        if os.path.exists(auth):
            with open(auth) as f:
                state = json.load(f)
            page.context.add_cookies(state.get("cookies", []))
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            bypass_cloudflare_challenge(page)
            if page.get_by_text("登入/註冊").count() == 0:
                print("[104] session loaded from auth file — skipping login")
                return
            print("[104] saved session expired — doing full login")

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        bypass_cloudflare_challenge(page)
        try:
            page.locator(".popup-icon-click > .jb_icon_delete").click(timeout=5000)
        except Exception:
            pass
        page.get_by_text("登入/註冊").click()
        page.wait_for_selector('[placeholder="Enter ID or Email"]', timeout=10000)
        human_delay(0.5, 1.0)
        page.get_by_placeholder("Enter ID or Email").fill(self._email)
        page.get_by_placeholder("Enter ID or Email").press("Enter")
        page.wait_for_selector('[placeholder="Enter Password"]', timeout=10000)
        human_delay(0.5, 1.0)
        page.get_by_placeholder("Enter Password").fill(self._password)
        human_delay(0.3, 0.6)
        page.get_by_role("button", name="Login").click()
        page.wait_for_load_state("domcontentloaded")
        human_delay(3.0, 5.0)
        logged_in = page.get_by_text("登入/註冊").count() == 0
        print(f"[104] login complete — url={page.url!r} logged_in={logged_in}")

        if logged_in:
            page.context.storage_state(path=auth)
            print("[104] auth file saved")
            if os.environ.get("ENV") == "production":
                _upload_auth()

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list[str]:
        links: list[str] = []
        encoded = urllib.parse.quote(search_term)
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=encoded, page=p)
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            bypass_cloudflare_challenge(page)
            human_delay(1.5, 3.0)
            anchors = page.query_selector_all('a[href*="/job/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/job/" in href:
                    full = href if href.startswith("http") else f"https://www.104.com.tw{href}"
                    full = full.split("?")[0]
                    if full not in links:
                        links.append(full)
        print(f"[104] collected {len(links)} links for {search_term!r}")
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            bypass_cloudflare_challenge(page)
            human_delay(1.0, 2.0)
            print(f"[104] job page — url={page.url!r} title={page.title()!r}")

            # Dismiss intro if present
            try:
                page.get_by_role("button", name="Skip").click(timeout=5000)
                human_delay(0.5, 1.0)
            except Exception:
                pass

            # Dismiss any lingering popup
            try:
                page.keyboard.press("Escape")
                human_delay(0.3, 0.6)
            except Exception:
                pass
            try:
                page.get_by_text("我知了").click(timeout=3000)
                human_delay(0.3, 0.6)
            except Exception:
                pass

            apply_btn = page.get_by_text("應徵", exact=True).first
            if not apply_btn.count():
                apply_btn = page.get_by_text("我要應徵", exact=True).first
            if not apply_btn.count():
                apply_btn = page.locator(".apply-button__button").first
            if not apply_btn.count():
                btns = page.evaluate("""() =>
                    Array.from(document.querySelectorAll('button, a, div[class*="apply"]'))
                        .map(el => ({text: el.innerText.trim().slice(0,30), cls: el.className.slice(0,50)}))
                        .filter(el => el.text || el.cls)
                        .slice(0, 8)
                """)
                print(f"[104] no apply btn — {btns}")
                return ApplyResult(status="skipped", error="apply button not found")

            apply_btn.click()
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)

            # Handle screening questions if present
            question_els = page.query_selector_all('textarea.apply-question, input.apply-question')
            if question_els and self._ai_screening:
                questions = [el.get_attribute("placeholder") or "" for el in question_els]
                answers = answer_screening_questions(questions, resume_text, self._claude_api_key)
                for el, answer in zip(question_els, answers):
                    el.fill(answer)
                    human_delay(0.3, 0.8)
            elif question_els and not self._ai_screening:
                return ApplyResult(status="skipped", screening_links=[url])

            # Cover letter — select custom template 1
            try:
                page.locator("div").filter(has_text=re.compile(r"^系統預設$")).click(timeout=5000)
                human_delay(0.3, 0.6)
                page.get_by_text("自訂推薦信1").click()
                human_delay(0.3, 0.6)
            except Exception:
                pass

            submit_btn = page.get_by_role("button", name=re.compile(r"確認送出"))
            if not submit_btn.count():
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn.click()
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)

            try:
                page.get_by_text("應徵成功", exact=False).wait_for(timeout=8000)
            except Exception:
                return ApplyResult(status="skipped", screening_links=[url])

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

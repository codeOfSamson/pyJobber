import json
import os
import random
import re
import urllib.parse
import boto3
from patchright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL = "https://www.linkedin.com/jobs/"

AUTH_LOCAL = "auth_linkedin.json"
AUTH_ECS = "/tmp/auth_linkedin.json"
AUTH_S3_KEY = "auth_linkedin.json"

MIN_LINKS_PER_RUN = 15
MAX_LINKS_PER_RUN = 25
MAX_CONTINUE_STEPS = 10


def _auth_path() -> str:
    return AUTH_ECS if os.environ.get("ENV") == "production" else AUTH_LOCAL


def _download_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.download_file(os.environ["CONFIG_BUCKET"], AUTH_S3_KEY, AUTH_ECS)
        print("[linkedin] auth file downloaded from S3")
    except Exception:
        pass


def _upload_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.upload_file(AUTH_ECS, os.environ["CONFIG_BUCKET"], AUTH_S3_KEY)
        print("[linkedin] auth file uploaded to S3")
    except Exception:
        pass


class LinkedInScraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["linkedin_email"]
        self._password = secrets["linkedin_password"]
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
            page.goto(JOBS_URL, wait_until="domcontentloaded", timeout=20000)
            if "/login" not in page.url and "/authwall" not in page.url:
                print("[linkedin] session loaded from auth file — skipping login")
                return
            print("[linkedin] saved session expired — doing full login")

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector('input[type="email"]:visible', timeout=10000)
        human_delay(0.5, 1.0)
        page.fill('input[type="email"]:visible', self._email)
        page.fill('input[type="password"]:visible', self._password)
        human_delay(0.3, 0.6)
        page.press('input[type="password"]:visible', "Enter")
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
        except Exception:
            pass
        page.wait_for_load_state("domcontentloaded")
        human_delay(1.0, 2.0)
        logged_in = "/login" not in page.url
        print(f"[linkedin] login complete — url={page.url!r} logged_in={logged_in}")

        if logged_in:
            page.context.storage_state(path=auth)
            print("[linkedin] auth file saved")
            if os.environ.get("ENV") == "production":
                _upload_auth()

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        links: list = []
        encoded = urllib.parse.quote(search_term)
        location = urllib.parse.quote("Minnesota")
        remote_param = "&f_WT=2" if remote_only else ""
        for p in range(pages):
            start = p * 25
            url = (
                f"https://www.linkedin.com/jobs/search/?keywords={encoded}"
                f"&location={location}&f_AL=true{remote_param}&start={start}"
            )
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.5, 3.0)
            anchors = page.query_selector_all('a[href*="/jobs/view/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                full = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                full = full.split("?")[0]
                if full not in links:
                    links.append(full)
        print(f"[linkedin] collected {len(links)} links for {search_term!r}")

        random.shuffle(links)
        capped = links[:random.randint(MIN_LINKS_PER_RUN, MAX_LINKS_PER_RUN)]
        print(f"[linkedin] capped to {len(capped)} links for this run")
        return capped

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)
            print(f"[linkedin] job page — url={page.url!r} title={page.title()!r}")

            easy_apply = page.get_by_role("link", name="Easy Apply to this job")
            if not easy_apply.count():
                return ApplyResult(status="skipped", error="no Easy Apply link — external application")

            easy_apply.click()
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)

            unsupported_field_js = """() => {
                const modal = document.querySelector('.jobs-easy-apply-modal') ||
                    document.querySelector('[role="dialog"]');
                if (!modal) return false;
                return !!modal.querySelector(
                    'input[type="radio"], input[type="file"], [role="radio"], [role="combobox"], [role="listbox"]'
                );
            }"""
            unfilled_dropdown_js = """() => {
                const modal = document.querySelector('.jobs-easy-apply-modal') ||
                    document.querySelector('[role="dialog"]');
                if (!modal) return false;
                const selects = Array.from(modal.querySelectorAll('select'));
                return selects.some(s => !s.value || s.value === 'Select an option');
            }"""
            question_texts_js = """() => {
                const isQuestion = (s) => /\\?\\s*\\**\\s*$/.test(s || '');
                const fields = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], textarea'));
                return fields
                    .map(el => el.getAttribute('aria-label')
                        || (el.labels && el.labels[0] && el.labels[0].innerText)
                        || el.getAttribute('placeholder')
                        || '')
                    .map(s => s.trim())
                    .filter(isQuestion);
            }"""

            for _ in range(MAX_CONTINUE_STEPS):
                if page.evaluate(unsupported_field_js):
                    page.keyboard.press("Escape")
                    return ApplyResult(
                        status="skipped",
                        error="unrecognized field type present (radio/file upload/combobox) — not supported this version",
                        screening_links=[url],
                    )
                if page.evaluate(unfilled_dropdown_js):
                    page.keyboard.press("Escape")
                    return ApplyResult(
                        status="skipped",
                        error="dropdown field requires a manual selection — not prefilled",
                        screening_links=[url],
                    )

                question_texts = page.evaluate(question_texts_js)
                for question_text in question_texts:
                    if not self._ai_screening:
                        return ApplyResult(
                            status="skipped",
                            error="text screening question found but ai_screening is disabled",
                            screening_links=[url],
                        )
                    answer = answer_screening_questions([question_text], resume_text, self._claude_api_key)[0]
                    page.get_by_role("textbox", name=question_text, exact=True).fill(answer)
                    human_delay(0.3, 0.8)

                continue_btn = page.get_by_role("button", name="Continue to next step")
                if not continue_btn.count():
                    break
                continue_btn.click()
                page.wait_for_load_state("domcontentloaded")
                human_delay(1.0, 2.0)

            review_btn = page.get_by_role("button", name="Review your application")
            if review_btn.count():
                review_btn.click()
                human_delay(1.0, 2.0)

            submit_btn = page.get_by_role("button", name="Submit application")
            if not submit_btn.count():
                return ApplyResult(status="skipped", screening_links=[url])
            submit_btn.click()
            human_delay(1.0, 2.0)

            confirmed = True
            try:
                page.get_by_text("Application submitted", exact=False).wait_for(timeout=8000)
            except Exception:
                confirmed = False

            try:
                dismiss_btn = page.get_by_role("button", name=re.compile(r"Dismiss|Not now|Done", re.I))
                dismiss_btn.first.click(timeout=5000)
            except Exception:
                pass

            if not confirmed:
                return ApplyResult(status="failed", error="submit click did not register — no confirmation text found")

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))

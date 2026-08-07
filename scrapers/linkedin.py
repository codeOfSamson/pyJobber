import json
import os
import random
import urllib.parse
import boto3
from patchright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult

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
            if page.get_by_role("link", name="Sign in").count() == 0:
                print("[linkedin] session loaded from auth file — skipping login")
                return
            print("[linkedin] saved session expired — doing full login")

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#username", timeout=10000)
        human_delay(0.5, 1.0)
        page.fill("#username", self._email)
        page.fill("#password", self._password)
        human_delay(0.3, 0.6)
        page.click('button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        human_delay(3.0, 5.0)
        logged_in = page.get_by_role("link", name="Sign in").count() == 0
        print(f"[linkedin] login complete — url={page.url!r} logged_in={logged_in}")

        if logged_in:
            page.context.storage_state(path=auth)
            print("[linkedin] auth file saved")
            if os.environ.get("ENV") == "production":
                _upload_auth()

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        links: list = []
        encoded = urllib.parse.quote(search_term)
        remote_param = "&f_WT=2" if remote_only else ""
        for p in range(pages):
            start = p * 25
            url = (
                f"https://www.linkedin.com/jobs/search/?keywords={encoded}"
                f"&f_AL=true{remote_param}&start={start}"
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
        return ApplyResult(status="skipped", error="not implemented")

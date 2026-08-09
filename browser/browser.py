import os
import random
import tempfile
import time
from patchright.sync_api import BrowserContext, Page

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def create_browser_context(playwright, locale: str = None) -> BrowserContext:
    production = os.environ.get("ENV") == "production"
    args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"] if production else []
    return playwright.chromium.launch_persistent_context(
        user_data_dir=tempfile.mkdtemp(),
        headless=False,
        args=args,
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale=locale,
    )


def create_page(context: BrowserContext) -> Page:
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(30000)
    return page


def human_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def bypass_cloudflare_challenge(page: Page, timeout: int = 8000) -> None:
    if "Just a moment" not in page.title():
        return
    try:
        cf_frame = page.frame_locator('iframe[src*="challenges.cloudflare.com"]')
        cf_frame.locator('input[type="checkbox"]').click(timeout=timeout)
        page.wait_for_load_state("domcontentloaded")
        human_delay(2.0, 4.0)
    except Exception:
        pass

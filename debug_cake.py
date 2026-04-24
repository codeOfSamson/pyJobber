"""
Interactive CakeResume debug script.
Runs headed with DevTools open so you can inspect the page at any pause() call.

Usage:
    python debug_cake.py                  # browse listing page
    python debug_cake.py --login          # log in first, then pause
    python debug_cake.py --job <url>      # open a specific job page and pause
"""
import argparse
from playwright.sync_api import sync_playwright
from secrets.loader import load_secrets

LISTING = "https://www.cakeresume.com/jobs?q=python&remote=true&page=1"
LOGIN_URL = "https://www.cakeresume.com/users/sign_in"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true", help="Log in before pausing")
    parser.add_argument("--job", metavar="URL", help="Open a specific job URL and pause")
    args = parser.parse_args()

    secrets = load_secrets()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            devtools=True,  # opens DevTools automatically
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        if args.login:
            print("Logging in...")
            page.goto(LOGIN_URL)
            page.wait_for_selector('[name="email"]')
            page.fill('[name="email"]', secrets["cakeresume_email"])
            page.fill('[name="password"]', secrets["cakeresume_password"])
            page.click('[type="submit"]')
            page.wait_for_load_state("networkidle")
            print("Logged in. Pausing — inspect away.")
            page.pause()

        target = args.job or LISTING
        print(f"Navigating to: {target}")
        page.goto(target)
        page.wait_for_load_state("networkidle")

        if args.job:
            # Dump every button and link so we can find the apply selector
            print("\n--- All <button> elements ---")
            for btn in page.query_selector_all("button"):
                print(f"  text={btn.inner_text().strip()!r:30}  class={btn.get_attribute('class')!r}")

            print("\n--- All <a> elements with href ---")
            for a in page.query_selector_all("a[href]"):
                text = a.inner_text().strip()
                href = a.get_attribute("href") or ""
                cls = a.get_attribute("class") or ""
                if text or "apply" in href.lower() or "apply" in cls.lower():
                    print(f"  text={text!r:30}  href={href!r:50}  class={cls!r}")
        else:
            links = page.query_selector_all('a[href*="/jobs/"]')
            print(f"\nFound {len(links)} a[href*='/jobs/'] links:")
            for a in links[:10]:
                print(" ", a.get_attribute("href"))

        print("\nPaused. Use the Playwright Inspector or DevTools to explore.")
        print("In DevTools console you can run: document.querySelectorAll('...')")
        page.pause()

        browser.close()


if __name__ == "__main__":
    main()

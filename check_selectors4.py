"""Find the real 104.com.tw login URL by following the login button."""
from playwright.sync_api import sync_playwright


def find_104_real_login(page):
    print("\n=== 104.com.tw: trace the login button ===")
    page.goto("https://www.104.com.tw/job/8zc8e", timeout=20000)
    page.wait_for_load_state("networkidle")

    # Find the "立即登入" link and where it goes
    all_links = page.query_selector_all("a")
    for a in all_links:
        text = a.inner_text().strip()
        href = a.get_attribute("href") or ""
        if "登入" in text or "login" in href.lower() or "signin" in href.lower():
            print(f"  login link: text={text!r} href={href!r}")

    # Try clicking the login button and see where it navigates
    login_btn = page.query_selector('a:has-text("立即登入")')
    if login_btn:
        href = login_btn.get_attribute("href")
        print(f"\n  '立即登入' href: {href!r}")
        if href and href.startswith("http"):
            page.goto(href, timeout=20000)
            page.wait_for_load_state("networkidle")
            print(f"  navigated to: {page.url}")
            inputs = page.query_selector_all("input")
            for inp in inputs:
                print(f"    input name={inp.get_attribute('name')!r} type={inp.get_attribute('type')!r} id={inp.get_attribute('id')!r}")
            # Also check iframes
            for i, frame in enumerate(page.frames):
                print(f"    frame[{i}]: {frame.url}")
                try:
                    frame_inputs = frame.query_selector_all("input")
                    for inp in frame_inputs:
                        print(f"      input name={inp.get_attribute('name')!r} type={inp.get_attribute('type')!r} id={inp.get_attribute('id')!r} placeholder={inp.get_attribute('placeholder')!r}")
                except Exception as e:
                    print(f"      inaccessible: {e}")

    # Also check the main page nav
    print("\n  checking main page nav for login:")
    page.goto("https://www.104.com.tw/", timeout=20000)
    page.wait_for_load_state("networkidle")
    all_links = page.query_selector_all("a, button")
    for el in all_links:
        text = el.inner_text().strip()
        href = el.get_attribute("href") or ""
        if "登入" in text or "login" in href.lower():
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            print(f"  <{tag}> text={text!r} href={href!r}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        ).new_page()
        try:
            find_104_real_login(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()

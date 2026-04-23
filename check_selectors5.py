"""Understand the 104 signin flow — does password appear after submitting identity?"""
from playwright.sync_api import sync_playwright


def check_104_signin_flow(page):
    print("\n=== 104.com.tw: signin flow ===")
    page.goto("https://signin.104.com.tw/", timeout=20000)
    page.wait_for_load_state("networkidle")
    print(f"  url: {page.url}")

    # Show all inputs at load
    inputs = page.query_selector_all("input")
    print(f"  inputs at load ({len(inputs)}):")
    for inp in inputs:
        print(f"    name={inp.get_attribute('name')!r} type={inp.get_attribute('type')!r} id={inp.get_attribute('id')!r} placeholder={inp.get_attribute('placeholder')!r} class={inp.get_attribute('class')!r}")

    # Show all buttons
    buttons = page.query_selector_all("button")
    print(f"  buttons ({len(buttons)}):")
    for btn in buttons:
        print(f"    text={btn.inner_text().strip()!r} type={btn.get_attribute('type')!r} class={btn.get_attribute('class')!r}")

    # Type a fake identity and see if password field appears
    identity_input = page.query_selector('[name="identity"]')
    if identity_input:
        identity_input.fill("test@test.com")
        page.keyboard.press("Tab")
        page.wait_for_timeout(1000)

        inputs_after = page.query_selector_all("input")
        print(f"\n  inputs after filling identity ({len(inputs_after)}):")
        for inp in inputs_after:
            print(f"    name={inp.get_attribute('name')!r} type={inp.get_attribute('type')!r} id={inp.get_attribute('id')!r} placeholder={inp.get_attribute('placeholder')!r}")

        # Try pressing Enter / clicking Next
        submit = page.query_selector('button[type="submit"], button:has-text("下一步"), button:has-text("Next")')
        if submit:
            print(f"  found submit/next button: {submit.inner_text().strip()!r}")
            submit.click()
            page.wait_for_timeout(1500)
            inputs_after_submit = page.query_selector_all("input")
            print(f"\n  inputs after clicking next ({len(inputs_after_submit)}):")
            for inp in inputs_after_submit:
                print(f"    name={inp.get_attribute('name')!r} type={inp.get_attribute('type')!r} id={inp.get_attribute('id')!r} placeholder={inp.get_attribute('placeholder')!r}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        ).new_page()
        try:
            check_104_signin_flow(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()

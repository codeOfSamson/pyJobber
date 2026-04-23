"""Second pass — investigate failing selectors in detail."""
from playwright.sync_api import sync_playwright
import urllib.parse


def inspect_cakeresume_links(page):
    print("\n=== CakeResume: detail link patterns ===")
    page.goto("https://www.cakeresume.com/jobs?q=python&remote=true&page=1", timeout=20000)
    page.wait_for_load_state("networkidle")
    anchors = page.query_selector_all('a[href*="/jobs/"]')
    seen = set()
    for a in anchors:
        href = a.get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            full = href if href.startswith("http") else f"https://www.cakeresume.com{href}"
            print(f"  {full}")


def inspect_104_login(page):
    print("\n=== 104.com.tw: login page DOM ===")
    page.goto("https://www.104.com.tw/user/login", timeout=20000)
    page.wait_for_load_state("networkidle")

    # Check for iframes
    frames = page.frames
    print(f"  frames on page: {len(frames)}")
    for i, frame in enumerate(frames):
        print(f"    frame[{i}] url: {frame.url}")

    # Check all inputs
    inputs = page.query_selector_all("input")
    print(f"  input elements: {len(inputs)}")
    for inp in inputs:
        name = inp.get_attribute("name")
        type_ = inp.get_attribute("type")
        id_ = inp.get_attribute("id")
        placeholder = inp.get_attribute("placeholder")
        print(f"    input name={name!r} type={type_!r} id={id_!r} placeholder={placeholder!r}")

    # Check buttons
    buttons = page.query_selector_all("button")
    print(f"  button elements: {len(buttons)}")
    for btn in buttons:
        type_ = btn.get_attribute("type")
        text = btn.inner_text().strip()[:40]
        class_ = btn.get_attribute("class")
        print(f"    button type={type_!r} text={text!r} class={class_!r}")

    # Check if there are inputs inside iframes
    for i, frame in enumerate(frames[1:], 1):
        try:
            inputs_in_frame = frame.query_selector_all("input")
            if inputs_in_frame:
                print(f"  inputs in frame[{i}]:")
                for inp in inputs_in_frame:
                    name = inp.get_attribute("name")
                    type_ = inp.get_attribute("type")
                    id_ = inp.get_attribute("id")
                    print(f"    input name={name!r} type={type_!r} id={id_!r}")
        except Exception as e:
            print(f"    frame[{i}] not accessible: {e}")


def inspect_104_apply_btn(page):
    print("\n=== 104.com.tw: job detail apply button ===")
    term = urllib.parse.quote("python")
    page.goto(f"https://www.104.com.tw/jobs/search/?keyword={term}&remoteWork=1&page=1", timeout=20000)
    page.wait_for_load_state("networkidle")
    anchors = page.query_selector_all('a[href*="/job/"]')
    job_links = list(dict.fromkeys(
        (h if h.startswith("http") else f"https://www.104.com.tw{h}").split("?")[0]
        for a in anchors
        if (h := a.get_attribute("href")) and "/job/" in h
    ))
    if not job_links:
        print("  no job links found")
        return

    page.goto(job_links[0], timeout=20000)
    page.wait_for_load_state("networkidle")
    print(f"  visiting: {job_links[0]}")

    # Show all links and buttons with 'apply' or Chinese apply text
    all_els = page.query_selector_all("a, button")
    print("  all interactive elements (first 30):")
    for el in all_els[:30]:
        tag = el.evaluate("el => el.tagName.toLowerCase()")
        text = el.inner_text().strip()[:50]
        class_ = el.get_attribute("class") or ""
        href = el.get_attribute("href") or ""
        print(f"    <{tag}> text={text!r} class={class_[:60]!r} href={href[:60]!r}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        ).new_page()
        try:
            inspect_cakeresume_links(page)
            inspect_104_login(page)
            inspect_104_apply_btn(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()

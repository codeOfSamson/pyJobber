"""Find the real 104.com.tw login page and verify apply button deeper in the page."""
from playwright.sync_api import sync_playwright
import urllib.parse


def find_104_login(page):
    print("\n=== 104.com.tw: find login URL ===")
    # Try candidate login URLs
    candidates = [
        "https://member.104.com.tw/login",
        "https://www.104.com.tw/user/login",
        "https://www.104.com.tw/member/login",
        "https://www.104.com.tw/login",
    ]
    for url in candidates:
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle")
            final_url = page.url
            inputs = page.query_selector_all("input")
            input_info = [(i.get_attribute("name"), i.get_attribute("type"), i.get_attribute("id")) for i in inputs]
            print(f"  {url} -> {final_url}")
            print(f"    inputs: {input_info}")
            email_input = page.query_selector('[name="id"], input[type="email"], input[type="text"]')
            if email_input:
                print(f"    found usable input!")
        except Exception as e:
            print(f"  {url} -> ERROR: {e}")


def find_104_apply_btn(page):
    print("\n=== 104.com.tw: full interactive element scan on job detail ===")
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
        print("  no job links")
        return

    page.goto(job_links[0], timeout=20000)
    page.wait_for_load_state("networkidle")
    print(f"  visiting: {job_links[0]}")

    # Scan ALL elements for apply-related text/classes
    all_els = page.query_selector_all("a, button")
    print(f"  total interactive elements: {len(all_els)}")
    apply_keywords = ["應徵", "apply", "btn-apply", "立即", "投遞"]
    for el in all_els:
        text = el.inner_text().strip()
        class_ = el.get_attribute("class") or ""
        href = el.get_attribute("href") or ""
        if any(kw in text.lower() or kw in class_.lower() or kw in href.lower() for kw in apply_keywords):
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            print(f"    <{tag}> text={text[:60]!r} class={class_[:80]!r}")


def check_cakeresume_new_selector(page):
    print("\n=== CakeResume: test new selector a[href*='/companies/'][href*='/jobs/'] ===")
    page.goto("https://www.cakeresume.com/jobs?q=python&remote=true&page=1", timeout=20000)
    page.wait_for_load_state("networkidle")
    anchors = page.query_selector_all('a[href*="/companies/"][href*="/jobs/"]')
    job_links = []
    for a in anchors:
        href = a.get_attribute("href")
        if href:
            full = href if href.startswith("http") else f"https://www.cakeresume.com{href}"
            if full not in job_links:
                job_links.append(full)
    print(f"  found {len(job_links)} job detail links")
    for l in job_links[:5]:
        print(f"    {l}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        ).new_page()
        try:
            check_cakeresume_new_selector(page)
            find_104_login(page)
            find_104_apply_btn(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()

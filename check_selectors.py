"""
Check that CakeResume and 104.com.tw selectors still match the live DOM.
Visits public pages only — no login required.
"""
from playwright.sync_api import sync_playwright

PASS = "  [PASS]"
FAIL = "  [FAIL]"


def check(label, found):
    mark = PASS if found else FAIL
    print(f"{mark} {label}")
    return found


def check_cakeresume(page):
    print("\n=== CakeResume ===")

    # Login page selectors
    page.goto("https://www.cakeresume.com/users/sign_in", timeout=20000)
    page.wait_for_load_state("networkidle")
    check("login: [name='email']", page.query_selector('[name="email"]') is not None)
    check("login: [name='password']", page.query_selector('[name="password"]') is not None)
    check("login: [type='submit']", page.query_selector('[type="submit"]') is not None)

    # Search / listing page selectors
    page.goto("https://www.cakeresume.com/jobs?q=python&remote=true&page=1", timeout=20000)
    page.wait_for_load_state("networkidle")
    anchors = page.query_selector_all('a[href*="/jobs/"]')
    job_links = []
    for a in anchors:
        href = a.get_attribute("href")
        if href and "/jobs/" in href and not href.endswith("/jobs/"):
            full = href if href.startswith("http") else f"https://www.cakeresume.com{href}"
            if full not in job_links:
                job_links.append(full)

    # Filter to actual job detail pages (not category/filter pages like /jobs/python)
    # Real job listings have a numeric or slug pattern after /jobs/
    detail_links = [l for l in job_links if any(c.isdigit() for c in l.split("/jobs/")[-1])]
    if not detail_links:
        detail_links = job_links  # fallback if heuristic misses

    check(f"listing: a[href*='/jobs/'] ({len(job_links)} total, {len(detail_links)} likely detail)", len(job_links) > 0)
    print(f"    all samples (first 5): {job_links[:5]}")

    # Job detail page — check apply button selector
    if detail_links:
        page.goto(detail_links[0], timeout=20000)
        page.wait_for_load_state("networkidle")
        apply_btn = page.query_selector('button:has-text("Apply"), a:has-text("Apply now")')
        check("detail: apply button (button:has-text('Apply') or a:has-text('Apply now'))", apply_btn is not None)
        if not apply_btn:
            # Show what buttons/links are visible to help tune selector
            btns = page.query_selector_all("button, a.btn")
            visible_text = [b.inner_text().strip() for b in btns if b.inner_text().strip()][:10]
            print(f"    visible buttons/links: {visible_text}")


def check_job104(page):
    print("\n=== 104.com.tw ===")

    # Login page selectors
    page.goto("https://www.104.com.tw/user/login", timeout=20000)
    page.wait_for_load_state("networkidle")
    check("login: [name='id']", page.query_selector('[name="id"]') is not None)
    check("login: [name='passwd']", page.query_selector('[name="passwd"]') is not None)
    check("login: button[type='submit']", page.query_selector('button[type="submit"]') is not None)

    # Search / listing page selectors
    import urllib.parse
    term = urllib.parse.quote("python")
    page.goto(f"https://www.104.com.tw/jobs/search/?keyword={term}&remoteWork=1&page=1", timeout=20000)
    page.wait_for_load_state("networkidle")
    anchors = page.query_selector_all('a[href*="/job/"]')
    job_links = [
        a.get_attribute("href") for a in anchors
        if a.get_attribute("href") and "/job/" in a.get_attribute("href")
    ]
    job_links = list(dict.fromkeys(  # dedupe
        (h if h.startswith("http") else f"https://www.104.com.tw{h}").split("?")[0]
        for h in job_links
    ))
    check(f"listing: a[href*='/job/'] ({len(job_links)} found)", len(job_links) > 0)
    if job_links:
        print(f"    sample: {job_links[0]}")

    # Job detail page — check apply button selector
    if job_links:
        page.goto(job_links[0], timeout=20000)
        page.wait_for_load_state("networkidle")
        apply_btn = page.query_selector('a.btn-apply, button.btn-apply, a:has-text("我要應徵")')
        check("detail: apply button (.btn-apply or a:has-text('我要應徵'))", apply_btn is not None)
        if not apply_btn:
            btns = page.query_selector_all("button, a.btn, a[class*='apply'], button[class*='apply']")
            visible_text = [b.inner_text().strip() for b in btns if b.inner_text().strip()][:10]
            print(f"    visible buttons/links: {visible_text}")
        # Also check screening question selectors (post-apply modal — hard to reach without login)
        # Just verify the classes exist anywhere on the page as a sanity check
        q_els = page.query_selector_all('textarea.apply-question, input.apply-question')
        print(f"    (screening question els visible without login: {len(q_els)} — expected 0)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        ).new_page()
        try:
            check_cakeresume(page)
            check_job104(page)
        finally:
            browser.close()
    print("\nDone.")


if __name__ == "__main__":
    main()

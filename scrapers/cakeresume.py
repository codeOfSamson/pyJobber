import re
from patchright.sync_api import Page
from browser.browser import human_delay, bypass_cloudflare_challenge
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.cakeresume.com/users/sign_in"
SEARCH_URL = "https://www.cakeresume.com/jobs?q={term}&remote=true&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.cakeresume.com/jobs?q={term}&page={page}"


class CakeResumeScraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["cakeresume_email"]
        self._password = secrets["cakeresume_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        page.goto(LOGIN_URL)
        page.wait_for_selector('[name="email"]')
        page.fill('[name="email"]', self._email)
        page.fill('[name="password"]', self._password)
        page.click('[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        human_delay(1.5, 3.0)
        print(f"[cake] login complete — url={page.url!r}")

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        links: list = []
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=search_term.replace(" ", "+"), page=p)
            try:
                page.goto(url)
            except Exception as e:
                print(f"[cake] page {p} goto failed — requested={url!r} landed_on={page.url!r} error={e}")
                continue
            page.wait_for_load_state("domcontentloaded")
            bypass_cloudflare_challenge(page)
            human_delay(1.0, 2.5)
            anchors = page.query_selector_all('a[href*="/companies/"][href*="/jobs/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                full = href.split("?")[0]
                if not full.startswith("http"):
                    full = f"https://www.cakeresume.com{full}"
                if full not in links:
                    links.append(full)
        print(f"[cake] collected {len(links)} links for {search_term!r}")
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            bypass_cloudflare_challenge(page)
            human_delay(1.0, 2.0)
            print(f"[cake] job page — url={page.url!r} title={page.title()!r}")

            if page.get_by_text("ineligible to apply for the same job", exact=False).count():
                return ApplyResult(status="skipped", error="recently applied — ineligible for 1 day")

            # Step 1: Find apply button, get its href — works for both Apply Now and Reapply
            try:
                apply_loc = page.get_by_role("link", name=re.compile(r"apply now|reapply", re.I)).first
                apply_loc.wait_for(state="attached", timeout=15000)
            except Exception:
                apply_links = page.evaluate("""() =>
                    Array.from(document.querySelectorAll('a[href]'))
                        .map(a => ({text: a.innerText.trim().slice(0,40), href: a.getAttribute('href')}))
                        .filter(a => /apply/i.test(a.href) || /apply/i.test(a.text))
                        .slice(0, 5)
                """)
                print(f"[cake] no apply btn — url={page.url!r} title={page.title()!r}")
                print(f"[cake] apply-related links: {apply_links}")
                return ApplyResult(status="skipped", error="apply button not found")

            href = apply_loc.get_attribute("href") or ""
            if not href:
                return ApplyResult(status="skipped", error="apply button has no href")

            apply_url = f"https://www.cake.me{href}" if href.startswith("/") else href

            ap = page.context.new_page()
            ap.goto(apply_url)
            ap.wait_for_load_state("domcontentloaded")
            human_delay(1.5, 2.5)

            # If redirected to external ATS, skip
            if "cake.me" not in ap.url and "cakeresume.com" not in ap.url:
                ap.close()
                return ApplyResult(status="skipped", error=f"external ATS: {ap.url}")

            # Step 2: Personal info page(s) — click Next until we reach the
            # resume-template step or the submit step. Some jobs insert an
            # extra personal-info page, so this isn't always a single click.
            for _ in range(5):
                if ap.get_by_role("button", name="Select Template").count():
                    break
                if ap.get_by_role("button", name="Submit Application").count():
                    break
                next_btn = ap.get_by_role("button", name="Next")
                if not next_btn.count():
                    break
                next_btn.first.click()
                ap.wait_for_load_state("domcontentloaded")
                human_delay(1.0, 2.0)

            # Step 3: Resume template page (optional — some jobs skip
            # straight to submit) — click Select Template, pick topmost
            # radio, confirm
            if ap.get_by_role("button", name="Select Template").count():
                ap.get_by_role("button", name="Select Template").click()
                human_delay(0.5, 1.0)

                # Custom radio divs (no <input type="radio">) — wait for modal to render
                first_radio = ap.wait_for_selector('[class*="radioOuter"]', timeout=5000)
                first_radio.click()
                human_delay(0.3, 0.6)

                ap.get_by_role("button", name="Confirm").click()
                human_delay(0.5, 1.0)
                ap.wait_for_load_state("domcontentloaded")

            # Step 4: Click Next — may land on Submit or Screening Questions
            submit_loc = ap.get_by_role("button", name="Submit Application")
            next_loc = ap.get_by_role("button",  name="Next")

            if next_loc.count():
                next_loc.click()
                ap.wait_for_load_state("domcontentloaded")
                human_delay(1.0, 2.0)
                submit_loc = ap.get_by_role("button", name="Submit Application")
            if not submit_loc.count():
                # Screening questions or unknown step — flag for manual review
                ap.close()
                return ApplyResult(status="skipped", screening_links=[url])

            # Step 5: Submit, then verify it actually registered. A rejected
            # submission (e.g. missing required field) leaves the button in
            # place instead of raising — only a detached button means the
            # application actually went through.
            submit_loc.click()
            submit_loc.wait_for(state="detached", timeout=10000)
            ap.close()
            return ApplyResult(status="applied")

        except Exception as e:
            try:
                ap.close()
            except Exception:
                pass
            return ApplyResult(status="failed", error=str(e))

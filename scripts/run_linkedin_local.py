import os
from patchright.sync_api import sync_playwright
from browser.browser import create_browser_context, create_page
from scrapers.linkedin import LinkedInScraper


def main() -> None:
    secrets = {
        "linkedin_email": os.environ["LINKEDIN_EMAIL"],
        "linkedin_password": os.environ["LINKEDIN_PASSWORD"],
    }
    scraper = LinkedInScraper(secrets=secrets, ai_screening=False, claude_api_key="")

    # LinkedIn reuses the resume already cached on the applicant's profile for Easy Apply,
    # and resume_text is only consumed when ai_screening is enabled (it isn't, here).
    resume_path = ""
    resume_text = ""

    with sync_playwright() as playwright:
        context = create_browser_context(playwright, locale="en-US")
        page = create_page(context)
        scraper.login(page)
        links = scraper.collect_links(page, "software engineer Minneapolis", pages=1, remote_only=True)
        print(f"\nFound {len(links)} links:")
        for link in links:
            print(f"  {link}")

        if links:
            url = links[0]
            print(f"\nApplying to: {url}")
            result = scraper.apply(page, url, resume_path, resume_text)
            print(f"Result: {result.status}" + (f" — {result.error}" if result.error else ""))

        input("\nPress Enter to close the browser...")
        context.close()


if __name__ == "__main__":
    main()

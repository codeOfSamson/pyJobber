"""
Run the CakeResume apply flow against a single job URL.
Launches a headed browser so you can watch what happens.

Usage:
    python test_apply_one.py <job_url>

Example:
    python test_apply_one.py "https://www.cake.me/companies/hour-loop/jobs/software-engineer-f3c235"
"""
import sys
from playwright.sync_api import sync_playwright
from secrets.loader import load_secrets
from config.loader import load_config
from scrapers.cakeresume import CakeResumeScraper
from mailer.reporter import send_alert

if len(sys.argv) < 2:
    print("Usage: python test_apply_one.py <job_url>")
    sys.exit(1)

job_url = sys.argv[1]
secrets = load_secrets()
config = load_config()

scraper = CakeResumeScraper(
    secrets=secrets,
    ai_screening=False,
    claude_api_key=secrets["claude_api_key"],
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page = context.new_page()

    print("Logging in...")
    scraper.login(page)
    print("Logged in.")

    print(f"Applying to: {job_url}")
    result = scraper.apply(page, job_url, resume_path="resume.pdf", resume_text="")
    print(f"\nResult: status={result.status!r}")
    if result.error:
        print(f"  reason: {result.error}")
    if result.screening_links:
        print(f"  screening_links: {result.screening_links}")
        for url in result.screening_links:
            print(f"\nSending alert email for: {url}")
            try:
                send_alert(
                    url=url,
                    from_email=secrets["report_email"],
                    to_email=config["report_email"],
                    password=secrets["email_password"],
                )
                print("  Email sent successfully.")
            except Exception as e:
                print(f"  Email failed: {e}")

    input("\nPress Enter to close the browser...")
    browser.close()

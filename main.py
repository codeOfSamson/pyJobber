import datetime
import os
import traceback
import boto3
from patchright.sync_api import sync_playwright
from pdfminer.high_level import extract_text


from config.loader import load_config
from secrets.loader import load_secrets
from db.client import get_engine, get_session, init_db
from db.models import JobApplication, RunLog
from browser.browser import create_browser_context, create_page
from scrapers.cakeresume import CakeResumeScraper
from scrapers.job104 import Job104Scraper
from mailer.reporter import build_report, build_subject, send_report

SCRAPER_MAP = {
    "cakeresume": CakeResumeScraper,
    "104": Job104Scraper,
}


def get_next_term_index(session, num_terms: int) -> int:
    last_run = session.query(RunLog).order_by(RunLog.id.desc()).first()
    if last_run is None:
        return 0
    return (last_run.term_index + 1) % num_terms


def build_db_url(secrets: dict) -> str:
    return (
        f"mysql+pymysql://{secrets['db_user']}:{secrets['db_password']}"
        f"@{secrets['db_host']}/{secrets['db_name']}"
    )


def _get_resume_path() -> str:
    if os.environ.get("ENV") == "production":
        local_path = "/tmp/resume.pdf"
        s3 = boto3.client("s3")
        s3.download_file(
            Bucket=os.environ["CONFIG_BUCKET"],
            Key="resume.pdf",
            Filename=local_path,
        )
        return local_path
    return os.environ.get("RESUME_PATH", "resume.pdf")


def main() -> None:
    config = load_config()
    secrets = load_secrets()
    smoke_test = os.environ.get("SMOKE_TEST") == "1"

    engine = get_engine(build_db_url(secrets))
    init_db(engine)
    session = get_session(engine)

    term_index = get_next_term_index(session, len(config["search_terms"]))
    search_term = config["search_terms"][term_index]

    resume_path = _get_resume_path()
    resume_text = extract_text(resume_path)

    started_at = datetime.datetime.now()
    total_applied = total_failed = total_skipped = total_dupes = 0
    failed_urls: list[tuple[str, str]] = []
    screening_urls: list[str] = []

    with sync_playwright() as playwright:
        for site_name in config["sites"]:
            scraper = SCRAPER_MAP[site_name](
                secrets=secrets,
                ai_screening=config["ai_screening"],
                claude_api_key=secrets["claude_api_key"],
            )
            context = create_browser_context(playwright)
            page = create_page(context)
            try:
                scraper.login(page)
                links = scraper.collect_links(
                    page, search_term, config["pages_per_site"], config["remote_only"]
                )
                if smoke_test:
                    print(f"[smoke-test] {site_name}: login OK, found {len(links)} links")
                    continue
                max_links = config.get("max_links_per_site")
                if max_links:
                    links = links[:max_links]
                for url in links:
                    if session.query(JobApplication).filter_by(url=url).first():
                        total_dupes += 1
                        continue

                    print(f"  [{site_name}] applying: {url}")
                    result = scraper.apply(page, url, resume_path, resume_text)
                    print(f"  [{site_name}] result: {result.status}" + (f" — {result.error[:80]}" if result.error else ""))
                    session.add(JobApplication(
                        url=url,
                        site=site_name,
                        search_term=search_term,
                        status=result.status,
                        applied_at=datetime.datetime.now(),
                        error_message=result.error,
                        job_updated_at=result.job_updated_at,
                        employer_active_at=result.employer_active_at,
                    ))
                    session.commit()

                    if result.status == "applied":
                        total_applied += 1
                    elif result.status == "failed":
                        total_failed += 1
                        failed_urls.append((url, result.error or "Unknown error"))
                    else:
                        total_skipped += 1

                    screening_urls.extend(result.screening_links)
            finally:
                context.close()

    if smoke_test:
        print("[smoke-test] passed")
        return

    completed_at = datetime.datetime.now()
    session.add(RunLog(
        run_date=started_at.date(),
        search_term_used=search_term,
        term_index=term_index,
        total_applied=total_applied,
        total_failed=total_failed,
        total_skipped=total_skipped,
        completed_at=completed_at,
    ))
    session.commit()
    session.close()

    body = build_report(
        search_term=search_term,
        sites=config["sites"],
        pages_per_site=config["pages_per_site"],
        started_at=started_at,
        completed_at=completed_at,
        total_applied=total_applied,
        total_failed=total_failed,
        total_skipped=total_skipped,
        total_dupes=total_dupes,
        failed_urls=failed_urls,
        screening_urls=screening_urls,
    )
    send_report(
        body=body,
        subject=build_subject(started_at.strftime("%Y-%m-%d"), config["sites"], search_term),
        from_email=secrets["report_email"],
        to_email=config["report_email"],
        password=secrets["email_password"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_body = f"Autojobber crashed with the following error:\n\n{traceback.format_exc()}"
        print(error_body)
        try:
            secrets = load_secrets()
            config = load_config()
            send_report(
                body=error_body,
                subject=f"Jobber Failed — {datetime.datetime.now().strftime('%Y-%m-%d')}",
                from_email=secrets["report_email"],
                to_email=config["report_email"],
                password=secrets["email_password"],
            )
        except Exception:
            print("failed to send crash email")
        raise


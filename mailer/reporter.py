import smtplib
from datetime import datetime
from email.mime.text import MIMEText

SITE_DISPLAY = {"cakeresume": "CakeResume", "104": "104.com.tw"}


def build_report(
    search_term: str,
    sites: list[str],
    pages_per_site: int,
    started_at: datetime,
    completed_at: datetime,
    total_applied: int,
    total_failed: int,
    total_skipped: int,
    failed_urls: list[tuple[str, str]],
    screening_urls: list[str],
) -> str:
    sites_str = ", ".join(SITE_DISPLAY.get(s, s) for s in sites)
    lines = [
        "Run Summary",
        "─" * 35,
        f"Search term:   {search_term}",
        f"Sites:         {sites_str}",
        f"Pages/site:    {pages_per_site}",
        f"Started:       {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Completed:     {completed_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Results",
        "─" * 35,
        f"Applied:       {total_applied}",
        f"Failed:        {total_failed}",
        f"Skipped:       {total_skipped}",
    ]
    if failed_urls:
        lines += ["", "Failed Applications", "─" * 35]
        for i, (url, error) in enumerate(failed_urls, 1):
            lines.append(f"{i}. {url} — {error}")
    if screening_urls:
        lines += ["", "Screening Questions (manual review needed)", "─" * 35]
        for i, url in enumerate(screening_urls, 1):
            lines.append(f"{i}. {url}")
    return "\n".join(lines)


def build_subject(run_date: str, sites: list[str], search_term: str) -> str:
    sites_str = " + ".join(SITE_DISPLAY.get(s, s) for s in sites)
    return f'AutoJobber Daily Report — {run_date} | {sites_str} | "{search_term}"'


def send_report(body: str, subject: str, from_email: str, to_email: str, password: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, password)
        server.send_message(msg)

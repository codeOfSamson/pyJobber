import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Optional

SITE_DISPLAY = {"cakeresume": "CakeResume", "104": "104.com.tw", "linkedin": "LinkedIn"}


def build_report(
    search_term: str,
    sites: list[str],
    pages_per_site: int,
    started_at: datetime,
    completed_at: datetime,
    total_applied: int,
    total_failed: int,
    total_skipped: int,
    total_dupes: int,
    failed_urls: list[tuple[str, str]],
    screening_urls: list[str],
    linkedin_urls: Optional[list[tuple[str, str]]] = None,
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
        f"Dupes:         {total_dupes}",
    ]
    if failed_urls:
        lines += ["", "Failed Applications", "─" * 35]
        for i, (url, error) in enumerate(failed_urls, 1):
            lines.append(f"{i}. {url} — {error}")
    if screening_urls:
        lines += ["", "Screening Questions (manual review needed)", "─" * 35]
        for i, url in enumerate(screening_urls, 1):
            lines.append(f"{i}. {url}")
    if linkedin_urls:
        lines += ["", "LinkedIn Jobs Attempted", "─" * 35]
        for i, (url, status) in enumerate(linkedin_urls, 1):
            lines.append(f"{i}. [{status}] {url}")
    return "\n".join(lines)


def build_subject(run_date: str, sites: list[str], search_term: str) -> str:
    sites_str = " + ".join(SITE_DISPLAY.get(s, s) for s in sites)
    return f'AutoJobber Daily Report — {run_date} | {sites_str} | "{search_term}"'


def send_alert(url: str, from_email: str, to_email: str, password: str) -> None:
    body = f"AutoJobber hit screening questions and needs manual review:\n\n{url}"
    subject = "AutoJobber — Screening Questions Need Review"
    send_report(body=body, subject=subject, from_email=from_email, to_email=to_email, password=password)


def send_report(body: str, subject: str, from_email: str, to_email: str, password: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, password)
        server.send_message(msg)

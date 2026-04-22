# tests/test_reporter.py
import datetime
from mailer.reporter import build_report, build_subject


def test_build_report_basic():
    body = build_report(
        search_term="python developer",
        sites=["cakeresume", "104"],
        pages_per_site=3,
        started_at=datetime.datetime(2026, 4, 22, 9, 0, 12),
        completed_at=datetime.datetime(2026, 4, 22, 9, 14, 37),
        total_applied=12,
        total_failed=0,
        total_skipped=8,
        failed_urls=[],
        screening_urls=[],
    )
    assert "python developer" in body
    assert "CakeResume" in body
    assert "104.com.tw" in body
    assert "Applied:       12" in body
    assert "Failed:        0" in body
    assert "Failed Applications" not in body
    assert "Screening Questions" not in body


def test_build_report_includes_failures():
    body = build_report(
        search_term="engineer",
        sites=["cakeresume"],
        pages_per_site=2,
        started_at=datetime.datetime(2026, 4, 22, 9, 0, 0),
        completed_at=datetime.datetime(2026, 4, 22, 9, 5, 0),
        total_applied=5,
        total_failed=2,
        total_skipped=1,
        failed_urls=[
            ("https://cakeresume.com/jobs/xyz", "TimeoutError"),
            ("https://cakeresume.com/jobs/abc", "Login expired"),
        ],
        screening_urls=[],
    )
    assert "Failed Applications" in body
    assert "https://cakeresume.com/jobs/xyz" in body
    assert "TimeoutError" in body
    assert "Login expired" in body


def test_build_report_includes_screening_urls():
    body = build_report(
        search_term="engineer",
        sites=["104"],
        pages_per_site=1,
        started_at=datetime.datetime(2026, 4, 22, 9, 0, 0),
        completed_at=datetime.datetime(2026, 4, 22, 9, 2, 0),
        total_applied=3,
        total_failed=0,
        total_skipped=2,
        failed_urls=[],
        screening_urls=["https://www.104.com.tw/job/def"],
    )
    assert "Screening Questions" in body
    assert "https://www.104.com.tw/job/def" in body


def test_build_subject():
    subject = build_subject("2026-04-22", ["cakeresume", "104"], "backend developer")
    assert "2026-04-22" in subject
    assert "CakeResume" in subject
    assert "104" in subject
    assert "backend developer" in subject

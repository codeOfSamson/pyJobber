# tests/test_main.py
import datetime
from main import get_next_term_index, build_db_url
from db.models import RunLog


def test_get_next_term_index_no_prior_runs(session):
    assert get_next_term_index(session, num_terms=4) == 0


def test_get_next_term_index_increments(session):
    run = RunLog(
        run_date=datetime.date(2026, 4, 21),
        search_term_used="python",
        term_index=1,
        total_applied=5,
        total_failed=0,
        total_skipped=2,
    )
    session.add(run)
    session.commit()
    assert get_next_term_index(session, num_terms=4) == 2


def test_get_next_term_index_wraps_around(session):
    run = RunLog(
        run_date=datetime.date(2026, 4, 21),
        search_term_used="python",
        term_index=3,
        total_applied=5,
        total_failed=0,
        total_skipped=2,
    )
    session.add(run)
    session.commit()
    assert get_next_term_index(session, num_terms=4) == 0  # (3 + 1) % 4


def test_build_db_url():
    secrets = {
        "db_user": "admin",
        "db_password": "secret",
        "db_host": "localhost",
        "db_name": "autojobber",
    }
    assert build_db_url(secrets) == "mysql+pymysql://admin:secret@localhost/autojobber"


def test_scraper_map_includes_linkedin():
    from main import SCRAPER_MAP
    from scrapers.linkedin import LinkedInScraper
    assert SCRAPER_MAP["linkedin"] is LinkedInScraper


from scrapers.base import ApplyResult
from main import _needs_review


def test_needs_review_true_when_screening_links_present():
    result = ApplyResult(status="skipped", screening_links=["https://example.com/job/1"])
    assert _needs_review(result) is True


def test_needs_review_false_when_no_screening_links():
    result = ApplyResult(status="applied")
    assert _needs_review(result) is False


from main import _resolve_sites, _resolve_search_term


def test_resolve_sites_uses_override(monkeypatch):
    monkeypatch.setenv("SITES_OVERRIDE", "cakeresume, linkedin")
    assert _resolve_sites({"sites": ["104"]}) == ["cakeresume", "linkedin"]


def test_resolve_sites_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("SITES_OVERRIDE", raising=False)
    assert _resolve_sites({"sites": ["104"]}) == ["104"]


def test_resolve_search_term_uses_override(monkeypatch):
    monkeypatch.setenv("SEARCH_TERM_OVERRIDE", "rust developer")
    assert _resolve_search_term({"search_terms": ["python"]}, 0) == "rust developer"


def test_resolve_search_term_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("SEARCH_TERM_OVERRIDE", raising=False)
    assert _resolve_search_term({"search_terms": ["python", "rust"]}, 1) == "rust"

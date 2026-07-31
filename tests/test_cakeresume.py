# tests/test_cakeresume.py
from unittest.mock import MagicMock
from scrapers.cakeresume import CakeResumeScraper
from scrapers.base import ApplyResult


def _scraper(ai_screening=False):
    return CakeResumeScraper(
        secrets={"cakeresume_email": "a@b.com", "cakeresume_password": "pass"},
        ai_screening=ai_screening,
        claude_api_key="",
    )


def _page():
    page = MagicMock()
    page.query_selector_all.return_value = []
    page.query_selector.return_value = None
    return page


def test_login_navigates_to_cakeresume(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.goto.assert_called_once()
    assert "cakeresume.com" in page.goto.call_args[0][0]


def test_login_fills_email_and_password(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.fill.assert_any_call('[name="email"]', "a@b.com")
    page.fill.assert_any_call('[name="password"]', "pass")


def test_collect_links_returns_href_list(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.cakeresume.com/jobs/test-123"
    page.query_selector_all.return_value = [mock_a]

    links = scraper.collect_links(page, "python developer", pages=1, remote_only=True)
    assert isinstance(links, list)
    assert "https://www.cakeresume.com/jobs/test-123" in links


def test_collect_links_deduplicates(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.cakeresume.com/jobs/same-job"
    page.query_selector_all.return_value = [mock_a, mock_a]

    links = scraper.collect_links(page, "python", pages=1, remote_only=True)
    assert links.count("https://www.cakeresume.com/jobs/same-job") == 1


def test_apply_returns_skipped_when_no_apply_button(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    page.query_selector.return_value = None

    result = scraper.apply(page, "https://www.cakeresume.com/jobs/xyz", "resume.pdf", "resume text")
    assert result.status == "skipped"


def test_apply_returns_skipped_with_screening_link_when_ai_off(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=False)
    page = _page()
    page.get_by_text.return_value.count.return_value = 0  # not "ineligible to apply"

    ap = page.context.new_page.return_value
    ap.url = "https://www.cake.me/companies/acme/jobs/xyz/apply"
    ap.get_by_role.return_value.count.return_value = 0  # no Next/Submit button — unknown step

    result = scraper.apply(page, "https://www.cakeresume.com/jobs/xyz", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "https://www.cakeresume.com/jobs/xyz" in result.screening_links

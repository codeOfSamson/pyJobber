# tests/test_linkedin.py
from unittest.mock import MagicMock
from scrapers.linkedin import LinkedInScraper
from scrapers.base import ApplyResult


def _scraper(ai_screening=False):
    return LinkedInScraper(
        secrets={"linkedin_email": "a@b.com", "linkedin_password": "pass"},
        ai_screening=ai_screening,
        claude_api_key="",
    )


def _page():
    page = MagicMock()
    page.query_selector_all.return_value = []
    page.query_selector.return_value = None
    return page


def test_login_navigates_to_linkedin_when_no_saved_session(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    assert any("linkedin.com" in str(c.args[0]) for c in page.goto.call_args_list)


def test_login_fills_credentials_when_no_saved_session(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.fill.assert_any_call("#username", "a@b.com")
    page.fill.assert_any_call("#password", "pass")


def test_login_skips_full_login_when_saved_session_valid(monkeypatch, tmp_path):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    auth_file = tmp_path / "auth_linkedin.json"
    auth_file.write_text('{"cookies": [{"name": "li_at", "value": "x", "domain": ".linkedin.com", "path": "/"}]}')
    monkeypatch.setattr("scrapers.linkedin._auth_path", lambda: str(auth_file))

    scraper = _scraper()
    page = _page()
    page.get_by_role.return_value.count.return_value = 0  # no "Sign in" link — logged in

    scraper.login(page)

    page.context.add_cookies.assert_called_once()
    # Only the saved-session check navigation happened — no credential fill on top of it.
    page.fill.assert_not_called()


def test_collect_links_returns_href_list(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.linkedin.com/jobs/view/111222333"
    page.query_selector_all.return_value = [mock_a]

    links = scraper.collect_links(page, "python developer", pages=1, remote_only=True)
    assert isinstance(links, list)
    assert "https://www.linkedin.com/jobs/view/111222333" in links


def test_collect_links_deduplicates(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.linkedin.com/jobs/view/999?refId=abc"
    page.query_selector_all.return_value = [mock_a, mock_a]

    links = scraper.collect_links(page, "python", pages=1, remote_only=True)
    assert links.count("https://www.linkedin.com/jobs/view/999") == 1


def test_collect_links_caps_to_15_25_range(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()

    mocks = []
    for i in range(40):
        m = MagicMock()
        m.get_attribute.return_value = f"https://www.linkedin.com/jobs/view/{i}"
        mocks.append(m)
    page.query_selector_all.return_value = mocks

    links = scraper.collect_links(page, "python", pages=1, remote_only=True)
    assert 15 <= len(links) <= 25

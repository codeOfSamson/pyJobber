# tests/test_job104.py
from unittest.mock import MagicMock
from scrapers.job104 import Job104Scraper
from scrapers.base import ApplyResult


def _scraper(ai_screening=False):
    return Job104Scraper(
        secrets={"job104_email": "a@b.com", "job104_password": "pass"},
        ai_screening=ai_screening,
        claude_api_key="",
    )


def _page():
    page = MagicMock()
    page.query_selector_all.return_value = []
    page.query_selector.return_value = None
    return page


def test_login_navigates_to_104(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.goto.assert_called_once()
    assert "104.com.tw" in page.goto.call_args[0][0]


def test_login_fills_credentials(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.fill.assert_called()


def test_collect_links_returns_href_list(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.104.com.tw/job/abc123"
    page.query_selector_all.return_value = [mock_a]

    links = scraper.collect_links(page, "python developer", pages=1, remote_only=True)
    assert isinstance(links, list)
    assert "https://www.104.com.tw/job/abc123" in links


def test_collect_links_deduplicates(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.104.com.tw/job/same?ref=foo"
    page.query_selector_all.return_value = [mock_a, mock_a]

    links = scraper.collect_links(page, "python", pages=1, remote_only=True)
    assert links.count("https://www.104.com.tw/job/same") == 1


def test_apply_returns_skipped_when_no_apply_button(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    page.query_selector.return_value = None

    result = scraper.apply(page, "https://www.104.com.tw/job/abc", "resume.pdf", "resume text")
    assert result.status == "skipped"


def test_apply_returns_skipped_with_screening_link_when_ai_off(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=False)
    page = _page()
    apply_btn = MagicMock()
    question_el = MagicMock()
    question_el.get_attribute.return_value = "請說明您的相關經驗"

    def query_selector_side_effect(sel):
        if "btn-apply" in sel or "應徵" in sel:
            return apply_btn
        return None

    page.query_selector.side_effect = query_selector_side_effect
    page.query_selector_all.return_value = [question_el]

    result = scraper.apply(page, "https://www.104.com.tw/job/abc", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "https://www.104.com.tw/job/abc" in result.screening_links

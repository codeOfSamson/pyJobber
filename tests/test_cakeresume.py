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


def _apply_page_stub(page, select_template_count, submit_count, next_count):
    """Wire up ap.get_by_role so Next/Select Template/Submit Application
    each report an independently controllable .count()."""
    ap = page.context.new_page.return_value
    ap.url = "https://www.cake.me/companies/acme/jobs/xyz/apply"

    next_loc = MagicMock()
    next_loc.count.side_effect = next_count
    select_template_loc = MagicMock()
    select_template_loc.count.side_effect = select_template_count
    submit_loc = MagicMock()
    submit_loc.count.side_effect = submit_count

    def get_by_role(role, name=None, **kw):
        return {"Next": next_loc, "Select Template": select_template_loc, "Submit Application": submit_loc}.get(name, MagicMock())

    ap.get_by_role.side_effect = get_by_role
    return ap, next_loc, select_template_loc, submit_loc


def test_apply_clicks_next_repeatedly_across_multiple_personal_info_pages(monkeypatch):
    # Some jobs insert an extra personal-info page before the submit step —
    # the scraper must click Next until Submit Application actually shows up,
    # not assume a single click is enough.
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=False)
    page = _page()
    page.get_by_text.return_value.count.return_value = 0

    clicks = {"n": 0}
    ap, next_loc, select_template_loc, submit_loc = _apply_page_stub(
        page,
        select_template_count=lambda: 0,  # this job has no resume-template step
        submit_count=lambda: 1 if clicks["n"] >= 3 else 0,
        next_count=lambda: 0 if clicks["n"] >= 3 else 1,
    )
    next_loc.first.click.side_effect = lambda: clicks.__setitem__("n", clicks["n"] + 1)
    submit_loc.wait_for.return_value = None  # button detaches — submission registered

    result = scraper.apply(page, "https://www.cakeresume.com/jobs/xyz", "resume.pdf", "resume text")

    assert clicks["n"] == 3
    assert result.status == "applied"


def test_apply_returns_failed_when_submit_button_never_detaches(monkeypatch):
    # If CakeResume rejects the submission (e.g. missing required field), the
    # Submit button stays on the page instead of raising any error — the
    # scraper must not report "applied" for that.
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=False)
    page = _page()
    page.get_by_text.return_value.count.return_value = 0

    ap, next_loc, select_template_loc, submit_loc = _apply_page_stub(
        page,
        select_template_count=lambda: 0,
        submit_count=lambda: 1,
        next_count=lambda: 0,
    )
    submit_loc.wait_for.side_effect = TimeoutError("Timeout 10000ms exceeded")

    result = scraper.apply(page, "https://www.cakeresume.com/jobs/xyz", "resume.pdf", "resume text")

    assert result.status == "failed"
    assert "submit" in (result.error or "").lower() or "timeout" in (result.error or "").lower()

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
    page.url = "https://www.linkedin.com/feed/"  # post-login URL by default
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
    page.fill.assert_any_call('input[type="email"]:visible', "a@b.com")
    page.fill.assert_any_call('input[type="password"]:visible', "pass")
    page.press.assert_any_call('input[type="password"]:visible', "Enter")


def test_login_skips_full_login_when_saved_session_valid(monkeypatch, tmp_path):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    auth_file = tmp_path / "auth_linkedin.json"
    auth_file.write_text('{"cookies": [{"name": "li_at", "value": "x", "domain": ".linkedin.com", "path": "/"}]}')
    monkeypatch.setattr("scrapers.linkedin._auth_path", lambda: str(auth_file))

    scraper = _scraper()
    page = _page()
    page.url = "https://www.linkedin.com/jobs/"  # not redirected to login/authwall — session still valid

    scraper.login(page)

    page.context.add_cookies.assert_called_once()
    # Only the saved-session check navigation happened — no credential fill on top of it.
    page.fill.assert_not_called()


def test_login_does_full_login_when_saved_session_expired(monkeypatch, tmp_path):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    auth_file = tmp_path / "auth_linkedin.json"
    auth_file.write_text('{"cookies": [{"name": "li_at", "value": "x", "domain": ".linkedin.com", "path": "/"}]}')
    monkeypatch.setattr("scrapers.linkedin._auth_path", lambda: str(auth_file))

    scraper = _scraper()
    page = _page()
    # Loading JOBS_URL with the stale cookie bounces to the login page — session expired.
    page.url = "https://www.linkedin.com/login"

    scraper.login(page)

    page.fill.assert_any_call('input[type="email"]:visible', "a@b.com")
    page.fill.assert_any_call('input[type="password"]:visible', "pass")


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


def test_apply_returns_skipped_when_no_easy_apply_link(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    page.get_by_role.return_value.count.return_value = 0  # no "Easy Apply to this job" link

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "Easy Apply" in result.error


def test_apply_answers_text_screening_question_and_continues(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr(
        "scrapers.linkedin.answer_screening_questions",
        lambda questions, resume_text, api_key: ["5 years"],
    )
    scraper = _scraper(ai_screening=True)
    page = _page()
    page.get_by_role.return_value.count.return_value = 1  # Easy Apply link present

    # First loop pass: one text question, no unsupported fields, no unfilled dropdowns, Continue button present.
    # Second pass: no questions, Continue button present (must iterate again).
    # Third pass: no questions, no Continue button — loop exits.
    page.evaluate.side_effect = [
        False,  # unsupported-field check, pass 1
        False,  # unfilled-dropdown check, pass 1
        ["How many years of work experience do you have with Python?*"],  # questions, pass 1
        False,  # unsupported-field check, pass 2
        False,  # unfilled-dropdown check, pass 2
        [],  # questions, pass 2
        False,  # unsupported-field check, pass 3
        False,  # unfilled-dropdown check, pass 3
        [],  # questions, pass 3
    ]
    continue_calls = {"n": 0}

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        if name == "Continue to next step":
            m.count.return_value = 1 if continue_calls["n"] < 2 else 0
            m.click.side_effect = lambda: continue_calls.__setitem__("n", continue_calls["n"] + 1)
        elif name == "Easy Apply to this job":
            m.count.return_value = 1
        elif name == "Review your application":
            m.count.return_value = 0
        elif name == "Submit application":
            m.count.return_value = 0
        else:
            m.count.return_value = 0
        return m

    page.get_by_role.side_effect = get_by_role

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")

    assert continue_calls["n"] == 2
    page.get_by_role.assert_any_call("textbox", name="How many years of work experience do you have with Python?*", exact=True)


def test_apply_returns_skipped_when_unrecognized_field_present(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        m.count.return_value = 1 if name == "Easy Apply to this job" else 0
        return m

    page.get_by_role.side_effect = get_by_role
    page.evaluate.return_value = True  # unsupported field (e.g. radio/file/combobox) present

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "https://www.linkedin.com/jobs/view/123" in result.screening_links


def test_apply_returns_skipped_when_dropdown_not_prefilled(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        m.count.return_value = 1 if name == "Easy Apply to this job" else 0
        return m

    page.get_by_role.side_effect = get_by_role
    page.evaluate.side_effect = [False, True]  # no unsupported field, but a dropdown is still on its placeholder

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "dropdown" in result.error
    assert "https://www.linkedin.com/jobs/view/123" in result.screening_links


def _apply_stub_for_submit_flow(page, submit_count, dismiss_count, confirmation_count):
    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        if name == "Easy Apply to this job":
            m.count.return_value = 1
        elif name == "Continue to next step":
            m.count.return_value = 0
        elif name == "Review your application":
            m.count.return_value = 0
        elif name == "Submit application":
            m.count.return_value = submit_count()
        else:
            m.first.click.return_value = None
            m.count.return_value = dismiss_count()
        return m

    page.get_by_role.side_effect = get_by_role
    page.evaluate.side_effect = [False, False, []]  # one loop pass: no unsupported field, no unfilled dropdown, no questions
    page.get_by_text.return_value.wait_for.side_effect = (
        None if confirmation_count() else Exception("Timeout 8000ms exceeded")
    )


def test_apply_returns_applied_when_confirmation_text_appears(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()
    _apply_stub_for_submit_flow(page, submit_count=lambda: 1, dismiss_count=lambda: 0, confirmation_count=lambda: 1)

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "applied"


def test_apply_returns_failed_when_confirmation_text_never_appears(monkeypatch):
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()
    _apply_stub_for_submit_flow(page, submit_count=lambda: 1, dismiss_count=lambda: 0, confirmation_count=lambda: 0)

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "failed"


def test_apply_verifies_confirmation_before_dismissing_modal(monkeypatch):
    # Regression test: dismissing the confirmation modal must happen AFTER we've
    # checked for the "Application submitted" text, not before — otherwise the
    # dismiss click removes the very text we're waiting for, and a successful
    # application gets reported as failed.
    monkeypatch.setattr("scrapers.linkedin.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()
    call_order = []

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        if name == "Easy Apply to this job":
            m.count.return_value = 1
        elif name == "Continue to next step":
            m.count.return_value = 0
        elif name == "Review your application":
            m.count.return_value = 0
        elif name == "Submit application":
            m.count.return_value = 1
        else:
            m.count.return_value = 1
            m.first.click.side_effect = lambda **kw: call_order.append("dismiss")
        return m

    page.get_by_role.side_effect = get_by_role
    page.evaluate.side_effect = [False, False, []]  # one loop pass: no unsupported field, no unfilled dropdown, no questions
    page.get_by_text.return_value.wait_for.side_effect = lambda **kw: call_order.append("verify")

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")

    assert call_order == ["verify", "dismiss"]
    assert result.status == "applied"

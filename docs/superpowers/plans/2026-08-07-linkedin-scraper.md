# LinkedIn Easy Apply Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `LinkedInScraper` module that applies to LinkedIn "Easy Apply" jobs, implementing the existing `BaseScraper` interface so it plugs into `main.py`'s orchestration with no changes to the shared run loop.

**Architecture:** A new `scrapers/linkedin.py` file mirrors `scrapers/job104.py`'s session-persistence auth pattern (cookies saved to `auth_linkedin.json`, uploaded/downloaded from S3 in production) and `scrapers/cakeresume.py`'s capped step-loop pattern for the variable-length Easy Apply form. Screening questions are detected via a JS `evaluate()` scan for text fields whose computed label ends in `?`/`?*`, then answered through the existing `ai/screening.py` helper and filled via `page.get_by_role("textbox", name=..., exact=True)`. Any field type outside plain text (radio, dropdown, file upload) aborts that application as `skipped` — out of scope for this version per the design spec.

**Tech Stack:** Python, `patchright` (Playwright fork), `pytest` + `unittest.mock.MagicMock` for scraper tests (no real browser/network in unit tests), MySQL via SQLAlchemy for the `site` enum change.

## Global Constraints

- Continue-loop safety cap: 10 iterations (`MAX_CONTINUE_STEPS = 10`), matching the CakeResume Next-loop fix's cap style.
- Applications-per-run cap for LinkedIn: `random.randint(15, 25)`, applied inside `collect_links()` only — `main.py`'s existing `max_links_per_site` truncation is untouched and still applies uniformly across all sites afterward.
- Auth session file names: `auth_linkedin.json` (local path and S3 key), `/tmp/auth_linkedin.json` (ECS path) — mirrors `job104.py`'s `AUTH_LOCAL`/`AUTH_ECS`/`AUTH_S3_KEY` naming exactly.
- Radio buttons, `<select>` dropdowns, and file-upload fields are explicitly out of scope this version — any step containing one aborts the application as `skipped` with the link in `screening_links`. Do not attempt to handle them.
- New secrets keys: `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` (lowercase `linkedin_email`/`linkedin_password` in the returned secrets dict, matching the existing `cakeresume_email`/`job104_email` naming convention).
- New `JobApplication.site` enum value: `"linkedin"`, added alongside the existing `"cakeresume"`, `"104"`.

---

### Task 1: Add LinkedIn credentials to secrets loader

**Files:**
- Modify: `secrets/loader.py:16-28`
- Test: `tests/test_secrets.py`

**Interfaces:**
- Produces: `load_secrets()` return dict gains `"linkedin_email"` and `"linkedin_password"` keys, consumed by `LinkedInScraper.__init__` in Task 3.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_secrets.py`, inside `test_load_secrets_local`'s `env_file.write_text(...)` block, add two new lines to the fixture text (after the `JOB104_PASSWORD` line):

```python
def test_load_secrets_local(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAKERESUME_EMAIL=cake@test.com\n"
        "CAKERESUME_PASSWORD=pass1\n"
        "JOB104_EMAIL=job@test.com\n"
        "JOB104_PASSWORD=pass2\n"
        "LINKEDIN_EMAIL=linkedin@test.com\n"
        "LINKEDIN_PASSWORD=pass3\n"
        "CLAUDE_API_KEY=sk-ant-test\n"
        "DB_HOST=localhost\n"
        "DB_USER=root\n"
        "DB_PASSWORD=dbpass\n"
        "DB_NAME=autojobber\n"
        "REPORT_EMAIL=report@test.com\n"
        "EMAIL_PASSWORD=emailpass\n"
    )
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))

    from secrets.loader import load_secrets
    result = load_secrets()
    assert result["cakeresume_email"] == "cake@test.com"
    assert result["linkedin_email"] == "linkedin@test.com"
    assert result["linkedin_password"] == "pass3"
    assert result["claude_api_key"] == "sk-ant-test"
    assert result["db_host"] == "localhost"
```

Also update `test_load_secrets_production`'s `secret_data` dict to include `"linkedin_email": "prod@linkedin.com"` and `"linkedin_password": "prodpass3"`, and add `assert result["linkedin_email"] == "prod@linkedin.com"` at the end.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_secrets.py -v`
Expected: FAIL — `KeyError: 'LINKEDIN_EMAIL'` (the loader doesn't read these env vars yet)

- [ ] **Step 3: Write minimal implementation**

In `secrets/loader.py`, update `_load_from_env`:

```python
def _load_from_env() -> dict:
    dotenv_path = os.environ.get("DOTENV_PATH", ".env")
    load_dotenv(dotenv_path=dotenv_path)
    return {
        "cakeresume_email": os.environ["CAKERESUME_EMAIL"],
        "cakeresume_password": os.environ["CAKERESUME_PASSWORD"],
        "job104_email": os.environ["JOB104_EMAIL"],
        "job104_password": os.environ["JOB104_PASSWORD"],
        "linkedin_email": os.environ["LINKEDIN_EMAIL"],
        "linkedin_password": os.environ["LINKEDIN_PASSWORD"],
        "claude_api_key": os.environ["CLAUDE_API_KEY"],
        "db_host": os.environ["DB_HOST"],
        "db_user": os.environ["DB_USER"],
        "db_password": os.environ["DB_PASSWORD"],
        "db_name": os.environ["DB_NAME"],
        "report_email": os.environ["REPORT_EMAIL"],
        "email_password": os.environ["EMAIL_PASSWORD"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_secrets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add secrets/loader.py tests/test_secrets.py
git commit -m "feat: add LinkedIn credentials to secrets loader"
```

---

### Task 2: Add "linkedin" to the JobApplication site enum

**Files:**
- Modify: `db/models.py:15`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `JobApplication(site="linkedin", ...)` is now a valid row, consumed by `main.py`'s existing `session.add(JobApplication(url=url, site=site_name, ...))` call (no change needed there — `site_name` already comes from `config["sites"]`, which Task 8 extends).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:

```python
def test_job_application_accepts_linkedin_site(session):
    app = JobApplication(
        url="https://www.linkedin.com/jobs/view/12345",
        site="linkedin",
        search_term="python developer",
        status="applied",
        applied_at=datetime.datetime(2026, 8, 7, 9, 0, 0),
    )
    session.add(app)
    session.commit()

    saved = session.query(JobApplication).filter_by(url="https://www.linkedin.com/jobs/view/12345").one()
    assert saved.site == "linkedin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_db.py::test_job_application_accepts_linkedin_site -v`
Expected: FAIL — SQLite raises a constraint/`LookupError`-style failure because `"linkedin"` isn't in the enum's allowed values yet (SQLAlchemy's `Enum` validates against its declared set even on SQLite).

- [ ] **Step 3: Write minimal implementation**

In `db/models.py`, change line 15:

```python
    site = Column(SAEnum("cakeresume", "104", "linkedin"), nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: PASS (all tests in the file, to confirm no regression on the existing `"cakeresume"` case)

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_db.py
git commit -m "feat: add linkedin to JobApplication site enum"
```

---

### Task 3: Scaffold LinkedInScraper with session-persistence login

**Files:**
- Create: `scrapers/linkedin.py`
- Test: `tests/test_linkedin.py`

**Interfaces:**
- Consumes: `BaseScraper`, `ApplyResult` from `scrapers/base.py` (unchanged); `human_delay` from `browser/browser.py`.
- Produces: `LinkedInScraper(secrets: dict, ai_screening: bool, claude_api_key: str)` — `secrets` must contain `"linkedin_email"`/`"linkedin_password"` (Task 1). `login(page)`, `collect_links(...)` (stubbed here, real implementation in Task 4), `apply(...)` (stubbed here, real implementation in Tasks 5-7).

- [ ] **Step 1: Write the failing test**

Create `tests/test_linkedin.py`:

```python
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
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    assert any("linkedin.com" in str(c.args[0]) for c in page.goto.call_args_list)


def test_login_fills_credentials_when_no_saved_session(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    scraper = _scraper()
    page = _page()
    scraper.login(page)
    page.fill.assert_any_call("#username", "a@b.com")
    page.fill.assert_any_call("#password", "pass")


def test_login_skips_full_login_when_saved_session_valid(monkeypatch, tmp_path):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.linkedin'`

- [ ] **Step 3: Write minimal implementation**

Create `scrapers/linkedin.py`:

```python
import json
import os
import boto3
from patchright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult

LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL = "https://www.linkedin.com/jobs/"

AUTH_LOCAL = "auth_linkedin.json"
AUTH_ECS = "/tmp/auth_linkedin.json"
AUTH_S3_KEY = "auth_linkedin.json"

MIN_LINKS_PER_RUN = 15
MAX_LINKS_PER_RUN = 25
MAX_CONTINUE_STEPS = 10


def _auth_path() -> str:
    return AUTH_ECS if os.environ.get("ENV") == "production" else AUTH_LOCAL


def _download_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.download_file(os.environ["CONFIG_BUCKET"], AUTH_S3_KEY, AUTH_ECS)
        print("[linkedin] auth file downloaded from S3")
    except Exception:
        pass


def _upload_auth() -> None:
    try:
        s3 = boto3.client("s3")
        s3.upload_file(AUTH_ECS, os.environ["CONFIG_BUCKET"], AUTH_S3_KEY)
        print("[linkedin] auth file uploaded to S3")
    except Exception:
        pass


class LinkedInScraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["linkedin_email"]
        self._password = secrets["linkedin_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        if os.environ.get("ENV") == "production":
            _download_auth()

        auth = _auth_path()
        if os.path.exists(auth):
            with open(auth) as f:
                state = json.load(f)
            page.context.add_cookies(state.get("cookies", []))
            page.goto(JOBS_URL, wait_until="domcontentloaded", timeout=20000)
            if page.get_by_role("link", name="Sign in").count() == 0:
                print("[linkedin] session loaded from auth file — skipping login")
                return
            print("[linkedin] saved session expired — doing full login")

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("#username", timeout=10000)
        human_delay(0.5, 1.0)
        page.fill("#username", self._email)
        page.fill("#password", self._password)
        human_delay(0.3, 0.6)
        page.click('button[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        human_delay(3.0, 5.0)
        logged_in = page.get_by_role("link", name="Sign in").count() == 0
        print(f"[linkedin] login complete — url={page.url!r} logged_in={logged_in}")

        if logged_in:
            page.context.storage_state(path=auth)
            print("[linkedin] auth file saved")
            if os.environ.get("ENV") == "production":
                _upload_auth()

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        return []

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        return ApplyResult(status="skipped", error="not implemented")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add scrapers/linkedin.py tests/test_linkedin.py
git commit -m "feat: scaffold LinkedInScraper with session-persistence login"
```

---

### Task 4: Implement collect_links with randomized per-run cap

**Files:**
- Modify: `scrapers/linkedin.py` (replace the `collect_links` stub from Task 3)
- Test: `tests/test_linkedin.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `collect_links(page, search_term, pages, remote_only) -> list[str]`, deduped job URLs, length capped to a random value in `[MIN_LINKS_PER_RUN, MAX_LINKS_PER_RUN]`. Consumed by `main.py`'s existing loop (Task 8 wires site registration; the loop itself needs no change since it already just calls `scraper.collect_links(...)`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_linkedin.py`:

```python
def test_collect_links_returns_href_list(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.linkedin.com/jobs/view/111222333"
    page.query_selector_all.return_value = [mock_a]

    links = scraper.collect_links(page, "python developer", pages=1, remote_only=True)
    assert isinstance(links, list)
    assert "https://www.linkedin.com/jobs/view/111222333" in links


def test_collect_links_deduplicates(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    mock_a = MagicMock()
    mock_a.get_attribute.return_value = "https://www.linkedin.com/jobs/view/999?refId=abc"
    page.query_selector_all.return_value = [mock_a, mock_a]

    links = scraper.collect_links(page, "python", pages=1, remote_only=True)
    assert links.count("https://www.linkedin.com/jobs/view/999") == 1


def test_collect_links_caps_to_15_25_range(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: `test_collect_links_returns_href_list` and `test_collect_links_deduplicates` FAIL (stub returns `[]`); `test_collect_links_caps_to_15_25_range` FAILS (`0` is not `>= 15`)

- [ ] **Step 3: Write minimal implementation**

In `scrapers/linkedin.py`, add near the top:

```python
import random
import urllib.parse
```

Replace the `collect_links` stub:

```python
    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list:
        links: list = []
        encoded = urllib.parse.quote(search_term)
        remote_param = "&f_WT=2" if remote_only else ""
        for p in range(pages):
            start = p * 25
            url = (
                f"https://www.linkedin.com/jobs/search/?keywords={encoded}"
                f"&f_AL=true{remote_param}&start={start}"
            )
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.5, 3.0)
            anchors = page.query_selector_all('a[href*="/jobs/view/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                full = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                full = full.split("?")[0]
                if full not in links:
                    links.append(full)
        print(f"[linkedin] collected {len(links)} links for {search_term!r}")

        random.shuffle(links)
        capped = links[:random.randint(MIN_LINKS_PER_RUN, MAX_LINKS_PER_RUN)]
        print(f"[linkedin] capped to {len(capped)} links for this run")
        return capped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add scrapers/linkedin.py tests/test_linkedin.py
git commit -m "feat: implement LinkedIn collect_links with randomized 15-25 cap"
```

---

### Task 5: apply() — Easy Apply detection and external-application skip

**Files:**
- Modify: `scrapers/linkedin.py` (replace the `apply` stub from Task 3)
- Test: `tests/test_linkedin.py`

**Interfaces:**
- Produces: `apply(page, url, resume_path, resume_text) -> ApplyResult` — returns `skipped` with `error="no Easy Apply link — external application"` when the job has no Easy Apply link. Later tasks (6, 7) extend this same method body.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_linkedin.py`:

```python
def test_apply_returns_skipped_when_no_easy_apply_link(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper()
    page = _page()
    page.get_by_role.return_value.count.return_value = 0  # no "Easy Apply to this job" link

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "Easy Apply" in result.error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linkedin.py::test_apply_returns_skipped_when_no_easy_apply_link -v`
Expected: FAIL — stub always returns `error="not implemented"`, not the Easy-Apply-specific message.

- [ ] **Step 3: Write minimal implementation**

Replace the `apply` stub in `scrapers/linkedin.py`:

```python
    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)
            print(f"[linkedin] job page — url={page.url!r} title={page.title()!r}")

            easy_apply = page.get_by_role("link", name="Easy Apply to this job")
            if not easy_apply.count():
                return ApplyResult(status="skipped", error="no Easy Apply link — external application")

            easy_apply.click()
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))
```

(The `return ApplyResult(status="applied")` placeholder return after the Easy Apply click is intentionally replaced in Task 6/7 — for this task it only needs to prove the skip path works.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: PASS (all tests, including the new one)

- [ ] **Step 5: Commit**

```bash
git add scrapers/linkedin.py tests/test_linkedin.py
git commit -m "feat: detect Easy Apply link and skip external applications"
```

---

### Task 6: apply() — Continue-loop with screening questions and unrecognized-field skip

**Files:**
- Modify: `scrapers/linkedin.py` (extend `apply`, inserting the step loop between the Easy Apply click and the final `return ApplyResult(status="applied")` from Task 5)
- Test: `tests/test_linkedin.py`

**Interfaces:**
- Consumes: `answer_screening_questions(questions: list[str], resume_text: str, api_key: str) -> list[str]` from `ai/screening.py` (unchanged signature).
- Produces: the loop portion of `apply()` — clicks through "Continue to next step" pages, answers text screening questions, aborts as `skipped` (with `screening_links=[url]`) on any unrecognized field type or when `ai_screening` is off and a question is found.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_linkedin.py`:

```python
def test_apply_answers_text_screening_question_and_continues(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    monkeypatch.setattr(
        "scrapers.linkedin.answer_screening_questions",
        lambda questions, resume_text, api_key: ["5 years"],
    )
    scraper = _scraper(ai_screening=True)
    page = _page()
    page.get_by_role.return_value.count.return_value = 1  # Easy Apply link present

    # First loop pass: one text question, no unrecognized fields, Continue button present.
    # Second pass: no questions, no Continue button — loop exits.
    page.evaluate.side_effect = [
        False,  # unrecognized-field check, pass 1
        ["How many years of work experience do you have with Python?*"],  # questions, pass 1
        False,  # unrecognized-field check, pass 2
        [],  # questions, pass 2
    ]
    continue_calls = {"n": 0}

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        if name == "Continue to next step":
            m.count.return_value = 1 if continue_calls["n"] == 0 else 0
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

    assert continue_calls["n"] == 1
    page.get_by_role.assert_any_call("textbox", name="How many years of work experience do you have with Python?*", exact=True)


def test_apply_returns_skipped_when_unrecognized_field_present(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()

    def get_by_role(role, name=None, **kw):
        m = MagicMock()
        m.count.return_value = 1 if name == "Easy Apply to this job" else 0
        return m

    page.get_by_role.side_effect = get_by_role
    page.evaluate.return_value = True  # unrecognized field (e.g. a dropdown) present

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "https://www.linkedin.com/jobs/view/123" in result.screening_links
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: Both new tests FAIL — `apply()` doesn't call `page.evaluate` or answer questions yet, and always reaches `return ApplyResult(status="applied")` unconditionally after the Easy Apply click.

- [ ] **Step 3: Write minimal implementation**

At the top of `scrapers/linkedin.py`, add the import:

```python
from ai.screening import answer_screening_questions
```

In `scrapers/linkedin.py`, replace the body of `apply()` between the Easy Apply click and the final return with the step loop:

```python
    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)
            print(f"[linkedin] job page — url={page.url!r} title={page.title()!r}")

            easy_apply = page.get_by_role("link", name="Easy Apply to this job")
            if not easy_apply.count():
                return ApplyResult(status="skipped", error="no Easy Apply link — external application")

            easy_apply.click()
            page.wait_for_load_state("domcontentloaded")
            human_delay(1.0, 2.0)

            unrecognized_field_js = """() => {
                const modal = document.querySelector('.jobs-easy-apply-modal') ||
                    document.querySelector('[role="dialog"]');
                if (!modal) return false;
                return !!modal.querySelector(
                    'input[type="radio"], select, input[type="file"], [role="radio"], [role="combobox"], [role="listbox"]'
                );
            }"""
            question_texts_js = """() => {
                const isQuestion = (s) => /\\?\\s*\\**\\s*$/.test(s || '');
                const fields = Array.from(document.querySelectorAll('input[type="text"], input[type="number"], textarea'));
                return fields
                    .map(el => el.getAttribute('aria-label')
                        || (el.labels && el.labels[0] && el.labels[0].innerText)
                        || el.getAttribute('placeholder')
                        || '')
                    .map(s => s.trim())
                    .filter(isQuestion);
            }"""

            for _ in range(MAX_CONTINUE_STEPS):
                if page.evaluate(unrecognized_field_js):
                    page.keyboard.press("Escape")
                    return ApplyResult(status="skipped", screening_links=[url])

                question_texts = page.evaluate(question_texts_js)
                for question_text in question_texts:
                    if not self._ai_screening:
                        return ApplyResult(status="skipped", screening_links=[url])
                    answer = answer_screening_questions([question_text], resume_text, self._claude_api_key)[0]
                    page.get_by_role("textbox", name=question_text, exact=True).fill(answer)
                    human_delay(0.3, 0.8)

                continue_btn = page.get_by_role("button", name="Continue to next step")
                if not continue_btn.count():
                    break
                continue_btn.click()
                page.wait_for_load_state("domcontentloaded")
                human_delay(1.0, 2.0)

            return ApplyResult(status="applied")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add scrapers/linkedin.py tests/test_linkedin.py
git commit -m "feat: handle multi-step Easy Apply forms and text screening questions"
```

---

### Task 7: apply() — Review, Submit, dismiss, and success verification

**Files:**
- Modify: `scrapers/linkedin.py` (replace the `return ApplyResult(status="applied")` at the end of the loop from Task 6 with the real submit/verify sequence)
- Test: `tests/test_linkedin.py`

**Interfaces:**
- Produces: final `apply()` behavior — clicks "Review your application" (if present), "Submit application", best-effort dismisses the post-submit modal, then verifies success via "Application submitted" text before returning `applied`; returns `failed` if that text never appears.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_linkedin.py`:

```python
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
    page.evaluate.side_effect = [False, []]  # one loop pass: no unrecognized field, no questions
    page.get_by_text.return_value.wait_for.side_effect = (
        None if confirmation_count() else Exception("Timeout 8000ms exceeded")
    )


def test_apply_returns_applied_when_confirmation_text_appears(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()
    _apply_stub_for_submit_flow(page, submit_count=lambda: 1, dismiss_count=lambda: 0, confirmation_count=lambda: 1)

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "applied"


def test_apply_returns_failed_when_confirmation_text_never_appears(monkeypatch):
    monkeypatch.setattr("browser.browser.human_delay", lambda *a, **kw: None)
    scraper = _scraper(ai_screening=True)
    page = _page()
    _apply_stub_for_submit_flow(page, submit_count=lambda: 1, dismiss_count=lambda: 0, confirmation_count=lambda: 0)

    result = scraper.apply(page, "https://www.linkedin.com/jobs/view/123", "resume.pdf", "resume text")
    assert result.status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: Both new tests FAIL — `apply()` still returns `applied` unconditionally after the loop, without clicking Submit or checking confirmation text (the second test expects `failed` but gets `applied`).

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `scrapers/linkedin.py`:

```python
import re
```

Replace `return ApplyResult(status="applied")` at the end of the loop in `apply()` (from Task 6) with:

```python
            review_btn = page.get_by_role("button", name="Review your application")
            if review_btn.count():
                review_btn.click()
                human_delay(1.0, 2.0)

            submit_btn = page.get_by_role("button", name="Submit application")
            if not submit_btn.count():
                return ApplyResult(status="skipped", screening_links=[url])
            submit_btn.click()
            human_delay(1.0, 2.0)

            try:
                dismiss_btn = page.get_by_role("button", name=re.compile(r"Dismiss|Not now|Done", re.I))
                dismiss_btn.first.click(timeout=5000)
            except Exception:
                pass

            try:
                page.get_by_text("Application submitted", exact=False).wait_for(timeout=8000)
            except Exception:
                return ApplyResult(status="failed", error="submit click did not register — no confirmation text found")

            return ApplyResult(status="applied")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linkedin.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add scrapers/linkedin.py
git commit -m "feat: submit LinkedIn Easy Apply and verify success via confirmation text"
```

---

### Task 8: Wire LinkedInScraper into main.py and config.example.json

**Files:**
- Modify: `main.py:14-15` (import), `main.py:18-21` (`SCRAPER_MAP`)
- Modify: `config.example.json:9` (`sites` list)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `LinkedInScraper` from `scrapers/linkedin.py` (Tasks 3-7).
- Produces: `main.SCRAPER_MAP["linkedin"]` resolves to `LinkedInScraper`, so adding `"linkedin"` to a deployed `config.json`'s `sites` list is sufficient to enable it — no other `main.py` change needed.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
def test_scraper_map_includes_linkedin():
    from main import SCRAPER_MAP
    from scrapers.linkedin import LinkedInScraper
    assert SCRAPER_MAP["linkedin"] is LinkedInScraper
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_main.py::test_scraper_map_includes_linkedin -v`
Expected: FAIL — `KeyError: 'linkedin'`

- [ ] **Step 3: Write minimal implementation**

In `main.py`, update the imports (line 14-15 area):

```python
from scrapers.cakeresume import CakeResumeScraper
from scrapers.job104 import Job104Scraper
from scrapers.linkedin import LinkedInScraper
```

Update `SCRAPER_MAP`:

```python
SCRAPER_MAP = {
    "cakeresume": CakeResumeScraper,
    "104": Job104Scraper,
    "linkedin": LinkedInScraper,
}
```

In `config.example.json`, update the `sites` line:

```json
  "sites": ["cakeresume", "104", "linkedin"],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: PASS (all tests)

Then run the full suite to confirm no regressions anywhere:

Run: `python3 -m pytest -q`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add main.py config.example.json tests/test_main.py
git commit -m "feat: register LinkedInScraper in SCRAPER_MAP and config.example.json"
```

---

### Task 9: Migrate the production RDS site enum and add LinkedIn secrets

**Files:**
- None (operational/infrastructure step — no code changes; this task updates the live database and Secrets Manager, not the repo)

**Interfaces:**
- Consumes: nothing.
- Produces: the production `job_applications.site` column accepts `'linkedin'`, and the `autojobber/production` Secrets Manager secret has the two new keys `LinkedInScraper.__init__` (Task 3) expects — `linkedin_email`, `linkedin_password`.

**Why this is a separate task:** `db/client.py`'s `init_db()` calls `Base.metadata.create_all(engine)`, which only creates missing tables — it does **not** alter existing columns. Task 2 changed the Python-side `SAEnum` definition, but the live RDS table's `site` column is still physically `ENUM('cakeresume','104')` until this migration runs. Without it, the first LinkedIn `INSERT` in production will fail with a MySQL data-truncation error on that column.

- [ ] **Step 1: Add the new secrets to Secrets Manager**

Run this yourself (it modifies the production secret) — fetch the current secret, merge in the two new keys, and write it back:

```bash
export AWS_PROFILE=personal
export AWS_REGION=us-east-1

CURRENT=$(aws secretsmanager get-secret-value \
  --secret-id autojobber/production \
  --query SecretString --output text)

UPDATED=$(echo "$CURRENT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
d['linkedin_email'] = 'YOUR_LINKEDIN_EMAIL'
d['linkedin_password'] = 'YOUR_LINKEDIN_PASSWORD'
print(json.dumps(d))
")

aws secretsmanager update-secret \
  --secret-id autojobber/production \
  --secret-string "$UPDATED"
```

Replace `YOUR_LINKEDIN_EMAIL`/`YOUR_LINKEDIN_PASSWORD` with the real values before running — don't paste real credentials into a chat session when filling this in.

- [ ] **Step 2: Alter the RDS site enum column**

Run this yourself against the production database (needs `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` from the secret fetched in Step 1, or from your local `.env` if it's already configured for RDS access — see the earlier `update_rds_ip.sh` step to make sure your IP is currently whitelisted on the RDS security group first):

```bash
mysql -h <DB_HOST> -u <DB_USER> -p<DB_PASSWORD> <DB_NAME> -e \
  "ALTER TABLE job_applications MODIFY COLUMN site ENUM('cakeresume','104','linkedin') NOT NULL;"
```

- [ ] **Step 3: Verify the migration**

```bash
mysql -h <DB_HOST> -u <DB_USER> -p<DB_PASSWORD> <DB_NAME> -e \
  "SHOW COLUMNS FROM job_applications LIKE 'site';"
```

Expected output's `Type` column: `enum('cakeresume','104','linkedin')`

No commit needed — this task touches infrastructure only, not the repo.

---

## Self-Review

### Spec coverage

| Spec item | Task |
|---|---|
| Auth — session persistence (104 pattern) | Task 3 |
| collect_links — randomized 15-25 cap, isolated from main.py | Task 4 |
| Easy Apply detection / external-application skip | Task 5 |
| Continue-loop, capped iterations | Task 6 |
| Text screening questions via answer_screening_questions | Task 6 |
| Unrecognized field type (radio/dropdown/file) → skip + flag | Task 6 |
| Review your application (optional step) | Task 7 |
| Submit application + best-effort dismiss | Task 7 |
| Success verification via "Application submitted" text | Task 7 |
| JobApplication.site enum gains "linkedin" | Task 2 |
| LINKEDIN_EMAIL/LINKEDIN_PASSWORD secrets | Task 1 |
| SCRAPER_MAP + config.example.json wiring | Task 8 |
| Production RDS/Secrets Manager migration (implied by spec's config/secrets section, not spelled out as a runtime step there) | Task 9, added during this review |

No gaps found.

### Placeholder scan

No TBD, TODO, "implement later", "similar to Task N", or "add appropriate" patterns. All code steps contain complete implementations. The `collect_links`/`apply` stubs in Task 3 are real, working (if minimal) code, not comments — each is fully replaced by name in a specifically identified later task (4, and 5-7 respectively).

### Type consistency

- `ApplyResult(status=..., error=..., screening_links=[...])` used identically across Tasks 5-7 matches `scrapers/base.py`'s existing dataclass fields — no new fields introduced.
- `answer_screening_questions(questions: list[str], resume_text: str, api_key: str) -> list[str]` called in Task 6 matches `ai/screening.py`'s actual signature exactly.
- `LinkedInScraper(secrets: dict, ai_screening: bool, claude_api_key: str)` constructor signature (Task 3) matches how `SCRAPER_MAP["linkedin"]` gets instantiated in `main.py` (Task 8), identical to the existing `CakeResumeScraper`/`Job104Scraper` construction.
- `secrets["linkedin_email"]`/`secrets["linkedin_password"]` (Task 1's dict keys) match exactly what `LinkedInScraper.__init__` reads (Task 3).

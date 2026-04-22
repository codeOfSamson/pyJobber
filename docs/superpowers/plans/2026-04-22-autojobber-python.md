# AutoJobber Python — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a headless Python bot that runs on AWS ECS Fargate, automatically applies to jobs on CakeResume and 104.com.tw, handles AI-powered screening questions via Claude, stores results in MySQL, and sends a daily email report.

**Architecture:** A single Python process orchestrated by `main.py` — it loads config from S3, fetches credentials from Secrets Manager, runs a Playwright browser session per job site, deduplicates against MySQL before each application attempt, and sends a summary email on completion. Each subsystem (config, secrets, DB, browser, scrapers, AI screening, email) is isolated behind its own module and wired together only in `main.py`.

**Tech Stack:** Python 3.12, Playwright (Chromium), SQLAlchemy 2 + PyMySQL, Anthropic SDK (Claude Haiku), pdfminer.six, boto3, python-dotenv, pytest, pytest-mock

---

## Scope Note

AWS infrastructure (ECS task definition, EventBridge Scheduler rule, ECR push, RDS provisioning, S3 bucket creation, Secrets Manager entries) is **not covered** — those are one-time console/CDK steps done after the code ships. This plan produces a working, locally-testable Python project and a Dockerfile ready to push to ECR.

**Naming note:** The spec names the email module `email/reporter.py`, but `email` is a Python stdlib package. Our reporter uses `from email.mime.text import MIMEText` internally — that import would resolve to the local package instead of stdlib if we named it `email/`. This plan uses `mailer/reporter.py` instead.

---

## File Structure

```
autojobber-py/
├── main.py                    # Entry point — full run orchestration
├── Dockerfile
├── requirements.txt
├── .env.example
├── config.example.json
├── .gitignore
├── config/
│   ├── __init__.py
│   └── loader.py              # Reads config.json from S3 (prod) or local file (dev)
├── secrets/
│   ├── __init__.py
│   └── loader.py              # Reads credentials from Secrets Manager (prod) or .env (dev)
├── db/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy table definitions: job_applications, run_log
│   └── client.py              # Engine creation, session factory, schema init
├── browser/
│   ├── __init__.py
│   └── browser.py             # Playwright: headless Chromium, random user agent, human_delay
├── scrapers/
│   ├── __init__.py
│   ├── base.py                # Abstract BaseScraper + ApplyResult dataclass
│   ├── cakeresume.py          # CakeResume implementation
│   └── job104.py              # 104.com.tw implementation
├── ai/
│   ├── __init__.py
│   └── screening.py           # Claude Haiku — answers screening questions given resume text
├── mailer/
│   ├── __init__.py
│   └── reporter.py            # Builds plain-text report body, formats subject, sends via SMTP
└── tests/
    ├── conftest.py             # Shared fixtures: SQLite in-memory engine, session, sample_config
    ├── test_db.py              # models + client
    ├── test_config.py          # config loader
    ├── test_secrets.py         # secrets loader
    ├── test_browser.py         # browser helpers
    ├── test_base_scraper.py    # ApplyResult + abstract enforcement
    ├── test_screening.py       # Claude screening (mocked anthropic)
    ├── test_reporter.py        # report body builder + subject line
    ├── test_cakeresume.py      # CakeResume scraper (mocked Playwright page)
    ├── test_job104.py          # Job104 scraper (mocked Playwright page)
    └── test_main.py            # orchestrator helpers (get_next_term_index, build_db_url)
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config.example.json`
- Create: `tests/conftest.py`
- Create: `config/__init__.py`, `secrets/__init__.py`, `db/__init__.py`, `browser/__init__.py`, `scrapers/__init__.py`, `ai/__init__.py`, `mailer/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
playwright==1.44.0
sqlalchemy==2.0.30
pymysql==1.1.0
boto3==1.34.0
anthropic==0.28.0
pdfminer.six==20221105
python-dotenv==1.0.1
pytest==8.2.0
pytest-mock==3.14.0
```

- [ ] **Step 2: Create .gitignore**

```
.env
config.json
resume.pdf
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.venv/
```

- [ ] **Step 3: Create .env.example**

```
ENV=local
CAKERESUME_EMAIL=your@email.com
CAKERESUME_PASSWORD=yourpassword
JOB104_EMAIL=your@email.com
JOB104_PASSWORD=yourpassword
CLAUDE_API_KEY=sk-ant-...
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=autojobber
REPORT_EMAIL=your@email.com
EMAIL_PASSWORD=yourapppassword
RESUME_PATH=resume.pdf
```

- [ ] **Step 4: Create config.example.json**

```json
{
  "search_terms": [
    "software engineer",
    "backend developer",
    "python developer",
    "full stack engineer"
  ],
  "pages_per_site": 3,
  "sites": ["cakeresume", "104"],
  "remote_only": true,
  "ai_screening": true,
  "report_email": "your@email.com"
}
```

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture
def sample_config():
    return {
        "search_terms": ["python developer", "backend engineer"],
        "pages_per_site": 2,
        "sites": ["cakeresume", "104"],
        "remote_only": True,
        "ai_screening": True,
        "report_email": "test@example.com",
    }
```

- [ ] **Step 6: Create empty __init__.py files**

```bash
touch config/__init__.py secrets/__init__.py db/__init__.py browser/__init__.py scrapers/__init__.py ai/__init__.py mailer/__init__.py tests/__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected: No errors. Chromium binary downloads successfully.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .gitignore .env.example config.example.json tests/conftest.py config/__init__.py secrets/__init__.py db/__init__.py browser/__init__.py scrapers/__init__.py ai/__init__.py mailer/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding — deps, gitignore, example files, test fixtures"
```

---

## Task 2: DB Models

**Files:**
- Create: `db/models.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import datetime
from db.models import JobApplication, RunLog


def test_job_application_fields(session):
    app = JobApplication(
        url="https://cakeresume.com/jobs/test",
        site="cakeresume",
        search_term="python developer",
        status="applied",
        applied_at=datetime.datetime(2026, 4, 22, 9, 0, 0),
    )
    session.add(app)
    session.commit()

    saved = session.query(JobApplication).filter_by(url="https://cakeresume.com/jobs/test").one()
    assert saved.site == "cakeresume"
    assert saved.status == "applied"
    assert saved.error_message is None
    assert saved.id is not None


def test_run_log_fields(session):
    run = RunLog(
        run_date=datetime.date(2026, 4, 22),
        search_term_used="python developer",
        term_index=1,
        total_applied=10,
        total_failed=2,
        total_skipped=5,
    )
    session.add(run)
    session.commit()

    saved = session.query(RunLog).first()
    assert saved.term_index == 1
    assert saved.total_applied == 10
    assert saved.completed_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db.models'`

- [ ] **Step 3: Create db/models.py**

```python
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, Text, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False)
    site = Column(SAEnum("cakeresume", "104"), nullable=False)
    search_term = Column(String(100))
    status = Column(SAEnum("applied", "failed", "skipped"), nullable=False)
    applied_at = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text)
    job_updated_at = Column(String(100))
    employer_active_at = Column(String(100))


class RunLog(Base):
    __tablename__ = "run_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(Date, nullable=False)
    search_term_used = Column(String(100))
    term_index = Column(Integer)
    total_applied = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_skipped = Column(Integer, default=0)
    completed_at = Column(DateTime)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_db.py
git commit -m "feat: add SQLAlchemy models for job_applications and run_log"
```

---

## Task 3: DB Client

**Files:**
- Create: `db/client.py`
- Modify: `tests/test_db.py` (add two tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
from db.client import get_engine, get_session, init_db


def test_get_engine_creates_tables():
    eng = get_engine("sqlite:///:memory:")
    init_db(eng)
    from sqlalchemy import inspect
    inspector = inspect(eng)
    assert "job_applications" in inspector.get_table_names()
    assert "run_log" in inspector.get_table_names()


def test_get_session_returns_usable_session():
    eng = get_engine("sqlite:///:memory:")
    init_db(eng)
    sess = get_session(eng)
    assert sess is not None
    sess.close()
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_db.py::test_get_engine_creates_tables tests/test_db.py::test_get_session_returns_usable_session -v
```

Expected: `ModuleNotFoundError: No module named 'db.client'`

- [ ] **Step 3: Create db/client.py**

```python
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base


def get_engine(db_url: str):
    return _create_engine(db_url)


def get_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: Run all DB tests**

```bash
pytest tests/test_db.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add db/client.py tests/test_db.py
git commit -m "feat: add DB client — engine factory, session factory, schema init"
```

---

## Task 4: Config Loader

**Files:**
- Create: `config/loader.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import json


def test_load_config_local(tmp_path, monkeypatch):
    cfg = {
        "search_terms": ["python"],
        "pages_per_site": 2,
        "sites": ["cakeresume"],
        "remote_only": True,
        "ai_screening": True,
        "report_email": "a@b.com",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(cfg))
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("CONFIG_PATH", str(config_file))

    from config.loader import load_config
    result = load_config()
    assert result["search_terms"] == ["python"]
    assert result["pages_per_site"] == 2


def test_load_config_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("CONFIG_BUCKET", "my-bucket")
    monkeypatch.setenv("CONFIG_KEY", "config.json")

    cfg = {
        "search_terms": ["engineer"],
        "pages_per_site": 3,
        "sites": ["104"],
        "remote_only": False,
        "ai_screening": False,
        "report_email": "x@y.com",
    }

    from unittest.mock import MagicMock
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: json.dumps(cfg).encode())}
    monkeypatch.setattr("boto3.client", lambda service: mock_s3)

    import importlib
    import config.loader
    importlib.reload(config.loader)
    from config.loader import load_config
    result = load_config()
    assert result["search_terms"] == ["engineer"]
    assert result["pages_per_site"] == 3
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config.loader'`

- [ ] **Step 3: Create config/loader.py**

```python
import json
import os
import boto3


def load_config() -> dict:
    if os.environ.get("ENV") == "production":
        return _load_from_s3()
    return _load_local()


def _load_from_s3() -> dict:
    bucket = os.environ["CONFIG_BUCKET"]
    key = os.environ.get("CONFIG_KEY", "config.json")
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def _load_local() -> dict:
    path = os.environ.get("CONFIG_PATH", "config.json")
    with open(path) as f:
        return json.load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add config/loader.py tests/test_config.py
git commit -m "feat: add config loader — local file and S3 modes"
```

---

## Task 5: Secrets Loader

**Files:**
- Create: `secrets/loader.py`
- Create: `tests/test_secrets.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_secrets.py
import json


def test_load_secrets_local(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAKERESUME_EMAIL=cake@test.com\n"
        "CAKERESUME_PASSWORD=pass1\n"
        "JOB104_EMAIL=job@test.com\n"
        "JOB104_PASSWORD=pass2\n"
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
    assert result["claude_api_key"] == "sk-ant-test"
    assert result["db_host"] == "localhost"


def test_load_secrets_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_NAME", "autojobber/prod")

    secret_data = {
        "cakeresume_email": "prod@cake.com",
        "cakeresume_password": "prodpass",
        "job104_email": "prod@104.com",
        "job104_password": "prodpass2",
        "claude_api_key": "sk-ant-prod",
        "db_host": "rds.endpoint",
        "db_user": "admin",
        "db_password": "rdspass",
        "db_name": "autojobber",
        "report_email": "prod@report.com",
        "email_password": "prodEmailPass",
    }
    from unittest.mock import MagicMock
    mock_sm = MagicMock()
    mock_sm.get_secret_value.return_value = {"SecretString": json.dumps(secret_data)}
    monkeypatch.setattr("boto3.client", lambda service: mock_sm)

    import importlib
    import secrets.loader
    importlib.reload(secrets.loader)
    from secrets.loader import load_secrets
    result = load_secrets()
    assert result["cakeresume_email"] == "prod@cake.com"
    assert result["db_host"] == "rds.endpoint"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_secrets.py -v
```

Expected: `ModuleNotFoundError: No module named 'secrets.loader'`

- [ ] **Step 3: Create secrets/loader.py**

```python
import os
import json
import boto3
from dotenv import load_dotenv


def load_secrets() -> dict:
    if os.environ.get("ENV") == "production":
        return _load_from_secrets_manager()
    return _load_from_env()


def _load_from_env() -> dict:
    dotenv_path = os.environ.get("DOTENV_PATH", ".env")
    load_dotenv(dotenv_path=dotenv_path)
    return {
        "cakeresume_email": os.environ["CAKERESUME_EMAIL"],
        "cakeresume_password": os.environ["CAKERESUME_PASSWORD"],
        "job104_email": os.environ["JOB104_EMAIL"],
        "job104_password": os.environ["JOB104_PASSWORD"],
        "claude_api_key": os.environ["CLAUDE_API_KEY"],
        "db_host": os.environ["DB_HOST"],
        "db_user": os.environ["DB_USER"],
        "db_password": os.environ["DB_PASSWORD"],
        "db_name": os.environ["DB_NAME"],
        "report_email": os.environ["REPORT_EMAIL"],
        "email_password": os.environ["EMAIL_PASSWORD"],
    }


def _load_from_secrets_manager() -> dict:
    secret_name = os.environ["SECRET_NAME"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_secrets.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add secrets/loader.py tests/test_secrets.py
git commit -m "feat: add secrets loader — .env and Secrets Manager modes"
```

---

## Task 6: Browser Setup

**Files:**
- Create: `browser/browser.py`
- Create: `tests/test_browser.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser.py
import time
from browser.browser import human_delay, USER_AGENTS


def test_user_agents_not_empty():
    assert len(USER_AGENTS) >= 2
    for ua in USER_AGENTS:
        assert "Mozilla" in ua


def test_human_delay_sleeps_within_range():
    start = time.time()
    human_delay(0.01, 0.02)
    elapsed = time.time() - start
    assert 0.01 <= elapsed < 0.5
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_browser.py -v
```

Expected: `ModuleNotFoundError: No module named 'browser.browser'`

- [ ] **Step 3: Create browser/browser.py**

```python
import random
import time
from playwright.sync_api import Browser, BrowserContext, Page

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def create_browser(playwright) -> Browser:
    return playwright.chromium.launch(headless=True)


def create_page(browser: Browser) -> Page:
    context: BrowserContext = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
    )
    return context.new_page()


def human_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_browser.py -v
```

Expected: `2 passed`

`create_browser` and `create_page` require a live Playwright runtime and are not unit-tested here — they get exercised during manual end-to-end testing after Task 12.

- [ ] **Step 5: Commit**

```bash
git add browser/browser.py tests/test_browser.py
git commit -m "feat: add Playwright browser factory with random user agent and human delay"
```

---

## Task 7: Base Scraper + ApplyResult

**Files:**
- Create: `scrapers/base.py`
- Create: `tests/test_base_scraper.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_base_scraper.py
import pytest
from scrapers.base import ApplyResult, BaseScraper


def test_apply_result_defaults():
    result = ApplyResult(status="applied")
    assert result.error is None
    assert result.job_updated_at is None
    assert result.employer_active_at is None
    assert result.screening_links == []


def test_apply_result_with_error():
    result = ApplyResult(status="failed", error="Timeout")
    assert result.status == "failed"
    assert result.error == "Timeout"


def test_apply_result_with_screening_links():
    result = ApplyResult(status="skipped", screening_links=["https://example.com/job/1"])
    assert len(result.screening_links) == 1
    assert result.screening_links[0] == "https://example.com/job/1"


def test_base_scraper_is_abstract():
    with pytest.raises(TypeError):
        BaseScraper()
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_base_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrapers.base'`

- [ ] **Step 3: Create scrapers/base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ApplyResult:
    status: str  # "applied" | "failed" | "skipped"
    error: str | None = None
    job_updated_at: str | None = None
    employer_active_at: str | None = None
    screening_links: list[str] = field(default_factory=list)


class BaseScraper(ABC):
    @abstractmethod
    def login(self, page) -> None: ...

    @abstractmethod
    def collect_links(self, page, search_term: str, pages: int, remote_only: bool) -> list[str]: ...

    @abstractmethod
    def apply(self, page, url: str, resume_path: str, resume_text: str) -> ApplyResult: ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_base_scraper.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add scrapers/base.py tests/test_base_scraper.py
git commit -m "feat: add BaseScraper interface and ApplyResult dataclass"
```

---

## Task 8: AI Screening

**Files:**
- Create: `ai/screening.py`
- Create: `tests/test_screening.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_screening.py
from unittest.mock import MagicMock, patch


def _mock_client(answer_text: str):
    mock_content = MagicMock()
    mock_content.text = answer_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_instance = MagicMock()
    mock_instance.messages.create.return_value = mock_response
    return mock_instance


def test_returns_one_answer_per_question():
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value = _mock_client("I have 5 years of Python experience.")
        from ai.screening import answer_screening_questions
        answers = answer_screening_questions(
            ["How many years of Python?", "Available full-time?"],
            "Resume text here.",
            "sk-ant-test",
        )
    assert len(answers) == 2
    assert answers[0] == "I have 5 years of Python experience."
    assert answers[1] == "I have 5 years of Python experience."


def test_uses_haiku_model():
    with patch("anthropic.Anthropic") as MockClient:
        mock_instance = _mock_client("Yes.")
        MockClient.return_value = mock_instance
        from ai.screening import answer_screening_questions
        answer_screening_questions(["Question?"], "Resume.", "sk-ant-test")
        call_kwargs = mock_instance.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


def test_empty_questions_returns_empty_list():
    with patch("anthropic.Anthropic"):
        from ai.screening import answer_screening_questions
        result = answer_screening_questions([], "Resume text.", "sk-ant-test")
    assert result == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_screening.py -v
```

Expected: `ModuleNotFoundError: No module named 'ai.screening'`

- [ ] **Step 3: Create ai/screening.py**

```python
import anthropic


def answer_screening_questions(questions: list[str], resume_text: str, api_key: str) -> list[str]:
    if not questions:
        return []
    client = anthropic.Anthropic(api_key=api_key)
    answers = []
    for question in questions:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    "You are filling out a job application screening question. "
                    "Answer concisely and professionally based on this resume:\n\n"
                    f"{resume_text}\n\n"
                    f"Question: {question}"
                ),
            }],
        )
        answers.append(response.content[0].text)
    return answers
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_screening.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ai/screening.py tests/test_screening.py
git commit -m "feat: add Claude Haiku screening question answerer"
```

---

## Task 9: Email Reporter

**Files:**
- Create: `mailer/reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_reporter.py -v
```

Expected: `ModuleNotFoundError: No module named 'mailer.reporter'`

- [ ] **Step 3: Create mailer/reporter.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_reporter.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add mailer/reporter.py tests/test_reporter.py
git commit -m "feat: add email reporter — report body builder and SMTP sender"
```

---

## Task 10: CakeResume Scraper

**Files:**
- Create: `scrapers/cakeresume.py`
- Create: `tests/test_cakeresume.py`

**Selector note:** Selectors in this task are based on CakeResume's DOM as of 2026-04. After implementation, run against the live site (`ENV=local python -c "..."`) and tune selectors if the page structure has changed.

- [ ] **Step 1: Write the failing tests**

```python
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
    apply_btn = MagicMock()
    question_el = MagicMock()
    question_el.get_attribute.return_value = "How many years of experience?"

    def query_selector_side_effect(sel):
        if "apply" in sel.lower() or "Apply" in sel:
            return apply_btn
        return None

    page.query_selector.side_effect = query_selector_side_effect
    page.query_selector_all.return_value = [question_el]

    result = scraper.apply(page, "https://www.cakeresume.com/jobs/xyz", "resume.pdf", "resume text")
    assert result.status == "skipped"
    assert "https://www.cakeresume.com/jobs/xyz" in result.screening_links
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_cakeresume.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrapers.cakeresume'`

- [ ] **Step 3: Create scrapers/cakeresume.py**

```python
from playwright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.cakeresume.com/users/sign_in"
SEARCH_URL = "https://www.cakeresume.com/jobs?q={term}&remote=true&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.cakeresume.com/jobs?q={term}&page={page}"


class CakeResumeScraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["cakeresume_email"]
        self._password = secrets["cakeresume_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        page.goto(LOGIN_URL)
        page.wait_for_selector('[name="email"]')
        page.fill('[name="email"]', self._email)
        page.fill('[name="password"]', self._password)
        page.click('[type="submit"]')
        page.wait_for_load_state("networkidle")
        human_delay(1.5, 3.0)

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list[str]:
        links: list[str] = []
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=search_term.replace(" ", "+"), page=p)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.5)
            anchors = page.query_selector_all('a[href*="/jobs/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/jobs/" in href and not href.endswith("/jobs/"):
                    full = href if href.startswith("http") else f"https://www.cakeresume.com{href}"
                    if full not in links:
                        links.append(full)
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            apply_btn = page.query_selector('button:has-text("Apply"), a:has-text("Apply now")')
            if not apply_btn:
                return ApplyResult(status="skipped")

            apply_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            question_els = page.query_selector_all('textarea[name*="question"], input[name*="question"]')
            if question_els and self._ai_screening:
                questions = [el.get_attribute("placeholder") or "" for el in question_els]
                answers = answer_screening_questions(questions, resume_text, self._claude_api_key)
                for el, answer in zip(question_els, answers):
                    el.fill(answer)
                    human_delay(0.3, 0.8)
            elif question_els and not self._ai_screening:
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn = page.query_selector('button[type="submit"]:has-text("Submit"), button:has-text("Send application")')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle")
                human_delay(1.0, 2.0)
                return ApplyResult(status="applied")

            return ApplyResult(status="skipped")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cakeresume.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add scrapers/cakeresume.py tests/test_cakeresume.py
git commit -m "feat: add CakeResume scraper — login, collect links, apply with AI screening"
```

---

## Task 11: Job104 Scraper

**Files:**
- Create: `scrapers/job104.py`
- Create: `tests/test_job104.py`

**Selector note:** 104.com.tw is a Traditional Chinese job platform. The apply button text is "我要應徵" (I want to apply). Selectors are based on known DOM patterns as of 2026-04 — tune against the live site after implementation.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_job104.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrapers.job104'`

- [ ] **Step 3: Create scrapers/job104.py**

```python
import urllib.parse
from playwright.sync_api import Page
from browser.browser import human_delay
from scrapers.base import BaseScraper, ApplyResult
from ai.screening import answer_screening_questions

LOGIN_URL = "https://www.104.com.tw/user/login"
SEARCH_URL = "https://www.104.com.tw/jobs/search/?keyword={term}&remoteWork=1&page={page}"
SEARCH_URL_NO_REMOTE = "https://www.104.com.tw/jobs/search/?keyword={term}&page={page}"


class Job104Scraper(BaseScraper):
    def __init__(self, secrets: dict, ai_screening: bool, claude_api_key: str):
        self._email = secrets["job104_email"]
        self._password = secrets["job104_password"]
        self._ai_screening = ai_screening
        self._claude_api_key = claude_api_key

    def login(self, page: Page) -> None:
        page.goto(LOGIN_URL)
        page.wait_for_selector('[name="id"]', timeout=10000)
        page.fill('[name="id"]', self._email)
        page.fill('[name="passwd"]', self._password)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        human_delay(2.0, 4.0)

    def collect_links(self, page: Page, search_term: str, pages: int, remote_only: bool) -> list[str]:
        links: list[str] = []
        encoded = urllib.parse.quote(search_term)
        url_template = SEARCH_URL if remote_only else SEARCH_URL_NO_REMOTE
        for p in range(1, pages + 1):
            url = url_template.format(term=encoded, page=p)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.5, 3.0)
            anchors = page.query_selector_all('a[href*="/job/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/job/" in href:
                    full = href if href.startswith("http") else f"https://www.104.com.tw{href}"
                    full = full.split("?")[0]
                    if full not in links:
                        links.append(full)
        return links

    def apply(self, page: Page, url: str, resume_path: str, resume_text: str) -> ApplyResult:
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            apply_btn = page.query_selector('a.btn-apply, button.btn-apply, a:has-text("我要應徵")')
            if not apply_btn:
                return ApplyResult(status="skipped")

            apply_btn.click()
            page.wait_for_load_state("networkidle")
            human_delay(1.0, 2.0)

            question_els = page.query_selector_all('textarea.apply-question, input.apply-question')
            if question_els and self._ai_screening:
                questions = [el.get_attribute("placeholder") or "" for el in question_els]
                answers = answer_screening_questions(questions, resume_text, self._claude_api_key)
                for el, answer in zip(question_els, answers):
                    el.fill(answer)
                    human_delay(0.3, 0.8)
            elif question_els and not self._ai_screening:
                return ApplyResult(status="skipped", screening_links=[url])

            submit_btn = page.query_selector('button[type="submit"].btn-submit, button:has-text("送出")')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle")
                human_delay(1.0, 2.0)
                return ApplyResult(status="applied")

            return ApplyResult(status="skipped")

        except Exception as e:
            return ApplyResult(status="failed", error=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_job104.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add scrapers/job104.py tests/test_job104.py
git commit -m "feat: add 104.com.tw scraper — login, collect links, apply with AI screening"
```

---

## Task 12: Main Orchestrator

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create main.py**

```python
import datetime
import os
import boto3
from playwright.sync_api import sync_playwright
from pdfminer.high_level import extract_text

from config.loader import load_config
from secrets.loader import load_secrets
from db.client import get_engine, get_session, init_db
from db.models import JobApplication, RunLog
from browser.browser import create_browser, create_page
from scrapers.cakeresume import CakeResumeScraper
from scrapers.job104 import Job104Scraper
from mailer.reporter import build_report, build_subject, send_report

SCRAPER_MAP = {
    "cakeresume": CakeResumeScraper,
    "104": Job104Scraper,
}


def get_next_term_index(session, num_terms: int) -> int:
    last_run = session.query(RunLog).order_by(RunLog.id.desc()).first()
    if last_run is None:
        return 0
    return (last_run.term_index + 1) % num_terms


def build_db_url(secrets: dict) -> str:
    return (
        f"mysql+pymysql://{secrets['db_user']}:{secrets['db_password']}"
        f"@{secrets['db_host']}/{secrets['db_name']}"
    )


def _get_resume_path() -> str:
    if os.environ.get("ENV") == "production":
        local_path = "/tmp/resume.pdf"
        s3 = boto3.client("s3")
        s3.download_file(
            Bucket=os.environ["CONFIG_BUCKET"],
            Key="resume.pdf",
            Filename=local_path,
        )
        return local_path
    return os.environ.get("RESUME_PATH", "resume.pdf")


def main() -> None:
    config = load_config()
    secrets = load_secrets()

    engine = get_engine(build_db_url(secrets))
    init_db(engine)
    session = get_session(engine)

    term_index = get_next_term_index(session, len(config["search_terms"]))
    search_term = config["search_terms"][term_index]

    resume_path = _get_resume_path()
    resume_text = extract_text(resume_path)

    started_at = datetime.datetime.now()
    total_applied = total_failed = total_skipped = 0
    failed_urls: list[tuple[str, str]] = []
    screening_urls: list[str] = []

    with sync_playwright() as playwright:
        for site_name in config["sites"]:
            scraper = SCRAPER_MAP[site_name](
                secrets=secrets,
                ai_screening=config["ai_screening"],
                claude_api_key=secrets["claude_api_key"],
            )
            browser = create_browser(playwright)
            page = create_page(browser)
            try:
                scraper.login(page)
                links = scraper.collect_links(
                    page, search_term, config["pages_per_site"], config["remote_only"]
                )
                for url in links:
                    if session.query(JobApplication).filter_by(url=url).first():
                        total_skipped += 1
                        continue

                    result = scraper.apply(page, url, resume_path, resume_text)
                    session.add(JobApplication(
                        url=url,
                        site=site_name,
                        search_term=search_term,
                        status=result.status,
                        applied_at=datetime.datetime.now(),
                        error_message=result.error,
                        job_updated_at=result.job_updated_at,
                        employer_active_at=result.employer_active_at,
                    ))
                    session.commit()

                    if result.status == "applied":
                        total_applied += 1
                    elif result.status == "failed":
                        total_failed += 1
                        failed_urls.append((url, result.error or "Unknown error"))
                    else:
                        total_skipped += 1

                    screening_urls.extend(result.screening_links)
            finally:
                browser.close()

    completed_at = datetime.datetime.now()
    session.add(RunLog(
        run_date=started_at.date(),
        search_term_used=search_term,
        term_index=term_index,
        total_applied=total_applied,
        total_failed=total_failed,
        total_skipped=total_skipped,
        completed_at=completed_at,
    ))
    session.commit()
    session.close()

    body = build_report(
        search_term=search_term,
        sites=config["sites"],
        pages_per_site=config["pages_per_site"],
        started_at=started_at,
        completed_at=completed_at,
        total_applied=total_applied,
        total_failed=total_failed,
        total_skipped=total_skipped,
        failed_urls=failed_urls,
        screening_urls=screening_urls,
    )
    send_report(
        body=body,
        subject=build_subject(started_at.strftime("%Y-%m-%d"), config["sites"], search_term),
        from_email=secrets["report_email"],
        to_email=config["report_email"],
        password=secrets["email_password"],
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the main tests**

```bash
pytest tests/test_main.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass. No failures.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add main orchestrator — full run loop with round-robin search terms"
```

---

## Task 13: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

ENV ENV=production

CMD ["python", "main.py"]
```

- [ ] **Step 2: Build the image**

```bash
docker build -t autojobber:local .
```

Expected: Build completes with no errors.

- [ ] **Step 3: Verify imports are clean inside the container**

```bash
docker run --rm autojobber:local python -c "from main import main; print('imports ok')"
```

Expected: `imports ok`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile — Python 3.12 slim with Playwright Chromium"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task |
|---|---|
| ECS Fargate execution | Dockerfile (Task 13) |
| EventBridge trigger | Out of scope (infra) |
| Load config from S3 | Task 4 |
| Fetch secrets from Secrets Manager | Task 5 |
| Round-robin search term from run_log | Task 12 (`get_next_term_index`) |
| Playwright browser per site | Tasks 6, 12 |
| Login to CakeResume | Task 10 |
| Login to 104.com.tw | Task 11 |
| Search with remote filter | Tasks 10, 11 (`collect_links`) |
| Deduplication via DB before applying | Task 12 (main loop) |
| Apply to each job | Tasks 10, 11 (`apply`) |
| AI screening via Claude Haiku | Task 8, Tasks 10, 11 |
| `ai_screening: false` → skip + add to report | Tasks 10, 11 |
| Save result to job_applications | Task 12 |
| Write run summary to run_log | Task 12 |
| job_applications schema | Task 2 |
| run_log schema | Task 2 |
| S3 config format | Tasks 1, 4 |
| Local dev ENV switch | Tasks 4, 5, 12 |
| Resume PDF from S3 in prod | Task 12 (`_get_resume_path`) |
| pdfminer for resume text | Task 12 |
| Email report body format | Task 9 |
| Email subject format | Task 9 |
| Failed/screening sections omitted when empty | Task 9 |
| SMTP send via Gmail | Task 9 (`send_report`) |
| CloudWatch Logs | Implicit — stdout/stderr captured automatically by ECS |
| RDS MySQL | Tasks 2, 3 (SQLAlchemy, PyMySQL) |
| S3 resume + config | Tasks 4, 12 |
| ECR | Out of scope (push step after Docker build) |

No gaps found.

### Placeholder scan

No TBD, TODO, "implement later", "similar to Task N", or "add appropriate" patterns. All code steps contain complete implementations.

### Type consistency

- `ApplyResult` fields (`status`, `error`, `job_updated_at`, `employer_active_at`, `screening_links`) defined in Task 7, referenced identically in Tasks 10, 11, 12.
- `secrets` dict keys (`cakeresume_email`, `cakeresume_password`, `job104_email`, `job104_password`, `claude_api_key`, `db_host`, `db_user`, `db_password`, `db_name`, `report_email`, `email_password`) defined in Task 5, used with the same names in Tasks 10, 11, 12.
- `CakeResumeScraper(secrets, ai_screening, claude_api_key)` and `Job104Scraper(secrets, ai_screening, claude_api_key)` — constructor signatures match `SCRAPER_MAP` instantiation in Task 12.
- `build_report(...)` and `build_subject(...)` signatures in Task 9 match call sites in Task 12.
- `get_next_term_index(session, num_terms)` and `build_db_url(secrets)` defined and tested in Task 12 consistently.

# Job Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only FastAPI backend (exposing `job_applications`/`run_log` and an ECS run-trigger) and a React + Tailwind + react95 frontend dashboard, on top of the existing autojobber-py scraper/DB codebase.

**Architecture:** A new `api/` package (FastAPI) reuses `db/models.py`/`db/client.py` directly and is layered into `schemas/` (Pydantic I/O models) → `services/` (business logic) → `routers/` (thin HTTP glue), with a `get_current_user()` dependency stub designed so real auth can be added later without touching routers. A new `frontend/` Vite+React+TS app renders three react95 "windows" (Stats, Applications, Run Now) styled with Tailwind for layout. Both run locally via two terminals (`uvicorn` + `npm run dev`); nothing here changes how scrapers or ECS deploys work today.

**Tech Stack:** FastAPI, uvicorn, httpx (test client), existing SQLAlchemy/pymysql; React + TypeScript + Vite, Tailwind CSS, react95 + styled-components, recharts.

**Note on scope:** this plan covers two loosely-coupled subsystems (backend API, frontend UI) rather than being split into two separate plans, because the approved spec (`docs/superpowers/specs/2026-08-11-job-dashboard-design.md`) treats them as one feature. Tasks 1–5 (backend) produce a fully working, independently-testable FastAPI service via `pytest` before any frontend code exists. Tasks 6–9 (frontend) build against that running service.

## Global Constraints

- **No authentication in this version** — `get_current_user()` in `api/dependencies.py` is a stub every route depends on, so auth can be added later by changing only that function (per spec's SOLID section).
- **No migration framework** — the existing `job_applications` table in production RDS needs a manual `ALTER TABLE` (given to the developer in Task 2, never run automatically).
- **No frontend test framework** — frontend tasks are verified manually (`npm run dev` + browser), not with automated tests.
- **No run-status polling** — `POST /api/runs` returns once the ECS task is started; watching it to completion is unchanged (`aws logs tail`).
- **Python 3.9 compatibility** — the developer's local machine runs Python 3.9 (confirmed via `python3 --version` earlier in this project). Do not use `X | None` union-type syntax (that's Python 3.10+ and previously broke this exact codebase in `mailer/reporter.py`); use `typing.Optional`/`typing.List` instead, matching existing repo convention.
- **Existing test fixtures** — `tests/conftest.py` already provides `engine`/`session` fixtures (in-memory SQLite via `Base.metadata.create_all`). Reuse them for all new backend tests rather than building a separate test-DB setup.

---

### Task 1: FastAPI app skeleton + DB/user dependencies

**Files:**
- Create: `api/__init__.py` (empty)
- Create: `api/dependencies.py`
- Create: `api/main.py`
- Create: `tests/test_api.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `api.dependencies.get_db()` (FastAPI dependency yielding a SQLAlchemy `Session`), `api.dependencies.get_current_user()` (FastAPI dependency, returns `{"user": "local"}` — the auth stub every later router depends on), `api.main.app` (the `FastAPI` instance later tasks register routers onto).

- [ ] **Step 1: Add new Python dependencies**

Append to `requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.30.1
httpx==0.27.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_api.py`:
```python
from fastapi.testclient import TestClient
from api.main import app


def test_health_check():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api'`

- [ ] **Step 4: Create the `api` package and dependencies module**

Create `api/__init__.py` (empty file).

Create `api/dependencies.py`:
```python
from functools import lru_cache

from db.client import get_engine, get_session, init_db
from main import build_db_url
from secrets.loader import load_secrets


@lru_cache
def _get_engine():
    creds = load_secrets()
    engine = get_engine(build_db_url(creds))
    init_db(engine)
    return engine


def get_db():
    session = get_session(_get_engine())
    try:
        yield session
    finally:
        session.close()


def get_current_user():
    """Auth stub. Every route depends on this so real auth can be added
    later by changing only this function's body."""
    return {"user": "local"}
```

- [ ] **Step 5: Create the FastAPI app**

Create `api/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Autojobber Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt api/__init__.py api/dependencies.py api/main.py tests/test_api.py
git commit -m "feat: add FastAPI app skeleton with db/auth dependency stubs"
```

---

### Task 2: `needs_review`/`reviewed` columns + main.py wiring

**Files:**
- Modify: `db/models.py`
- Modify: `main.py`
- Modify: `tests/test_db.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `JobApplication.needs_review: bool`, `JobApplication.reviewed: bool` (used by Task 3's `ApplicationService`); `main._needs_review(result: ApplyResult) -> bool` (pure helper, not consumed elsewhere but documents the rule Task 3 relies on: a row has `needs_review=True` iff its `ApplyResult.screening_links` was non-empty).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_db.py`:
```python
def test_job_application_review_flags_default_false(session):
    app = JobApplication(
        url="https://cakeresume.com/jobs/review-test",
        site="cakeresume",
        search_term="python developer",
        status="skipped",
        applied_at=datetime.datetime(2026, 8, 11, 9, 0, 0),
    )
    session.add(app)
    session.commit()

    saved = session.query(JobApplication).filter_by(url="https://cakeresume.com/jobs/review-test").one()
    assert saved.needs_review is False
    assert saved.reviewed is False
```

Add to `tests/test_main.py`:
```python
from scrapers.base import ApplyResult
from main import _needs_review


def test_needs_review_true_when_screening_links_present():
    result = ApplyResult(status="skipped", screening_links=["https://example.com/job/1"])
    assert _needs_review(result) is True


def test_needs_review_false_when_no_screening_links():
    result = ApplyResult(status="applied")
    assert _needs_review(result) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py tests/test_main.py -v`
Expected: FAIL — `AttributeError: 'JobApplication' object has no attribute 'needs_review'` and `ImportError: cannot import name '_needs_review'`

- [ ] **Step 3: Add the columns**

In `db/models.py`, change the import line:
```python
from sqlalchemy import Column, Integer, String, DateTime, Date, Text, Boolean, Enum as SAEnum
```

Add to `JobApplication` (after `employer_active_at`):
```python
    needs_review = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)
```

- [ ] **Step 4: Add the helper and wire it into `main.py`**

In `main.py`, add near the other module-level functions (after `build_db_url`):
```python
def _needs_review(result) -> bool:
    return bool(result.screening_links)
```

In the apply loop, update the `JobApplication(...)` construction to include the new field:
```python
                    session.add(JobApplication(
                        url=url,
                        site=site_name,
                        search_term=search_term,
                        status=result.status,
                        applied_at=datetime.datetime.now(),
                        error_message=result.error,
                        job_updated_at=result.job_updated_at,
                        employer_active_at=result.employer_active_at,
                        needs_review=_needs_review(result),
                    ))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py tests/test_main.py -v`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all passing (this touches shared model/main code, so verify nothing else broke)

- [ ] **Step 7: Commit**

```bash
git add db/models.py main.py tests/test_db.py tests/test_main.py
git commit -m "feat: add needs_review/reviewed columns, set needs_review from screening_links"
```

- [ ] **Step 8: Hand the developer the production migration command (do not run it yourself)**

Tell the developer: the production RDS table was created before these columns existed, and this project has no migration framework (`init_db()` only calls `create_all()`, which never alters existing tables). Before deploying this change, they need to run, against production:
```sql
ALTER TABLE job_applications
  ADD COLUMN needs_review BOOLEAN DEFAULT FALSE,
  ADD COLUMN reviewed BOOLEAN DEFAULT FALSE;
```

---

### Task 3: Applications API (list + mark reviewed)

**Files:**
- Create: `api/schemas/__init__.py` (empty)
- Create: `api/schemas/applications.py`
- Create: `api/services/__init__.py` (empty)
- Create: `api/services/application_service.py`
- Create: `api/routers/__init__.py` (empty)
- Create: `api/routers/applications.py`
- Modify: `api/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `api.dependencies.get_db`, `api.dependencies.get_current_user` (Task 1); `db.models.JobApplication` with `needs_review`/`reviewed` (Task 2).
- Produces: `ApplicationService(session).list_filtered(site=None, status=None, reviewed=None, needs_review=None) -> List[JobApplication]`, `ApplicationService(session).mark_reviewed(application_id: int, reviewed: bool) -> Optional[JobApplication]` — used only within this task's router, but the names/shapes are the contract for `GET /api/applications` and `PATCH /api/applications/{id}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:
```python
import datetime

import pytest

from api.dependencies import get_db
from db.models import JobApplication


@pytest.fixture
def client(session):
    def _override_get_db():
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_applications_empty(client):
    response = client.get("/api/applications")
    assert response.status_code == 200
    assert response.json() == []


def test_list_applications_filters_by_site(client, session):
    session.add(JobApplication(
        url="https://www.cakeresume.com/jobs/a", site="cakeresume", status="applied",
        applied_at=datetime.datetime(2026, 8, 11, 9, 0, 0),
    ))
    session.add(JobApplication(
        url="https://www.104.com.tw/job/b", site="104", status="skipped",
        applied_at=datetime.datetime(2026, 8, 11, 9, 5, 0), needs_review=True,
    ))
    session.commit()

    response = client.get("/api/applications", params={"site": "104"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["site"] == "104"
    assert body[0]["needs_review"] is True


def test_update_application_marks_reviewed(client, session):
    row = JobApplication(
        url="https://www.cakeresume.com/jobs/c", site="cakeresume", status="skipped",
        applied_at=datetime.datetime(2026, 8, 11, 9, 0, 0), needs_review=True,
    )
    session.add(row)
    session.commit()

    response = client.patch(f"/api/applications/{row.id}", json={"reviewed": True})
    assert response.status_code == 200
    assert response.json()["reviewed"] is True


def test_update_application_404_for_missing_id(client):
    response = client.patch("/api/applications/9999", json={"reviewed": True})
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: FAIL — `404 Not Found` for the new routes (they don't exist yet) / fixture errors

- [ ] **Step 3: Write the schemas**

Create `api/schemas/__init__.py` (empty file).

Create `api/schemas/applications.py`:
```python
import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    site: str
    search_term: Optional[str] = None
    status: str
    applied_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    job_updated_at: Optional[str] = None
    employer_active_at: Optional[str] = None
    needs_review: bool
    reviewed: bool


class ApplicationUpdate(BaseModel):
    reviewed: bool
```

- [ ] **Step 4: Write the service**

Create `api/services/__init__.py` (empty file).

Create `api/services/application_service.py`:
```python
from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import JobApplication


class ApplicationService:
    def __init__(self, session: Session):
        self._session = session

    def list_filtered(
        self,
        site: Optional[str] = None,
        status: Optional[str] = None,
        reviewed: Optional[bool] = None,
        needs_review: Optional[bool] = None,
    ) -> List[JobApplication]:
        query = self._session.query(JobApplication)
        if site is not None:
            query = query.filter(JobApplication.site == site)
        if status is not None:
            query = query.filter(JobApplication.status == status)
        if reviewed is not None:
            query = query.filter(JobApplication.reviewed == reviewed)
        if needs_review is not None:
            query = query.filter(JobApplication.needs_review == needs_review)
        return query.order_by(JobApplication.id.desc()).all()

    def mark_reviewed(self, application_id: int, reviewed: bool) -> Optional[JobApplication]:
        app = self._session.get(JobApplication, application_id)
        if app is None:
            return None
        app.reviewed = reviewed
        self._session.commit()
        self._session.refresh(app)
        return app
```

- [ ] **Step 5: Write the router**

Create `api/routers/__init__.py` (empty file).

Create `api/routers/applications.py`:
```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.schemas.applications import ApplicationOut, ApplicationUpdate
from api.services.application_service import ApplicationService

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    site: Optional[str] = None,
    status: Optional[str] = None,
    reviewed: Optional[bool] = None,
    needs_review: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ApplicationService(db)
    return service.list_filtered(site=site, status=status, reviewed=reviewed, needs_review=needs_review)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ApplicationService(db)
    updated = service.mark_reviewed(application_id, payload.reviewed)
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated
```

- [ ] **Step 6: Register the router**

In `api/main.py`, add:
```python
from api.routers import applications

app.include_router(applications.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/schemas api/services api/routers api/main.py tests/test_api.py
git commit -m "feat: add applications API (list + mark reviewed)"
```

---

### Task 4: Stats API

**Files:**
- Create: `api/schemas/stats.py`
- Create: `api/services/stats_service.py`
- Create: `api/routers/stats.py`
- Modify: `api/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `api.dependencies.get_db`, `api.dependencies.get_current_user` (Task 1); `db.models.RunLog` (existing).
- Produces: `StatsService(session).get_run_stats() -> List[RunLog]` — contract for `GET /api/stats`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:
```python
from db.models import RunLog


def test_get_stats_returns_run_log_entries(client, session):
    session.add(RunLog(
        run_date=datetime.date(2026, 8, 10), search_term_used="python developer",
        term_index=0, total_applied=5, total_failed=1, total_skipped=3,
    ))
    session.add(RunLog(
        run_date=datetime.date(2026, 8, 11), search_term_used="backend engineer",
        term_index=1, total_applied=2, total_failed=0, total_skipped=6,
    ))
    session.commit()

    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["run_date"] == "2026-08-10"
    assert body[1]["total_skipped"] == 6
```

(Add `import datetime` at the top of `tests/test_api.py` if not already present from Task 3.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: FAIL — `404 Not Found`

- [ ] **Step 3: Write the schema**

Create `api/schemas/stats.py`:
```python
import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RunStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_date: datetime.date
    search_term_used: Optional[str] = None
    total_applied: int
    total_failed: int
    total_skipped: int
```

- [ ] **Step 4: Write the service**

Create `api/services/stats_service.py`:
```python
from typing import List

from sqlalchemy.orm import Session

from db.models import RunLog


class StatsService:
    def __init__(self, session: Session):
        self._session = session

    def get_run_stats(self) -> List[RunLog]:
        return self._session.query(RunLog).order_by(RunLog.run_date.asc()).all()
```

- [ ] **Step 5: Write the router**

Create `api/routers/stats.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.schemas.stats import RunStatOut
from api.services.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=list[RunStatOut])
def get_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    service = StatsService(db)
    return service.get_run_stats()
```

- [ ] **Step 6: Register the router**

In `api/main.py`, add:
```python
from api.routers import stats

app.include_router(stats.router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/schemas/stats.py api/services/stats_service.py api/routers/stats.py api/main.py tests/test_api.py
git commit -m "feat: add stats API"
```

---

### Task 5: Run-trigger API (ECS) + main.py overrides

**Files:**
- Create: `api/cluster_runner.py`
- Create: `api/schemas/runs.py`
- Create: `api/services/run_service.py`
- Create: `api/routers/runs.py`
- Create: `tests/test_cluster_runner.py`
- Modify: `api/dependencies.py`
- Modify: `api/main.py`
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `deploy/.deploy_vars`-style env vars `SUBNET_ID`/`ECS_SG_ID` (developer must have these exported locally, same values used by `deploy/run_task.sh`); `api.dependencies.get_current_user`.
- Produces: `ClusterRunner().trigger(sites: Optional[List[str]] = None, search_term: Optional[str] = None) -> str` (task ARN); `main._resolve_sites(config: dict) -> list[str]` and `main._resolve_search_term(config: dict, term_index: int) -> str` (read `SITES_OVERRIDE`/`SEARCH_TERM_OVERRIDE` env vars, falling back to `config`) — this is how a triggered ECS task actually picks up the overrides `POST /api/runs` sends.

- [ ] **Step 1: Write the failing tests for `main.py` overrides**

Add to `tests/test_main.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_sites'`

- [ ] **Step 3: Implement the overrides in `main.py`**

Add near `_needs_review` (Task 2):
```python
def _resolve_sites(config: dict) -> list[str]:
    override = os.environ.get("SITES_OVERRIDE")
    if override:
        return [s.strip() for s in override.split(",") if s.strip()]
    return config["sites"]


def _resolve_search_term(config: dict, term_index: int) -> str:
    override = os.environ.get("SEARCH_TERM_OVERRIDE")
    if override:
        return override
    return config["search_terms"][term_index]
```

In `main()`, replace:
```python
    term_index = get_next_term_index(session, len(config["search_terms"]))
    search_term = config["search_terms"][term_index]
```
with:
```python
    term_index = get_next_term_index(session, len(config["search_terms"]))
    search_term = _resolve_search_term(config, term_index)
    sites = _resolve_sites(config)
```

Replace `for site_name in config["sites"]:` with `for site_name in sites:`.

In the `build_report(...)` call, replace `sites=config["sites"],` with `sites=sites,`.

- [ ] **Step 4: Run tests to verify they pass, then run the full suite**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: PASS

Run: `python3 -m pytest -q`
Expected: all passing

- [ ] **Step 5: Commit the main.py overrides**

```bash
git add main.py tests/test_main.py
git commit -m "feat: support SITES_OVERRIDE/SEARCH_TERM_OVERRIDE env vars in main.py"
```

- [ ] **Step 6: Write the failing tests for `ClusterRunner`**

Create `tests/test_cluster_runner.py`:
```python
from api.cluster_runner import ClusterRunner


def test_trigger_calls_run_task_with_expected_params(mocker, monkeypatch):
    monkeypatch.setenv("SUBNET_ID", "subnet-123")
    monkeypatch.setenv("ECS_SG_ID", "sg-456")
    fake_client = mocker.Mock()
    fake_client.run_task.return_value = {"tasks": [{"taskArn": "arn:aws:ecs:fake"}]}
    mocker.patch("boto3.client", return_value=fake_client)

    runner = ClusterRunner()
    task_arn = runner.trigger()

    assert task_arn == "arn:aws:ecs:fake"
    kwargs = fake_client.run_task.call_args.kwargs
    assert kwargs["cluster"] == "autojobber"
    assert kwargs["taskDefinition"] == "autojobber"
    assert kwargs["networkConfiguration"]["awsvpcConfiguration"]["subnets"] == ["subnet-123"]
    assert "overrides" not in kwargs


def test_trigger_adds_container_overrides_for_sites_and_search_term(mocker, monkeypatch):
    monkeypatch.setenv("SUBNET_ID", "subnet-123")
    monkeypatch.setenv("ECS_SG_ID", "sg-456")
    fake_client = mocker.Mock()
    fake_client.run_task.return_value = {"tasks": [{"taskArn": "arn:aws:ecs:fake"}]}
    mocker.patch("boto3.client", return_value=fake_client)

    runner = ClusterRunner()
    runner.trigger(sites=["cakeresume", "linkedin"], search_term="rust developer")

    kwargs = fake_client.run_task.call_args.kwargs
    env = kwargs["overrides"]["containerOverrides"][0]["environment"]
    assert {"name": "SITES_OVERRIDE", "value": "cakeresume,linkedin"} in env
    assert {"name": "SEARCH_TERM_OVERRIDE", "value": "rust developer"} in env
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cluster_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.cluster_runner'`

- [ ] **Step 8: Implement `ClusterRunner`**

Create `api/cluster_runner.py`:
```python
import os
from typing import List, Optional

import boto3


class ClusterRunner:
    def __init__(
        self,
        cluster: str = "autojobber",
        task_definition: str = "autojobber",
        container_name: str = "autojobber",
        region: str = "us-east-1",
    ):
        self._cluster = cluster
        self._task_definition = task_definition
        self._container_name = container_name
        self._region = region

    def trigger(self, sites: Optional[List[str]] = None, search_term: Optional[str] = None) -> str:
        subnet_id = os.environ["SUBNET_ID"]
        sg_id = os.environ["ECS_SG_ID"]

        env_overrides = []
        if sites:
            env_overrides.append({"name": "SITES_OVERRIDE", "value": ",".join(sites)})
        if search_term:
            env_overrides.append({"name": "SEARCH_TERM_OVERRIDE", "value": search_term})

        kwargs = {
            "cluster": self._cluster,
            "taskDefinition": self._task_definition,
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": [subnet_id],
                    "securityGroups": [sg_id],
                    "assignPublicIp": "ENABLED",
                }
            },
        }
        if env_overrides:
            kwargs["overrides"] = {
                "containerOverrides": [{"name": self._container_name, "environment": env_overrides}]
            }

        client = boto3.client("ecs", region_name=self._region)
        response = client.run_task(**kwargs)
        return response["tasks"][0]["taskArn"]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cluster_runner.py -v`
Expected: PASS

- [ ] **Step 10: Write the failing tests for the runs router**

Add to `tests/test_api.py`:
```python
from botocore.exceptions import ClientError

from api.dependencies import get_cluster_runner


def test_trigger_run_returns_task_arn(client):
    class FakeClusterRunner:
        def trigger(self, sites=None, search_term=None):
            return "arn:aws:ecs:us-east-1:123:task/autojobber/fake123"

    app.dependency_overrides[get_cluster_runner] = lambda: FakeClusterRunner()
    try:
        response = client.post("/api/runs", json={})
        assert response.status_code == 200
        assert response.json()["task_arn"] == "arn:aws:ecs:us-east-1:123:task/autojobber/fake123"
    finally:
        del app.dependency_overrides[get_cluster_runner]


def test_trigger_run_returns_502_on_aws_error(client):
    class FailingClusterRunner:
        def trigger(self, sites=None, search_term=None):
            raise ClientError(
                {"Error": {"Code": "InvalidParameterException", "Message": "bad subnet"}}, "RunTask"
            )

    app.dependency_overrides[get_cluster_runner] = lambda: FailingClusterRunner()
    try:
        response = client.post("/api/runs", json={"sites": ["linkedin"]})
        assert response.status_code == 502
    finally:
        del app.dependency_overrides[get_cluster_runner]
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_cluster_runner'`

- [ ] **Step 12: Add `get_cluster_runner` dependency**

In `api/dependencies.py`, add the import near the top (alongside the existing `from functools import lru_cache` from Task 1):
```python
from api.cluster_runner import ClusterRunner
```

And add the function anywhere after `_get_engine`:
```python
@lru_cache
def get_cluster_runner() -> ClusterRunner:
    return ClusterRunner()
```

- [ ] **Step 13: Write the schema, service, and router**

Create `api/schemas/runs.py`:
```python
from typing import List, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    sites: Optional[List[str]] = None
    search_term: Optional[str] = None


class RunResponse(BaseModel):
    task_arn: str
```

Create `api/services/run_service.py`:
```python
from typing import List, Optional

from api.cluster_runner import ClusterRunner


class RunService:
    def __init__(self, cluster_runner: ClusterRunner):
        self._cluster_runner = cluster_runner

    def trigger(self, sites: Optional[List[str]], search_term: Optional[str]) -> str:
        return self._cluster_runner.trigger(sites=sites, search_term=search_term)
```

Create `api/routers/runs.py`:
```python
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException

from api.cluster_runner import ClusterRunner
from api.dependencies import get_cluster_runner, get_current_user
from api.schemas.runs import RunRequest, RunResponse
from api.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunResponse)
def trigger_run(
    payload: RunRequest,
    cluster_runner: ClusterRunner = Depends(get_cluster_runner),
    user=Depends(get_current_user),
):
    service = RunService(cluster_runner)
    try:
        task_arn = service.trigger(sites=payload.sites, search_term=payload.search_term)
    except ClientError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return RunResponse(task_arn=task_arn)
```

- [ ] **Step 14: Register the router**

In `api/main.py`, add:
```python
from api.routers import runs

app.include_router(runs.router)
```

- [ ] **Step 15: Run tests to verify they pass, then run the full suite**

Run: `python3 -m pytest tests/test_api.py -v`
Expected: PASS

Run: `python3 -m pytest -q`
Expected: all passing

- [ ] **Step 16: Commit**

```bash
git add api/cluster_runner.py api/schemas/runs.py api/services/run_service.py api/routers/runs.py api/dependencies.py api/main.py tests/test_cluster_runner.py tests/test_api.py
git commit -m "feat: add ECS run-trigger API"
```

This completes the backend. The developer can now run `uvicorn api.main:app --reload --port 8000` (with `SUBNET_ID`/`ECS_SG_ID` exported, and DB secrets available via `.env`) and hit `/api/health`, `/api/applications`, `/api/stats`, `/api/runs` directly.

---

### Task 6: Scaffold the frontend (Vite + React + Tailwind + react95)

**Files:**
- Create: `frontend/` (Vite-generated React+TS project)
- Modify: `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/src/index.css`
- Create: `frontend/.env`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: a running `npm run dev` app at `http://localhost:5173` showing a single react95 `Window`, proving Tailwind + react95 + styled-components are wired together correctly before any real feature code is written.

- [ ] **Step 1: Scaffold the Vite project**

Run from the repo root:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install Tailwind, react95, and recharts**

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install react95 styled-components recharts
```

- [ ] **Step 3: Configure Tailwind**

Edit `frontend/tailwind.config.js` so `content` matches Vite's file layout:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

Replace the contents of `frontend/src/index.css` with:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: Set the API base URL**

Create `frontend/.env`:
```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 5: Wire up react95's theme and confirm the stack renders**

Replace `frontend/src/App.tsx`:
```tsx
import { ThemeProvider } from "styled-components";
import original from "react95/dist/themes/original";
import "react95/dist/App.css";
import { Window, WindowHeader, WindowContent } from "react95";

function App() {
  return (
    <ThemeProvider theme={original}>
      <div className="min-h-screen bg-teal-700 flex items-center justify-center p-8">
        <Window>
          <WindowHeader>Autojobber Dashboard</WindowHeader>
          <WindowContent>Scaffold OK.</WindowContent>
        </Window>
      </div>
    </ThemeProvider>
  );
}

export default App;
```

**Note for the implementer:** react95's theme/CSS import paths (`react95/dist/themes/original`, `react95/dist/App.css`) and exported component names (`Window`, `WindowHeader`, `WindowContent`) are accurate as of react95's documented API, but third-party packages evolve — if `npm run dev` errors on an import, check `node_modules/react95/dist/` (or the package's README/ CHANGELOG) for the current export paths and adjust. This is the one place in this plan where the exact import surface depends on whatever version npm resolves.

- [ ] **Step 6: Manually verify**

Run: `npm run dev` (from `frontend/`)
Expected: opening `http://localhost:5173` shows a beveled Win95-style window titled "Autojobber Dashboard" containing "Scaffold OK." on a teal background.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat: scaffold frontend (Vite + React + Tailwind + react95)"
```

---

### Task 7: Stats window (chart)

**Files:**
- Create: `frontend/src/api.ts`
- Create: `frontend/src/windows/StatsWindow.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/stats` (Task 4) — array of `{run_date, search_term_used, total_applied, total_failed, total_skipped}`.
- Produces: `fetchStats(): Promise<RunStat[]>` in `api.ts`, reused by no one else in this plan but establishes the fetch pattern Tasks 8–9 follow; `<StatsWindow />` component, mounted in `App.tsx`.

- [ ] **Step 1: Write the API client**

Create `frontend/src/api.ts`:
```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export interface RunStat {
  run_date: string;
  search_term_used: string | null;
  total_applied: number;
  total_failed: number;
  total_skipped: number;
}

export async function fetchStats(): Promise<RunStat[]> {
  const response = await fetch(`${API_BASE_URL}/api/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch stats: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Write the Stats window**

Create `frontend/src/windows/StatsWindow.tsx`:
```tsx
import { useEffect, useState } from "react";
import { Window, WindowHeader, WindowContent } from "react95";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchStats, RunStat } from "../api";

export function StatsWindow() {
  const [stats, setStats] = useState<RunStat[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <Window className="w-full">
      <WindowHeader>Applications Over Time</WindowHeader>
      <WindowContent>
        {error && <p>API unreachable — is `uvicorn` running? ({error})</p>}
        {!error && (
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={stats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="run_date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total_applied" stroke="#2e7d32" name="Applied" />
                <Line type="monotone" dataKey="total_failed" stroke="#c62828" name="Failed" />
                <Line type="monotone" dataKey="total_skipped" stroke="#f9a825" name="Skipped" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </WindowContent>
    </Window>
  );
}
```

- [ ] **Step 3: Mount it in `App.tsx`**

Replace `frontend/src/App.tsx`:
```tsx
import { ThemeProvider } from "styled-components";
import original from "react95/dist/themes/original";
import "react95/dist/App.css";
import { StatsWindow } from "./windows/StatsWindow";

function App() {
  return (
    <ThemeProvider theme={original}>
      <div className="min-h-screen bg-teal-700 p-8 flex flex-col gap-6">
        <StatsWindow />
      </div>
    </ThemeProvider>
  );
}

export default App;
```

- [ ] **Step 4: Manually verify**

With the backend running (`uvicorn api.main:app --reload --port 8000` from the repo root, in a separate terminal) and at least one `RunLog` row in the DB, run `npm run dev` and confirm the chart renders with real data. If the DB is empty, confirm the chart area renders without crashing (empty data set).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/windows/StatsWindow.tsx frontend/src/App.tsx
git commit -m "feat: add stats chart window"
```

---

### Task 8: Applications window (table, filters, review toggle)

**Files:**
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/windows/ApplicationsWindow.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/applications?site=&status=&needs_review=` and `PATCH /api/applications/{id}` (Task 3).
- Produces: `fetchApplications(filters)`, `updateApplicationReviewed(id, reviewed)` in `api.ts`; `<ApplicationsWindow />`, mounted in `App.tsx` alongside `StatsWindow`.

**Note:** the spec's prose mentions a "date range" filter, but the spec's own API endpoint table never defines a date param — only `site`/`status`/`reviewed`/`needs_review`. This task implements site + status + needs-review filters (everything the API actually supports) and intentionally omits date-range, since adding it would mean inventing an API contract the approved spec didn't define.

- [ ] **Step 1: Extend the API client**

Add to `frontend/src/api.ts`:
```ts
export interface Application {
  id: number;
  url: string;
  site: string;
  search_term: string | null;
  status: string;
  applied_at: string | null;
  error_message: string | null;
  needs_review: boolean;
  reviewed: boolean;
}

export interface ApplicationFilters {
  site?: string;
  status?: string;
  needs_review?: boolean;
}

export async function fetchApplications(filters: ApplicationFilters = {}): Promise<Application[]> {
  const params = new URLSearchParams();
  if (filters.site) params.set("site", filters.site);
  if (filters.status) params.set("status", filters.status);
  if (filters.needs_review !== undefined) params.set("needs_review", String(filters.needs_review));

  const response = await fetch(`${API_BASE_URL}/api/applications?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch applications: ${response.status}`);
  }
  return response.json();
}

export async function updateApplicationReviewed(id: number, reviewed: boolean): Promise<Application> {
  const response = await fetch(`${API_BASE_URL}/api/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewed }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update application: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Write the Applications window**

Create `frontend/src/windows/ApplicationsWindow.tsx`:
```tsx
import { useEffect, useState } from "react";
import { Checkbox, Select, Window, WindowContent, WindowHeader } from "react95";
import {
  Application,
  fetchApplications,
  updateApplicationReviewed,
} from "../api";

const SITE_OPTIONS = [
  { value: "", label: "All sites" },
  { value: "cakeresume", label: "CakeResume" },
  { value: "104", label: "104.com.tw" },
  { value: "linkedin", label: "LinkedIn" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "applied", label: "Applied" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

export function ApplicationsWindow() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [site, setSite] = useState("");
  const [status, setStatus] = useState("");
  const [onlyNeedsReview, setOnlyNeedsReview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchApplications({
      site: site || undefined,
      status: status || undefined,
      needs_review: onlyNeedsReview ? true : undefined,
    })
      .then(setApplications)
      .catch((e) => setError(e.message));
  };

  useEffect(load, [site, status, onlyNeedsReview]);

  const toggleReviewed = async (app: Application) => {
    const updated = await updateApplicationReviewed(app.id, !app.reviewed);
    setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };

  return (
    <Window className="w-full">
      <WindowHeader>Applications</WindowHeader>
      <WindowContent>
        {error && <p>API unreachable — is `uvicorn` running? ({error})</p>}

        <div className="flex items-center gap-4 mb-4">
          <Select
            options={SITE_OPTIONS}
            value={site}
            onChange={(option) => setSite(option.value as string)}
            width={180}
          />
          <Select
            options={STATUS_OPTIONS}
            value={status}
            onChange={(option) => setStatus(option.value as string)}
            width={180}
          />
          <Checkbox
            checked={onlyNeedsReview}
            onChange={(e) => setOnlyNeedsReview(e.target.checked)}
            label="Needs review only"
          />
        </div>

        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th>Site</th>
              <th>Status</th>
              <th>URL</th>
              <th>Reviewed</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((app) => (
              <tr key={app.id}>
                <td>{app.site}</td>
                <td>{app.status}</td>
                <td className="truncate max-w-xs">
                  <a href={app.url} target="_blank" rel="noreferrer">
                    {app.url}
                  </a>
                </td>
                <td>
                  <Checkbox checked={app.reviewed} onChange={() => toggleReviewed(app)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </WindowContent>
    </Window>
  );
}
```

**Note for the implementer:** react95's `Select` prop names (`options`, `onChange` receiving an option object) match its documented API as of this writing; if the installed version differs, adjust to whatever shape `npm run dev`'s type errors indicate — the filtering/rendering logic above doesn't depend on the exact prop names.

- [ ] **Step 3: Mount it in `App.tsx`**

In `frontend/src/App.tsx`, add the import and render it below `<StatsWindow />`:
```tsx
import { ApplicationsWindow } from "./windows/ApplicationsWindow";
```
```tsx
        <StatsWindow />
        <ApplicationsWindow />
```

- [ ] **Step 4: Manually verify**

With the backend running and some `job_applications` rows in the DB (including at least one with `needs_review=True`), confirm: the table lists rows, the site filter narrows results, "Needs review only" filters correctly, and clicking a row's checkbox persists (`PATCH` succeeds) and stays checked after a page reload.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/windows/ApplicationsWindow.tsx frontend/src/App.tsx
git commit -m "feat: add applications table window with review toggle"
```

---

### Task 9: Run Now window (with confirmation) + final wiring

**Files:**
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/windows/RunNowWindow.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `POST /api/runs` (Task 5).
- Produces: `triggerRun(sites, searchTerm)` in `api.ts`; `<RunNowWindow />`, mounted as the final piece in `App.tsx`.

- [ ] **Step 1: Extend the API client**

Add to `frontend/src/api.ts`:
```ts
export async function triggerRun(sites: string[], searchTerm: string): Promise<{ task_arn: string }> {
  const response = await fetch(`${API_BASE_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sites: sites.length > 0 ? sites : undefined,
      search_term: searchTerm || undefined,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Failed to trigger run: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Write the Run Now window**

Create `frontend/src/windows/RunNowWindow.tsx`:
```tsx
import { useState } from "react";
import { Button, Checkbox, TextInput, Window, WindowContent, WindowHeader } from "react95";
import { triggerRun } from "../api";

const ALL_SITES = ["cakeresume", "104", "linkedin"];

export function RunNowWindow() {
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleSite = (site: string) => {
    setSelectedSites((prev) =>
      prev.includes(site) ? prev.filter((s) => s !== site) : [...prev, site]
    );
  };

  const confirmAndRun = async () => {
    setShowConfirm(false);
    setError(null);
    setResult(null);
    try {
      const { task_arn } = await triggerRun(selectedSites, searchTerm);
      setResult(task_arn);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Window className="w-full">
      <WindowHeader>Run Now</WindowHeader>
      <WindowContent>
        <div className="flex gap-4 mb-4">
          {ALL_SITES.map((site) => (
            <Checkbox
              key={site}
              label={site}
              checked={selectedSites.includes(site)}
              onChange={() => toggleSite(site)}
            />
          ))}
        </div>
        <TextInput
          placeholder="Search term override (optional)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
        />
        <Button className="mt-4" onClick={() => setShowConfirm(true)}>
          Run Now
        </Button>

        {result && <p className="mt-4">Task started: {result}</p>}
        {error && <p className="mt-4">Failed to start run: {error}</p>}
      </WindowContent>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Window>
            <WindowHeader>Confirm</WindowHeader>
            <WindowContent>
              <p>
                This submits real applications to real employers on{" "}
                {selectedSites.length > 0 ? selectedSites.join(", ") : "the default configured sites"}.
              </p>
              <div className="flex gap-4 mt-4">
                <Button onClick={confirmAndRun}>Yes, run it</Button>
                <Button onClick={() => setShowConfirm(false)}>Cancel</Button>
              </div>
            </WindowContent>
          </Window>
        </div>
      )}
    </Window>
  );
}
```

- [ ] **Step 3: Mount it in `App.tsx`**

Final `frontend/src/App.tsx`:
```tsx
import { ThemeProvider } from "styled-components";
import original from "react95/dist/themes/original";
import "react95/dist/App.css";
import { StatsWindow } from "./windows/StatsWindow";
import { ApplicationsWindow } from "./windows/ApplicationsWindow";
import { RunNowWindow } from "./windows/RunNowWindow";

function App() {
  return (
    <ThemeProvider theme={original}>
      <div className="min-h-screen bg-teal-700 p-8 flex flex-col gap-6">
        <StatsWindow />
        <ApplicationsWindow />
        <RunNowWindow />
      </div>
    </ThemeProvider>
  );
}

export default App;
```

- [ ] **Step 4: Manually verify end-to-end**

With `uvicorn api.main:app --reload --port 8000` running (and `SUBNET_ID`/`ECS_SG_ID` exported in that terminal), and `npm run dev` running in `frontend/`:
1. Confirm all three windows render with real data from the DB.
2. Click "Run Now" without confirming — verify no request is sent (check the backend terminal logs no request).
3. Click "Run Now", confirm in the dialog, and verify a real ECS task starts (check `aws ecs list-tasks --cluster autojobber`) and the task ARN displays in the window.
4. Toggle a "reviewed" checkbox in the Applications window and refresh the page — verify it stayed checked (persisted to the DB).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/windows/RunNowWindow.tsx frontend/src/App.tsx
git commit -m "feat: add run-now window with confirmation dialog"
```

# Job Dashboard — Design Spec

**Date:** 2026-08-11
**Status:** Approved

---

## Goal

Add a local-only full-stack dashboard on top of the existing scraper/DB backend: a FastAPI service exposing the `job_applications` / `run_log` data (and a way to trigger a run), and a React + Tailwind + react95 frontend to view it. Purpose is explicitly to round out the project with real full-stack surface area (API layer, DB writes from a UI, a triggered cloud action), not just a read-only report viewer.

No changes to how scrapers, cron, or ECS deploys work today — this is a new, additive layer that reads/writes the same RDS database and can call the same ECS task the deploy scripts already use.

---

## Non-Goals (this version)

- **No authentication.** Both services are local-only, bound to `localhost`, run manually on the developer's laptop. Never deployed or exposed to the internet in this version.
- **No migration framework.** The project has no Alembic/migration tooling today; this spec adds one manual `ALTER TABLE` instead of introducing one.
- **No frontend test suite.** Backend gets tests matching existing pytest conventions; the React app is manually verified only, matching the project's current scope.
- **No run-status polling / live log streaming** from the triggered ECS task. "Run Now" fires the task and confirms it started; watching it to completion is still done via `aws logs tail`, same as today.

---

## Architecture

```
autojobber-py/
├── api/                     # new — FastAPI service
│   ├── main.py              # app factory, router registration
│   ├── dependencies.py      # get_db(), get_current_user() (see SOLID section)
│   ├── schemas/              # Pydantic request/response models
│   │   ├── applications.py
│   │   ├── stats.py
│   │   └── runs.py
│   ├── services/              # business logic, no HTTP/FastAPI imports
│   │   ├── application_service.py
│   │   ├── stats_service.py
│   │   └── run_service.py     # wraps ClusterRunner (ECS)
│   ├── cluster_runner.py     # thin boto3 ecs.run_task wrapper, injected into RunService
│   └── routers/
│       ├── applications.py
│       ├── stats.py
│       └── runs.py
├── frontend/                 # new — Vite + React + Tailwind + react95
│   ├── src/
│   │   ├── windows/
│   │   │   ├── StatsWindow.tsx
│   │   │   ├── ApplicationsWindow.tsx
│   │   │   └── RunNowWindow.tsx
│   │   ├── api.ts             # fetch wrapper for the FastAPI service
│   │   └── App.tsx
│   └── ...
├── db/                        # existing — reused as-is
├── scrapers/                  # existing — unchanged
├── main.py                    # existing — small edit: sets needs_review on JobApplication insert
└── ...                        # everything else — unchanged
```

The API imports `db/models.py` and `db/client.py` directly — no duplicate DB layer. `RunService` builds the same `run-task` call `deploy/run_task.sh` does (cluster `autojobber`, task-def `autojobber`, network config from `SUBNET_ID`/`ECS_SG_ID`), reading those two values from environment variables the developer sets locally (sourced from `deploy/.deploy_vars`, same values, not duplicated by hand).

---

## Code Organization — SOLID, with auth specifically in mind

The layering exists mainly so that **adding auth later touches one function, not every route:**

- **`api/dependencies.py`** defines `get_current_user()` as a FastAPI `Depends()` provider. In this version it's a no-op that always returns a placeholder identity. Every route takes it as a parameter from day one:
  ```python
  @router.get("/applications")
  def list_applications(filters: ApplicationFilters = Depends(), user=Depends(get_current_user)):
      ...
  ```
  Adding real auth later means rewriting the *inside* of `get_current_user()` (validate a token, look up a session) — zero router or service code changes. This is the concrete Dependency Inversion / Open-Closed payoff the dashboard is designed around.
- **`api/schemas/`** — Pydantic models, independent of `db/models.py`'s SQLAlchemy models. The DB schema and the API contract can change independently.
- **`api/services/`** — one class per resource, holding the actual logic (`ApplicationService.list_filtered(...)`, `ApplicationService.mark_reviewed(...)`, `RunService.trigger(...)`). Each has a single reason to change. Routers stay thin: parse request → call service → return response.
- **`api/cluster_runner.py`** — `ClusterRunner` wraps the boto3 `ecs.run_task` call behind a small interface (`trigger(sites, search_term_override) -> task_arn`). `RunService` depends on this abstraction, not on `boto3` directly, so tests mock `ClusterRunner` and any future change to how runs are triggered (e.g. swapping ECS for something else) touches one class.

---

## Data Model Change

Add two columns to `JobApplication` in `db/models.py`:

```python
needs_review = Column(Boolean, default=False)
reviewed = Column(Boolean, default=False)
```

`main.py`'s apply loop sets `needs_review=True` when `ApplyResult.screening_links` is non-empty (the same signal that currently only feeds the email's "Screening Questions" section — that section stays as-is, this just also persists the flag). `reviewed` is toggled from the frontend and never set by the scraper.

Because `init_db()` uses `Base.metadata.create_all()` (no migrations), the existing production RDS table needs a one-time manual migration before this ships:

```sql
ALTER TABLE job_applications
  ADD COLUMN needs_review BOOLEAN DEFAULT FALSE,
  ADD COLUMN reviewed BOOLEAN DEFAULT FALSE;
```

This will be handed to the developer to run when we implement — not run automatically.

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/applications?site=&status=&reviewed=&needs_review=` | Filterable list of `job_applications` rows |
| `PATCH` | `/api/applications/{id}` | Body `{"reviewed": true}` — toggle reviewed state |
| `GET` | `/api/stats` | Aggregated `run_log` rows: applied/failed/skipped per run, for the chart |
| `POST` | `/api/runs` | Body `{"sites": [...], "search_term": "..."}` (both optional, default to `config.json`'s values) — triggers an ECS `RunTask`, returns the task ARN |

All responses are JSON; errors return `{"detail": "..."}` with a 4xx/5xx status, following FastAPI's default error shape (no custom error envelope needed).

---

## Frontend

Three react95 "windows" on a single page (Tailwind handles page-level layout/spacing between them; react95 components render the Win95 chrome — title bars, beveled panels, buttons — inside each window):

- **Stats window** — a recharts line chart (applied/failed/skipped over time), fed by `GET /api/stats`.
- **Applications window** — filterable table (site, status, date range) fed by `GET /api/applications`, with a "Needs Review" filter toggle and a checkbox per row wired to `PATCH /api/applications/{id}`.
- **Run Now window** — site checkboxes + optional search-term override, a "Run Now" button, and a react95 modal dialog that requires explicit confirmation before the `POST /api/runs` call fires — this triggers real applications to real employers, so it must never fire on a single click.

---

## Error Handling

- **API → DB errors** (e.g. connection lost): FastAPI returns 500 with `{"detail": "..."}`; the frontend shows a react95 error dialog rather than failing silently.
- **`POST /api/runs` → ECS errors** (e.g. bad network config, AWS credentials missing/expired): `ClusterRunner` lets the boto3 exception propagate up to a router-level handler that returns a 502 with the underlying error message, surfaced verbatim in the confirmation dialog's failure state so the developer can see exactly what AWS rejected.
- **Frontend fetch failures** (API not running): a simple inline "API unreachable — is `uvicorn` running?" message, since this is a two-terminal local dev setup.

---

## Testing

- `tests/test_api.py`, following existing pytest conventions: endpoint tests against a throwaway SQLite DB (via `db/client.py`'s `get_engine`/`init_db`, same as production code path, just pointed at `sqlite:///:memory:`), with `ClusterRunner` mocked for the `/api/runs` tests (no real AWS calls in tests).
- Frontend: manual verification only, no test framework added.

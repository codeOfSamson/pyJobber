import datetime

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_db
from api.main import app
from db.models import JobApplication, RunLog


@pytest.fixture
def client(session):
    def _override_get_db():
        yield session
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_check():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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

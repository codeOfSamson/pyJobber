import datetime

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_db
from api.main import app
from db.models import JobApplication


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

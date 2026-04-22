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

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

from functools import lru_cache

from api.cluster_runner import ClusterRunner
from db.client import get_engine, get_session, init_db
from main import build_db_url
from secrets.loader import load_secrets


@lru_cache
def _get_engine():
    creds = load_secrets()
    engine = get_engine(build_db_url(creds))
    init_db(engine)
    return engine


@lru_cache
def get_cluster_runner() -> ClusterRunner:
    return ClusterRunner()


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

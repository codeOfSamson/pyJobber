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

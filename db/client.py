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

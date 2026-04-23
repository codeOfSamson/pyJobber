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

"""Database models and session setup using SQLAlchemy + Postgres.

Tables:
  datasets  — uploaded files metadata
  runs      — multiverse run metadata + aggregated results JSON
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///./nse_dev.db"
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True)
    original_filename = Column(String)
    storage_path = Column(String)          # server file path
    format = Column(String)                # csv | xlsx
    n_rows = Column(Integer)
    columns_json = Column(Text)            # JSON list of column info dicts
    created_at = Column(DateTime, default=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    dataset_id = Column(String)
    config_json = Column(Text)             # full Config JSON
    state = Column(String, default="queued")  # queued|running|done|failed
    progress = Column(Float, default=0.0)
    n_done = Column(Integer, default=0)
    n_total = Column(Integer, default=0)
    parquet_path = Column(String)          # spec rows on disk
    results_json = Column(Text)            # aggregated results JSON
    failure_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)

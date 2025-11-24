import datetime as dt
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .database import Base

# SQLite prior to 3.38 lacks native JSON, but SQLAlchemy emulates it via JSON/SQLiteJSON.
JsonType = JSON().with_variant(SQLiteJSON(), "sqlite").with_variant(JSONB(), "postgresql")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JsonType, nullable=True, default=list)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)



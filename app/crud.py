import datetime as dt
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


def create_note(db: Session, note_in: schemas.NoteCreate) -> models.Note:
    note = models.Note(
        title=note_in.title,
        content=note_in.content,
        tags=note_in.tags or [],
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_note(db: Session, note_id: int, include_deleted: bool = False) -> Optional[models.Note]:
    stmt = select(models.Note).where(models.Note.id == note_id)
    if not include_deleted:
        stmt = stmt.where(models.Note.is_deleted.is_(False))
    return db.scalar(stmt)


def list_notes(
    db: Session,
    *,
    tag: Optional[str] = None,
    title_contains: Optional[str] = None,
    include_deleted: bool = False,
) -> Sequence[models.Note]:
    stmt = select(models.Note)
    if not include_deleted:
        stmt = stmt.where(models.Note.is_deleted.is_(False))
    if title_contains:
        stmt = stmt.where(models.Note.title.ilike(f"%{title_contains}%"))
    stmt = stmt.order_by(models.Note.created_at.desc())
    results = db.execute(stmt).scalars().all()
    if tag:
        results = [note for note in results if note.tags and tag in note.tags]
    return results


def soft_delete_note(db: Session, note: models.Note) -> models.Note:
    note.is_deleted = True
    note.deleted_at = dt.datetime.utcnow()
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


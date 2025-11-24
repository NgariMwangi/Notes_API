from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
import redis.asyncio as redis

from . import crud, models, schemas
from .cache import cache_note, get_cached_note, invalidate_note_cache
from .config import get_settings
from .database import Base, engine, get_db
from .rate_limit import rate_limiter
from .recent import get_recent_notes, push_recent_note
from .redis_client import redis_dependency

settings = get_settings()
app = FastAPI(title="Notes API", version="1.0.0")

Base.metadata.create_all(bind=engine)


@app.post("/notes", response_model=schemas.Note, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limiter)])
async def create_note(
    note_in: schemas.NoteCreate,
    db: Session = Depends(get_db),
    cache_client: redis.Redis = Depends(redis_dependency),
) -> schemas.Note:
    note = crud.create_note(db, note_in)
    note_schema = schemas.Note.model_validate(note)
    await _safe_cache_note(cache_client, note_schema)
    return note_schema


@app.get("/notes", response_model=schemas.NotesListResponse, dependencies=[Depends(rate_limiter)])
async def list_notes(
    tag: Optional[str] = Query(default=None),
    title_contains: Optional[str] = Query(default=None),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> schemas.NotesListResponse:
    notes = crud.list_notes(db, tag=tag, title_contains=title_contains, include_deleted=include_deleted)
    items = [schemas.Note.model_validate(note) for note in notes]
    return schemas.NotesListResponse(total=len(items), items=items)


@app.get("/notes/recent", response_model=List[schemas.Note], dependencies=[Depends(rate_limiter)])
async def recent_notes(
    request: Request,
    db: Session = Depends(get_db),
    cache_client: redis.Redis = Depends(redis_dependency),
) -> List[schemas.Note]:
    note_ids = await _safe_get_recent(cache_client, request)
    items: List[schemas.Note] = []
    for note_id in note_ids:
        note = crud.get_note(db, note_id, include_deleted=False)
        if note:
            items.append(schemas.Note.model_validate(note))
    return items


@app.get("/notes/{note_id}", response_model=schemas.Note, dependencies=[Depends(rate_limiter)])
async def read_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    cache_client: redis.Redis = Depends(redis_dependency),
    use_cache: bool = Query(default=True),
    include_deleted: bool = Query(default=False),
) -> schemas.Note:
    if use_cache:
        note_schema = await _safe_get_cached_note(cache_client, note_id)
        if note_schema:
            await _safe_push_recent(cache_client, request, note_id)
            return note_schema

    note = crud.get_note(db, note_id, include_deleted=include_deleted)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note_schema = schemas.Note.model_validate(note)
    await _safe_cache_note(cache_client, note_schema)
    await _safe_push_recent(cache_client, request, note_id)
    return note_schema


@app.delete("/notes/{note_id}", response_model=schemas.Note, dependencies=[Depends(rate_limiter)])
async def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    cache_client: redis.Redis = Depends(redis_dependency),
) -> schemas.Note:
    note = crud.get_note(db, note_id, include_deleted=True)
    if not note or note.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note = crud.soft_delete_note(db, note)
    note_schema = schemas.Note.model_validate(note)
    await _safe_invalidate_cache(cache_client, note_id)
    return note_schema


async def _safe_cache_note(client: redis.Redis, note: schemas.Note) -> None:
    if not client:
        return
    try:
        await cache_note(client, note)
    except redis.RedisError:
        pass


async def _safe_get_cached_note(client: redis.Redis, note_id: int) -> Optional[schemas.Note]:
    if not client:
        return None
    try:
        return await get_cached_note(client, note_id)
    except redis.RedisError:
        return None


async def _safe_invalidate_cache(client: redis.Redis, note_id: int) -> None:
    if not client:
        return
    try:
        await invalidate_note_cache(client, note_id)
    except redis.RedisError:
        pass


async def _safe_push_recent(client: redis.Redis, request: Request, note_id: int) -> None:
    if not client:
        return
    if not request.client:
        return
    try:
        await push_recent_note(client, request.client.host, note_id)
    except redis.RedisError:
        pass


async def _safe_get_recent(client: redis.Redis, request: Request) -> List[int]:
    if not client or not request.client:
        return []
    try:
        return await get_recent_notes(client, request.client.host)
    except redis.RedisError:
        return []



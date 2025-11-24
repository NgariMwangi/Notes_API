# Notes API

A FastAPI-based backend that manages notes with validation, caching, and rate limiting. The service persists data in SQLite (or any SQLAlchemy-supported database) and leverages Redis for caching, rate limiting, and tracking recently viewed notes.

## Features

- Create, list, fetch, and soft-delete notes.
- Validation via Pydantic (title/content length, tag rules).
- Redis-backed caching for `GET /notes/{id}`.
- Rate limiting: 100 requests per 10 minutes per client IP.
- Recently viewed notes stored per client in Redis.
- Soft delete keeps history while hiding notes from default queries.

## Requirements

- Python 3.8+
- Redis 6+
- SQLite (default) or custom database via `DATABASE_URL`.

## Setup

```bash
python -m venv env
source env\Scripts\activate  # Linux
pip install -r requirements.txt
```

Create a `.env` file (optional) to override defaults:

```
DATABASE_URL=sqlite:///./notes.db
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT=100
RATE_LIMIT_WINDOW=600
NOTE_CACHE_TTL=300
RECENT_NOTES_LIMIT=5
```

## Running

```bash
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for interactive Swagger documentation.

## Endpoints

- `POST /notes` – Create a note.
- `GET /notes/{note_id}` – Fetch a note (uses Redis cache by default).
- `GET /notes` – List notes with `tag`, `title_contains`, and `include_deleted` filters.
- `DELETE /notes/{note_id}` – Soft delete a note.
- `GET /notes/recent` – Retrieve per-client recently viewed notes.

## Rate Limiting

Each request executes a dependency that increments a Redis counter keyed by the client IP. The counter expires after 10 minutes. Once it exceeds 100 requests for the current window, the API responds with HTTP 429. On Redis outages the limiter gracefully allows traffic to favor availability.

## Creative Features

1. **Soft delete:** `DELETE /notes/{id}` flags a note as deleted instead of removing it, preserving history. Deleted notes stay out of list queries unless `include_deleted=true`.
2. **Recently viewed notes:** Every successful `GET /notes/{id}` stores the note ID in a Redis list scoped to the client IP. The `GET /notes/recent` endpoint returns up to the last five visited notes.

## Design Notes

- **Dependency injection:** Database sessions and Redis clients are provided through FastAPI `Depends`, promoting testability.
- **Caching:** Individual notes are stored as serialized Pydantic models in Redis with a TTL. Writes and deletes invalidate the cache so reads remain consistent.
- **Extensibility:** The settings module centralizes environment configuration, and the service layer (CRUD, cache, rate limiter) provides separation of concerns for future enhancements.



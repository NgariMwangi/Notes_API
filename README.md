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

The API implements a sliding window rate limiter using Redis to protect against abuse and ensure fair resource usage across all clients. The rate limiting mechanism is applied to all endpoints through FastAPI's dependency injection system.

### Implementation Details

- **Algorithm:** Token bucket-style counter with sliding window expiration
- **Limit:** 100 requests per 10 minutes (600 seconds) per client IP address
- **Storage:** Redis counters keyed by client IP (`rate:ip:{ip_address}`)
- **Window Management:** Each counter automatically expires after the configured window period, resetting the limit for that client
- **Error Response:** When the limit is exceeded, the API returns HTTP 429 (Too Many Requests) with a descriptive error message

### Technical Approach

The rate limiter is implemented as a FastAPI dependency (`rate_limiter`) that executes before each request handler. It uses Redis pipelines for atomic operations:

1. **Increment Counter:** Atomically increments the request count for the client's IP
2. **Set Expiration:** Sets the key expiration on first request in the window (using `NX` flag to avoid resetting existing windows)
3. **Check Limit:** Compares the current count against the configured threshold
4. **Fail-Safe Behavior:** If Redis is unavailable, the limiter gracefully allows requests to proceed, prioritizing service availability over strict rate limiting

### Configuration

Rate limiting parameters can be customized via environment variables:
- `RATE_LIMIT`: Maximum number of requests allowed (default: 100)
- `RATE_LIMIT_WINDOW`: Time window in seconds (default: 600, i.e., 10 minutes)

### Benefits

- **DDoS Protection:** Prevents single clients from overwhelming the API
- **Resource Fairness:** Ensures all users have equal access to API resources
- **Cost Control:** Limits database and Redis operations per client
- **Graceful Degradation:** Service remains available even if Redis fails

## Creative Features

The API includes two optional creative features that enhance user experience and data management capabilities:

### 1. Soft Delete

The soft delete feature provides a safer alternative to permanent deletion by marking notes as deleted rather than removing them from the database entirely.

**Implementation:**
- Notes have an `is_deleted` boolean flag and a `deleted_at` timestamp field
- The `DELETE /notes/{note_id}` endpoint performs a soft delete by setting these fields
- Deleted notes are automatically excluded from all list and retrieval queries by default
- The `include_deleted=true` query parameter allows administrators to view deleted notes when needed

**Benefits:**
- **Data Recovery:** Deleted notes can be recovered if needed (by updating the `is_deleted` flag)
- **Audit Trail:** Maintains a complete history of all notes, including when they were deleted
- **User Safety:** Prevents accidental permanent data loss
- **Compliance:** Helps meet data retention requirements for audit purposes

**Usage:**
```bash
# Soft delete a note
DELETE /notes/123

# List notes (excludes deleted by default)
GET /notes

# Include deleted notes in results
GET /notes?include_deleted=true
```

### 2. Recently Viewed Notes

This feature tracks and provides quick access to notes that users have recently viewed, enhancing navigation and user experience.

**Implementation:**
- Each successful `GET /notes/{note_id}` request automatically adds the note ID to a Redis list
- The list is scoped per client IP address, providing personalized recent notes for each user
- Redis lists are used to maintain chronological order (most recent first)
- Duplicate entries are automatically removed when a note is viewed again (moved to the top)
- The list is automatically trimmed to the configured limit (default: 5 notes)

**Storage Details:**
- **Key Format:** `recent:ip:{client_ip_address}`
- **Data Structure:** Redis list containing note IDs as integers
- **Expiration:** Lists expire after the rate limit window (10 minutes) to prevent stale data accumulation
- **Limit:** Configurable via `RECENT_NOTES_LIMIT` environment variable (default: 5)

**Benefits:**
- **Quick Access:** Users can quickly return to notes they were recently working on
- **Personalized Experience:** Each client gets their own recent notes list
- **Performance:** Leverages Redis for fast retrieval without database queries
- **Memory Efficient:** Automatic expiration and trimming prevent unbounded growth

**Usage:**
```bash
# View a note (automatically added to recent list)
GET /notes/123

# Retrieve recently viewed notes for your IP
GET /notes/recent
```

**Response Format:**
The `/notes/recent` endpoint returns an array of note objects in the order they were most recently viewed, with the most recent note first. Only notes that still exist and are not deleted are included in the response.

## Design Notes

This section outlines the architectural decisions, design patterns, and tradeoffs made during the implementation of the Notes API.

### Architecture & Project Structure

The codebase follows a clean, modular architecture with clear separation of concerns:

```
app/
├── main.py          # FastAPI application and route handlers
├── models.py        # SQLAlchemy database models
├── schemas.py       # Pydantic validation models
├── crud.py          # Database operations (CRUD functions)
├── database.py      # Database connection and session management
├── config.py        # Application configuration and settings
├── redis_client.py  # Redis connection management
├── rate_limit.py    # Rate limiting logic
├── cache.py         # Redis caching utilities
└── recent.py        # Recently viewed notes functionality
```

### Dependency Injection

**Pattern:** FastAPI's `Depends` mechanism is used extensively throughout the application to inject dependencies.

**Benefits:**
- **Testability:** Dependencies can be easily mocked in unit tests
- **Flexibility:** Different implementations can be swapped without changing route handlers
- **Resource Management:** Database sessions and Redis connections are properly managed and closed
- **Clean Code:** Route handlers focus on business logic rather than resource acquisition

**Examples:**
- Database sessions: `db: Session = Depends(get_db)`
- Redis clients: `cache_client: redis.Redis = Depends(redis_dependency)`
- Rate limiter: Applied via `dependencies=[Depends(rate_limiter)]`

### Data Validation with Pydantic

**Approach:** All request and response data is validated using Pydantic v2 models.

**Validation Rules:**
- **Title:** Required, 1-100 characters
- **Content:** Required, 1-5000 characters
- **Tags:** Optional list of strings, each tag max 30 characters
- **Automatic Validation:** FastAPI automatically validates requests against Pydantic schemas and returns 422 errors for invalid data

**Benefits:**
- **Type Safety:** Compile-time and runtime type checking
- **Automatic Documentation:** OpenAPI/Swagger docs generated from Pydantic models
- **Data Transformation:** Automatic serialization/deserialization
- **Error Messages:** Clear, detailed validation error responses

### Caching Strategy

**Implementation:** Redis is used to cache individual note objects to reduce database load and improve response times.

**Cache Key Format:** `note:{note_id}`

**Cache Lifecycle:**
1. **Cache Write:** When a note is created or retrieved from the database, it's serialized as JSON and stored in Redis
2. **Cache Read:** `GET /notes/{note_id}` checks Redis first before querying the database
3. **Cache Invalidation:** When a note is deleted, the cache entry is immediately removed to prevent stale data
4. **TTL:** Cache entries expire after a configurable time (default: 300 seconds) to ensure eventual consistency

**Tradeoffs:**
- **Pros:** Significant performance improvement for frequently accessed notes, reduced database load
- **Cons:** Additional complexity, potential for stale data (mitigated by TTL and invalidation)
- **Fail-Safe:** If Redis is unavailable, the API gracefully falls back to database queries

**Cache Control:**
- The `use_cache` query parameter (default: `true`) allows clients to bypass cache when needed
- Useful for ensuring fresh data or debugging cache-related issues

### Error Handling

**Philosophy:** The API provides clear, actionable error messages with appropriate HTTP status codes.

**Error Responses:**
- **400 Bad Request:** Invalid request data (handled by Pydantic validation)
- **404 Not Found:** Note doesn't exist or has been deleted
- **429 Too Many Requests:** Rate limit exceeded
- **500 Internal Server Error:** Unexpected server errors (with detailed logging)

**Graceful Degradation:**
- Redis failures don't break the API; operations fall back to database-only mode
- Rate limiting allows requests through if Redis is unavailable (favoring availability)
- Cache misses automatically fall back to database queries

### Database Design

**ORM:** SQLAlchemy 2.0 with async support capability

**Schema:**
- **Primary Key:** Auto-incrementing integer ID
- **Timestamps:** `created_at` and `updated_at` for audit trails
- **Soft Delete:** `is_deleted` boolean and `deleted_at` timestamp
- **JSON Storage:** Tags stored as JSON array (SQLite-compatible)

**Query Optimization:**
- Indexes on `id` (primary key) and `is_deleted` for fast filtering
- Efficient queries using SQLAlchemy's query builder
- Tag filtering done in Python (acceptable for small datasets; could be optimized with full-text search for larger scales)

### Configuration Management

**Approach:** Centralized configuration using Pydantic Settings with environment variable support.

**Features:**
- **Environment Variables:** All settings can be overridden via `.env` file or environment variables
- **Type Safety:** Settings are validated and typed
- **Default Values:** Sensible defaults for all configuration options
- **Caching:** Settings are cached using `@lru_cache` to avoid repeated file reads

**Configuration Options:**
- Database connection string
- Redis connection URL
- Rate limiting parameters
- Cache TTL settings
- Recent notes limit

### Extensibility & Future Enhancements

The architecture is designed to be easily extensible:

**Easy Additions:**
- **New Endpoints:** Add routes in `main.py` following existing patterns
- **New Features:** Create new modules (like `recent.py`) and integrate via dependencies
- **Database Changes:** Modify `models.py` and run migrations
- **Validation Rules:** Update Pydantic schemas in `schemas.py`

**Potential Enhancements:**
- User authentication and authorization
- Note sharing and collaboration features
- Full-text search capabilities
- Note versioning/history
- Export/import functionality
- WebSocket support for real-time updates

### Tradeoffs & Design Decisions

**SQLite vs PostgreSQL:**
- **Chosen:** SQLite for simplicity and zero-configuration
- **Tradeoff:** SQLite lacks some advanced features but is sufficient for the assessment requirements
- **Flexibility:** Database URL can be changed to PostgreSQL without code modifications

**Synchronous vs Asynchronous:**
- **Chosen:** Mix of sync (SQLAlchemy) and async (Redis) operations
- **Reasoning:** SQLAlchemy async requires additional setup; sync operations are sufficient for this use case
- **Future:** Could be migrated to fully async for better concurrency

**Redis Dependency:**
- **Chosen:** Redis is required but gracefully degrades if unavailable
- **Alternative Considered:** In-memory rate limiting, but Redis provides persistence and shared state across instances
- **Production Note:** In production, Redis unavailability would be monitored and alerted

**Rate Limiting Strategy:**
- **Chosen:** Sliding window with Redis counters
- **Alternative:** Token bucket, fixed window, or distributed rate limiting
- **Reasoning:** Simple to implement, effective, and works well with Redis

**Caching Strategy:**
- **Chosen:** Write-through caching with TTL and manual invalidation
- **Alternative:** Write-behind or cache-aside patterns
- **Reasoning:** Balances performance with data consistency requirements



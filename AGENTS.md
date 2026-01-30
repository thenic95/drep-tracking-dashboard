# Agent Memory & Instructions

This file serves as the persistent memory for the AI agent. It is updated nightly by the Compound Review process.

## Core Instructions
- Always read this file before starting a task.
- When you learn a new pattern, fix a bug that shouldn't happen again, or discover a better way to do something, update this file.
- Keep instructions concise and actionable.

## Learned Patterns

### Async Architecture (learned 2026-01-28)
- Backend uses `httpx.AsyncClient` for all Koios API calls (migrated from `requests`).
- All `koios_api.py` and `data_manager.py` functions are `async`.
- **Scheduler runs in a separate daemon thread** and bridges sync→async via `asyncio.run()`. Each job creates its own event loop — acceptable for hourly/2-hourly jobs.
- Rate limiting between paginated Koios calls uses `await asyncio.sleep(0.2–0.5)`.
- httpx exceptions differ from requests: use `HTTPStatusError` and `RequestError`, not `ConnectionError`/`HTTPError`.

### SQLAlchemy ORM (learned 2026-01-29)
- Database layer uses SQLAlchemy 2.0 declarative models (`backend/models.py`).
- Session-per-request pattern: FastAPI endpoints get `Session` via `Depends(get_db_dep)`.
- ORM objects are converted to dicts for API responses. Pydantic schemas have `from_attributes = True` for direct ORM→schema conversion — prefer using that over manual dict conversion.
- Vote table uses surrogate `vote_id` PK + `UniqueConstraint("drep_id", "ga_id")`. Duplicate detection happens in `add_drep_vote()`.

### Config & Secrets (learned 2026-01-28)
- Secrets loaded via `python-dotenv` from `.env` file in backend directory.
- `KOIOS_API_TOKEN` comes from env var, never hardcoded.
- DB path constructed from `os.path.join(BACKEND_DIR, DB_FILE)` in `config.py`.

### Code Quality (learned 2026-01-29)
- **Ruff** configured in `backend/pyproject.toml`: line length 88, Python 3.12 target, double quotes.
- Enabled rule sets: E4, E7, E9, F (pyflakes), I (isort), B (flake8-bugbear). B008 disabled (function call in defaults, needed for FastAPI `Depends()`).
- No mypy or type-checking configured yet.

### Testing (learned 2026-01-29)
- Backend tests live in `backend/tests/`. Run with `pytest backend/tests/`.
- Some modules still have `if __name__ == "__main__"` test blocks (koios_api.py, database.py) — these are for manual debugging, not CI.
- Test for the API uses FastAPI's `TestClient`.

## Project Context
- **Project**: DRep Tracking MVP — Cardano DRep governance voting tracker
- **Tech Stack**: FastAPI (async) + SQLAlchemy ORM + SQLite | Vue 3 + Vite frontend
- **Current Focus**: Backend modernization (async, ORM, code quality tooling)

## Gotchas to Avoid

### Type Hint Mismatch in main.py
- Several endpoint signatures annotate `db` as `sqlite3.Connection` but the actual type is `sqlalchemy.orm.Session`. This doesn't cause runtime errors but breaks static analysis and confuses developers. Fix these when touching those endpoints.

### Scheduler + Async Boundary
- Each scheduler job calls `asyncio.run()` which creates and destroys an event loop. Don't nest `asyncio.run()` calls or call it from within an existing async context — it will raise `RuntimeError`.
- Scheduler jobs must get their own DB session (not reuse FastAPI's dependency injection).

### httpx Client Lifecycle
- Currently creates a new `httpx.AsyncClient` per request (`async with httpx.AsyncClient(...)`). Works but inefficient. If performance becomes an issue, consider a module-level persistent client with proper shutdown.

### Pagination Rate Limiting is Inconsistent
- Only some paginated Koios calls have `asyncio.sleep()` delays between pages. If Koios starts rate-limiting, add delays to all paginated calls.

### Vote Deduplication
- Vote table allows inserts with different `vote_id` for the same `(drep_id, ga_id)` pair. The `UniqueConstraint` prevents this at the DB level, but code should handle `IntegrityError` on duplicate insert attempts.

### Binary DB File in Git
- `backend/drep_tracker.db` (SQLite) is tracked in git. This causes merge conflicts and inflates repo size. Consider adding it to `.gitignore` for production.

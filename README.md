# AI Usage Metering and Quota Service

FastAPI service for AI text generation with per-user quota enforcement, credit multipliers, and usage tracking.

## Reviewer Guide

- Solution design: [docs/design.md](docs/design.md)
- C4 architecture: [docs/c4.md](docs/c4.md)
- Data model ERD: [docs/data-model.md](docs/data-model.md)

## What It Is

The service lets a client configure per-user quota settings, generate text, and inspect current usage plus history.

## Run

```bash
docker compose up --build
```

The container runs `alembic upgrade head` on startup, so the schema is created automatically.

## Test

```bash
docker compose run --rm api pytest
```

## Useful URLs

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Postgres: `localhost:5432`

## Key API Routes

- `PUT /users/{user_key}/quota`
- `POST /users/{user_key}/generate`
- `GET /users/{user_key}/usage`
- `GET /users/{user_key}/usage/records`

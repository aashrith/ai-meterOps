# AI Usage Metering and Quota Service

FastAPI service for AI text generation with per-user quota enforcement, credit multipliers, and usage tracking.

## Preview

- Design doc: [docs/design.md](docs/design.md)
- C4 diagrams: [docs/c4.md](docs/c4.md)
- Data model ERD: [docs/data-model.md](docs/data-model.md)

## Run

```bash
docker compose up --build
```

The container runs `alembic upgrade head` on startup, so the schema is created automatically.

## Test

```bash
docker compose run --rm api pytest
```

## What is included in this first scaffold

- FastAPI app entrypoint
- Pydantic DTO validation for API boundaries
- Postgres via Docker Compose
- Alembic migration scaffold
- DDD + hexagonal package layout
- Architecture preview document
- Usage metering and quota service implementation

## Local URLs

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Postgres: `localhost:5432`

## API

- `PUT /users/{user_key}/quota`
- `POST /users/{user_key}/generate`
- `GET /users/{user_key}/usage`
- `GET /users/{user_key}/usage/records`

## Next build steps

- Expand documentation with the design decision write-up
- Record the walkthrough video

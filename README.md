# AI Usage Metering and Quota Service

FastAPI service for AI text generation with per-user quota enforcement, credit multipliers, and usage tracking.

## Preview

- C4 diagram: [docs/c4.md](docs/c4.md)

## Run

```bash
docker compose up --build
```

To apply the first migration after the stack is up:

```bash
docker compose exec api alembic upgrade head
```

## What is included in this first scaffold

- FastAPI app entrypoint
- Pydantic DTO validation for API boundaries
- Postgres via Docker Compose
- Alembic migration scaffold
- DDD + hexagonal package layout
- Architecture preview document

## Local URLs

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Postgres: `localhost:5432`

## Next build steps

- Wire application use cases to the repository ports
- Add quota reservation and usage reconciliation
- Implement the mock AI adapter
- Add tests for quota behavior and concurrent requests

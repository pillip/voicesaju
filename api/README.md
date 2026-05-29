# VoiceSaju Backend

FastAPI service for VoiceSaju.

## Quick Start

```bash
cd api
uv sync
uv run uvicorn voicesaju.main:app --reload
```

The service starts on `http://localhost:8000`.

- `GET /healthz` — liveness probe (returns `{"status":"ok"}`)
- `GET /docs` — interactive OpenAPI docs

## Testing

```bash
uv run pytest -q
uv run pytest --cov=voicesaju --cov-report=term-missing
```

## Linting

```bash
uv run ruff check .
uv run black --check .
```

## Configuration

Settings load from environment variables and `.env.local` (gitignored).

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_NAME` | `voicesaju` | Application name |
| `ENVIRONMENT` | `local` | One of `local`, `dev`, `staging`, `prod` |
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |

See `.env.example` for a template.

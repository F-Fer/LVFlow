LVFlow MVP – FastAPI + Postgres (local)

Quickstart

1) Start Postgres

```bash
docker compose up -d
```

2) Install deps and run API

```bash
uv sync
uv run python main.py
```

API will be on http://localhost:8000 with docs at /docs.

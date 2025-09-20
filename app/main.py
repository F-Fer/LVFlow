from fastapi import FastAPI
from .routers.health import router as health_router
from .routers.ingest import router as ingest_router


def create_app() -> FastAPI:
    app = FastAPI(title="LVFlow MVP", version="0.1.0")

    app.include_router(health_router)
    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    return app


app = create_app()


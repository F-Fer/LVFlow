from fastapi import FastAPI
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from .routers.health import router as health_router
from .routers.ingest import router as ingest_router
from .routers.web import router as web_router
from .db import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="LVFlow MVP", version="0.1.0", lifespan=lifespan)

    app.include_router(health_router)
    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    app.include_router(web_router)

    # Static (if you add files under app/static)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    # Serve uploaded PDFs
    uploads_dir = Path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
    return app


app = create_app()


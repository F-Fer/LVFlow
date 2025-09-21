from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routers.health import router as health_router
from .routers.ingest import router as ingest_router
from .routers.web import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(title="LVFlow MVP", version="0.1.0")

    app.include_router(health_router)
    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    app.include_router(web_router)

    # Static (if you add files under app/static)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    return app


app = create_app()


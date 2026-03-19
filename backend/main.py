"""
Collabscribe FastAPI application.
Clean initialization with all business logic delegated to route modules.
Includes background snapshot scheduler for automatic document versioning.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import close_pool, create_pool
from init_db import create_tables
from routes import analytics, diff, documents, health, monitoring, versions, websocket
from socket_handlers import get_combined_app
from tasks import get_snapshot_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("collabscribe.main")
FRONTEND_ASSETS_DIR = Path(__file__).resolve().parent.parent / "frontend-app" / "dist" / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create pool, schema, and snapshot scheduler.
    Shutdown: stop scheduler and close pool.
    """
    logger.info("Starting application...")
    pool = await create_pool()
    await create_tables(pool)

    from services.nlp_pipeline import init_nlp

    await init_nlp()
    logger.info("NLP pipeline initialized")

    scheduler = await get_snapshot_scheduler()
    await scheduler.start()
    logger.info("Snapshot scheduler initialized and running")

    yield

    logger.info("Shutting down...")
    await scheduler.stop()
    await close_pool()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Collabscribe",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/assets",
    StaticFiles(directory=str(FRONTEND_ASSETS_DIR), check_dir=False),
    name="frontend-assets",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(websocket.router)
app.include_router(versions.router)
app.include_router(monitoring.router)
app.include_router(analytics.router)
app.include_router(diff.router)

combined_app = get_combined_app(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(combined_app, host="0.0.0.0", port=8000)

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from docurapi.core.logging_config import logger
from docurapi.core.settings import settings
from docurapi.db.connection import initialize_database
from docurapi.routers import (
    admin_cleanup,
    admin_dashboard,
    admin_payments,
    admin_system,
    frontend,
    health,
    jobs,
    payments,
    pricing,
    processing,
    templates,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    logger.info("%s started. Version=%s", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("%s stopped.", settings.APP_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_path = settings.BASE_DIR / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    app.include_router(frontend.router)

    app.include_router(health.router)
    app.include_router(processing.router)
    app.include_router(jobs.router)
    app.include_router(templates.router)
    app.include_router(payments.router)
    app.include_router(pricing.router)

    app.include_router(admin_payments.router)
    app.include_router(admin_dashboard.router)
    app.include_router(admin_cleanup.router)
    app.include_router(admin_system.router)

    return app


app = create_app()

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from docurapi.core.logging_config import logger
from docurapi.core.settings import settings
from docurapi.db.connection import initialize_database
from docurapi.routers import health, jobs, payments, processing, templates


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
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

    @app.on_event("startup")
    def startup_event() -> None:
        initialize_database()
        logger.info("%s started. Version=%s", settings.APP_NAME, settings.APP_VERSION)

    @app.get("/")
    def home():
        index_file = settings.BASE_DIR / "templates" / "index.html"

        if index_file.exists():
            return FileResponse(index_file)

        return HTMLResponse(
            """
            <html>
                <head>
                    <title>DocuRapi</title>
                </head>
                <body style="font-family: Arial; max-width: 720px; margin: 40px auto;">
                    <h1>DocuRapi</h1>
                    <p>Backend modular berhasil berjalan.</p>
                    <p>Health check: <a href="/api/health">/api/health</a></p>
                </body>
            </html>
            """
        )

    app.include_router(health.router)
    app.include_router(processing.router)
    app.include_router(jobs.router)
    app.include_router(templates.router)
    app.include_router(payments.router)

    return app


app = create_app()

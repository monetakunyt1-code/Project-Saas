from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
STATIC_APP = STATIC / "app"
TEMPLATES = ROOT / "templates"
MAIN_PY = ROOT / "docurapi" / "main.py"
FRONTEND_PY = ROOT / "docurapi" / "routers" / "frontend.py"

LEGACY_FILES = [
    "advanced.css",
    "advanced.js",
    "admin_billing.js",
    "audit.css",
    "audit.js",
    "billing_center.css",
    "billing_center.js",
    "billing_enforcement_client.js",
    "billing_launcher.js",
    "docurapi_ui_shell.css",
    "docurapi_ui_shell.js",
    "journal_studio.css",
    "journal_studio.js",
    "midtrans_checkout.js",
    "notification_center.css",
    "notification_center.js",
    "reset_password.js",
    "saas_portal.css",
    "saas_portal.js",
    "security_center.css",
    "security_center.js",
    "security_client.js",
    "style.css",
    "system_health.css",
    "system_health.js",
    "task_center.css",
    "task_center.js",
    "test_center.css",
    "test_center.js",
    "workspaces.css",
    "workspaces.js",
]

STUB_FILES = {
    "app.js": 'console.info("Legacy static/app.js disabled. Use /static/app/app.js for DocuRapi MVP.");\n',
    "background_client.js": 'console.info("Legacy background_client disabled. DocuRapi MVP uses direct /api/process.");\n',
    "notification_client.js": 'console.info("Legacy notification_client disabled for DocuRapi MVP.");\n',
}

SERVICE_WORKER_STUB = """self.addEventListener("install", event => self.skipWaiting());
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});
"""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def audit() -> int:
    print("=== DocuRapi Legacy UI Audit ===")

    issues = 0

    main_text = read(MAIN_PY)
    frontend_text = read(FRONTEND_PY)
    static_index = read(STATIC / "index.html")
    mvp_index = read(STATIC_APP / "index.html")
    template_index = read(TEMPLATES / "index.html")

    checks = [
        ("main.py has legacy @app.get('/')", '@app.get("/")' in main_text),
        ("main.py imports RedirectResponse", "RedirectResponse" in main_text),
        ("main.py imports HTMLResponse", "HTMLResponse" in main_text),
        ("main.py references templates/index.html directly", "templates" in main_text and "index.html" in main_text),
        ("frontend.py missing root route", '@router.get("/")' not in frontend_text),
        ("static/index.html missing MVP title", "Rapikan dokumen akademik tanpa login" not in static_index),
        ("templates/index.html missing MVP title", "Rapikan dokumen akademik tanpa login" not in template_index),
        ("static/app/index.html missing MVP title", "Rapikan dokumen akademik tanpa login" not in mvp_index),
    ]

    for label, bad in checks:
        status = "BAD " if bad else "OK  "
        print(f"[{status}] {label}")
        if bad:
            issues += 1

    print("")
    print("Legacy files in static root:")
    for name in LEGACY_FILES:
        path = STATIC / name
        if path.exists():
            print(f"  FOUND {path.relative_to(ROOT)}")
            issues += 1

    print("")
    print("Legacy strings:")
    legacy_patterns = [
        "Task Center",
        "Buka Fitur Lanjutan",
        "Audit Akademik",
        "/api/background/submit",
        "/api/notifications/unread-count",
    ]

    for pattern in legacy_patterns:
        found = []
        for path in [STATIC / "index.html", STATIC / "app.js", STATIC / "background_client.js", STATIC / "notification_client.js"]:
            if path.exists() and pattern in read(path):
                found.append(str(path.relative_to(ROOT)))

        if found:
            issues += 1
            print(f"  FOUND '{pattern}' in {', '.join(found)}")
        else:
            print(f"  OK '{pattern}' not found in active root legacy files")

    print("")
    print(f"Total issues: {issues}")
    return issues


def clean_main_py() -> None:
    content = '''from __future__ import annotations

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
'''
    write(MAIN_PY, content)


def clean_frontend_py() -> None:
    content = '''from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from docurapi.core.settings import settings

router = APIRouter(tags=["frontend"])


@router.get("/")
def frontend_home():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "index.html")


@router.get("/admin")
def frontend_admin():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "admin.html")
'''
    write(FRONTEND_PY, content)


def apply_cleanup() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "legacy_ui_backup" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"Backup dir: {backup_dir.relative_to(ROOT)}")

    for path in [
        MAIN_PY,
        FRONTEND_PY,
        STATIC / "index.html",
        TEMPLATES / "index.html",
        STATIC / "app.js",
        STATIC / "background_client.js",
        STATIC / "notification_client.js",
    ]:
        if path.exists():
            dst = backup_dir / path.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)

    for name in LEGACY_FILES:
        src = STATIC / name
        if src.exists():
            dst = backup_dir / "static" / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved legacy file: static/{name}")

    mvp_index = STATIC_APP / "index.html"

    if not mvp_index.exists():
        raise SystemExit("ERROR: static/app/index.html tidak ditemukan. Cleanup dibatalkan.")

    TEMPLATES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mvp_index, STATIC / "index.html")
    shutil.copy2(mvp_index, TEMPLATES / "index.html")

    for name, content in STUB_FILES.items():
        write(STATIC / name, content)

    write(STATIC / "service-worker.js", SERVICE_WORKER_STUB)
    write(STATIC / "sw.js", SERVICE_WORKER_STUB)

    bg_compat = ROOT / "docurapi" / "routers" / "background_compat.py"
    if bg_compat.exists():
        dst = backup_dir / bg_compat.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(bg_compat), str(dst))
        print("Moved background_compat.py to backup.")

    clean_main_py()
    clean_frontend_py()

    print("Cleanup applied.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply cleanup. Without this flag, only audit.")
    args = parser.parse_args()

    issues = audit()

    if args.apply:
        print("")
        print("=== APPLY CLEANUP ===")
        apply_cleanup()
        print("")
        audit()
    else:
        print("")
        print("Audit only. Run with --apply to clean legacy UI files.")

    raise SystemExit(0)


if __name__ == "__main__":
    main()

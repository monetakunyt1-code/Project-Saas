from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "releases"
RELEASE_DIR.mkdir(parents=True, exist_ok=True)

VERSION = "5.0.0-rc1"

REQUIRED_ROUTES = {
    "/",
    "/login",
    "/register",
    "/pricing",
    "/account",
    "/admin",
    "/security-center",
    "/workspaces",
    "/task-center",
    "/system-health",
    "/test-center",
    "/api/health",
    "/api/auth/me",
    "/api/plans",
    "/api/workspaces",
    "/api/background/health",
    "/api/security/health",
    "/api/system/health",
    "/api/tests/health",
        "/notifications",
        "/reset-password",
        "/api/notifications/health",
}

REQUIRED_FILES = {
    "app.py",
    "config.py",
    "requirements.txt",
    "requirements.lock.txt",
    "FEATURE_MANIFEST.json",
    ".env.production.example",
    "release_tool.py",
    "release.ps1",
    "start_release_candidate.ps1",
    "RELEASE_NOTES_5.0_RC1.md",
}

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "storage",
    "releases",
}

EXCLUDED_RELEASE_FILES = {
    ".env",
    ".env.production",
    "LOCAL_ADMIN.txt",
}

EXCLUDED_RELEASE_SUFFIXES = {
    ".db",
    ".pyc",
    ".pyo",
    ".log",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_check(
    checks: list[dict[str, Any]],
    category: str,
    name: str,
    status: str,
    detail: str,
    evidence: Any = None,
) -> None:
    checks.append(
        {
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
            "evidence": evidence,
        }
    )


def is_backup_path(path: Path) -> bool:
    lowered_name = path.name.lower()

    if "_before_" in lowered_name:
        return True

    if "before_fix" in lowered_name:
        return True

    if "before_startup" in lowered_name:
        return True

    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return True

    for part in relative.parts:
        if part.lower().startswith("_backup_"):
            return True

    return False


def active_python_files() -> list[Path]:
    files: list[Path] = []

    for path in ROOT.rglob("*.py"):
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            continue

        lowered_parts = {
            part.lower()
            for part in relative.parts
        }

        if lowered_parts.intersection(
            EXCLUDED_DIRECTORY_NAMES
        ):
            continue

        if is_backup_path(path):
            continue

        files.append(path)

    return sorted(
        files,
        key=lambda item: str(item),
    )


def check_required_files(
    checks: list[dict[str, Any]],
) -> None:
    missing = sorted(
        filename
        for filename in REQUIRED_FILES
        if not (ROOT / filename).exists()
    )

    if missing:
        add_check(
            checks,
            "Release",
            "File wajib",
            "FAIL",
            f"{len(missing)} file release belum tersedia.",
            missing,
        )
    else:
        add_check(
            checks,
            "Release",
            "File wajib",
            "PASS",
            f"Seluruh {len(REQUIRED_FILES)} file release tersedia.",
        )


def check_python_sources(
    checks: list[dict[str, Any]],
) -> None:
    files = active_python_files()
    errors: list[str] = []

    for path in files:
        try:
            source = path.read_text(
                encoding="utf-8"
            )

            compile(
                source,
                str(path),
                "exec",
            )

        except Exception as exc:
            errors.append(
                f"{path.relative_to(ROOT)}: {exc}"
            )

    if errors:
        add_check(
            checks,
            "Source Code",
            "Kompilasi Python",
            "FAIL",
            f"{len(errors)} file Python bermasalah.",
            errors,
        )
    else:
        add_check(
            checks,
            "Source Code",
            "Kompilasi Python",
            "PASS",
            f"{len(files)} file Python berhasil dikompilasi.",
        )


def sqlite_header_valid(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return (
                handle.read(16)
                == b"SQLite format 3\x00"
            )
    except OSError:
        return False


def check_databases(
    checks: list[dict[str, Any]],
) -> None:
    storage = ROOT / "storage"

    if not storage.exists():
        add_check(
            checks,
            "Database",
            "SQLite integrity",
            "FAIL",
            "Folder storage tidak ditemukan.",
        )
        return

    databases = [
        path
        for path in storage.rglob("*.db")
        if sqlite_header_valid(path)
    ]

    if not databases:
        add_check(
            checks,
            "Database",
            "SQLite integrity",
            "FAIL",
            "Database SQLite aktif tidak ditemukan.",
        )
        return

    verified: list[str] = []
    failures: list[str] = []

    for path in databases:
        try:
            connection = sqlite3.connect(
                str(path),
                timeout=10,
            )

            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            connection.close()

            relative = str(
                path.relative_to(ROOT)
            )

            if result and result[0] == "ok":
                verified.append(relative)
            else:
                failures.append(
                    f"{relative}: {result}"
                )

        except sqlite3.Error as exc:
            failures.append(
                f"{path}: {exc}"
            )

    if failures:
        add_check(
            checks,
            "Database",
            "SQLite integrity",
            "FAIL",
            f"{len(failures)} database bermasalah.",
            failures,
        )
    else:
        add_check(
            checks,
            "Database",
            "SQLite integrity",
            "PASS",
            f"{len(verified)} database lulus quick_check.",
            verified,
        )


def check_acceptance(
    checks: list[dict[str, Any]],
) -> None:
    path = (
        ROOT
        / "storage"
        / "acceptance"
        / "reports"
        / "latest_report.json"
    )

    if not path.exists():
        add_check(
            checks,
            "Acceptance",
            "Laporan terakhir",
            "FAIL",
            "Laporan acceptance belum tersedia.",
        )
        return

    try:
        report = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        add_check(
            checks,
            "Acceptance",
            "Laporan terakhir",
            "FAIL",
            f"Laporan tidak dapat dibaca: {exc}",
        )
        return

    summary = report.get(
        "summary",
        {},
    )

    fail_count = int(
        summary.get(
            "fail",
            999,
        )
    )

    score = int(
        summary.get(
            "score",
            0,
        )
    )

    readiness = str(
        summary.get(
            "readiness",
            "UNKNOWN",
        )
    )

    acceptance_ready = (
        fail_count == 0
        and score == 100
        and readiness == "READY"
    )

    if acceptance_ready:
        add_check(
            checks,
            "Acceptance",
            "Laporan terakhir",
            "PASS",
            "Acceptance READY dengan skor 100/100.",
        )
    else:
        add_check(
            checks,
            "Acceptance",
            "Laporan terakhir",
            "FAIL",
            (
                f"Acceptance belum memenuhi syarat: "
                f"{readiness}, score {score}, fail {fail_count}."
            ),
            summary,
        )


def check_application(
    checks: list[dict[str, Any]],
) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(
            0,
            str(ROOT),
        )

    try:
        module = importlib.import_module(
            "app"
        )

        app = module.app

    except Exception as exc:
        add_check(
            checks,
            "Application",
            "Import FastAPI",
            "FAIL",
            str(exc),
        )
        return

    add_check(
        checks,
        "Application",
        "Import FastAPI",
        "PASS",
        "Objek FastAPI berhasil diimpor.",
    )

    available_routes = {
        getattr(route, "path", "")
        for route in getattr(
            app,
            "routes",
            [],
        )
    }

    missing_routes = sorted(
        REQUIRED_ROUTES
        - available_routes
    )

    if missing_routes:
        add_check(
            checks,
            "Routing",
            "Route wajib",
            "FAIL",
            f"{len(missing_routes)} route belum tersedia.",
            missing_routes,
        )
    else:
        add_check(
            checks,
            "Routing",
            "Route wajib",
            "PASS",
            f"Seluruh {len(REQUIRED_ROUTES)} route tersedia.",
        )

    middleware_names = [
        middleware.cls.__name__
        for middleware in getattr(
            app,
            "user_middleware",
            [],
        )
    ]

    duplicates = {
        name: count
        for name, count in Counter(
            middleware_names
        ).items()
        if count > 1
    }

    if duplicates:
        add_check(
            checks,
            "Middleware",
            "Duplikasi middleware",
            "FAIL",
            "Ditemukan middleware ganda.",
            duplicates,
        )
    else:
        add_check(
            checks,
            "Middleware",
            "Duplikasi middleware",
            "PASS",
            (
                f"{len(middleware_names)} middleware "
                "terpasang tanpa duplikasi."
            ),
            middleware_names,
        )


def check_local_secrets(
    checks: list[dict[str, Any]],
) -> None:
    candidates = [
        "LOCAL_ADMIN.txt",
        ".env",
        ".env.production",
    ]

    existing = [
        name
        for name in candidates
        if (ROOT / name).exists()
    ]

    if existing:
        add_check(
            checks,
            "Security",
            "File lokal sensitif",
            "WARNING",
            (
                "File lokal sensitif ditemukan, tetapi "
                "akan dikecualikan dari paket release."
            ),
            existing,
        )
    else:
        add_check(
            checks,
            "Security",
            "File lokal sensitif",
            "PASS",
            "Tidak ditemukan file lokal sensitif.",
        )


def summarize(
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    counter = Counter(
        item["status"]
        for item in checks
    )

    fail_count = int(
        counter.get(
            "FAIL",
            0,
        )
    )

    return {
        "total": len(checks),
        "pass": int(
            counter.get(
                "PASS",
                0,
            )
        ),
        "fail": fail_count,
        "warning": int(
            counter.get(
                "WARNING",
                0,
            )
        ),
        "status": (
            "READY"
            if fail_count == 0
            else "NOT READY"
        ),
        "ready": fail_count == 0,
    }


def run_preflight() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    check_required_files(checks)
    check_python_sources(checks)
    check_databases(checks)
    check_acceptance(checks)
    check_application(checks)
    check_local_secrets(checks)

    report = {
        "generated_at": utc_now(),
        "version": VERSION,
        "summary": summarize(checks),
        "checks": checks,
    }

    report_path = (
        RELEASE_DIR
        / "latest_preflight.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return report


def print_preflight(
    report: dict[str, Any],
) -> None:
    print("")
    print("DOCURAPI PRODUCTION PREFLIGHT")
    print("------------------------------------------------------------")

    for item in report["checks"]:
        print(
            f"{item['status']:<8} "
            f"{item['category']} - "
            f"{item['name']}: "
            f"{item['detail']}"
        )

    summary = report["summary"]

    print("")
    print("Status  :", summary["status"])
    print("PASS    :", summary["pass"])
    print("FAIL    :", summary["fail"])
    print("WARNING :", summary["warning"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def release_file_is_excluded(
    path: Path,
) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return True

    lowered_parts = [
        part.lower()
        for part in relative.parts
    ]

    if any(
        part in EXCLUDED_DIRECTORY_NAMES
        for part in lowered_parts
    ):
        return True

    if any(
        part.startswith("_backup_")
        for part in lowered_parts
    ):
        return True

    if path.name in EXCLUDED_RELEASE_FILES:
        return True

    if path.suffix.lower() in EXCLUDED_RELEASE_SUFFIXES:
        return True

    lowered_name = path.name.lower()

    if lowered_name.endswith(".db-wal"):
        return True

    if lowered_name.endswith(".db-shm"):
        return True

    if "_before_" in lowered_name:
        return True

    if "before_fix" in lowered_name:
        return True

    if "before_startup" in lowered_name:
        return True

    return False


def collect_release_files() -> list[Path]:
    files: list[Path] = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if release_file_is_excluded(path):
            continue

        files.append(path)

    return sorted(
        files,
        key=lambda item: str(item),
    )


def build_release() -> dict[str, Any]:
    preflight = run_preflight()

    if not preflight["summary"]["ready"]:
        raise RuntimeError(
            "Production preflight belum READY."
        )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    archive_name = (
        "DocuRapi_5_0_0_rc1_"
        + timestamp
        + ".zip"
    )

    archive_path = (
        RELEASE_DIR
        / archive_name
    )

    files = collect_release_files()

    package_contents = {
        "version": VERSION,
        "built_at": utc_now(),
        "file_count": len(files),
        "excluded": {
            "storage": True,
            "database": True,
            "credentials": True,
            "environment": True,
            "virtual_environment": True,
            "source_backups": True,
        },
        "files": [
            path.relative_to(ROOT).as_posix()
            for path in files
        ],
    }

    with ZipFile(
        archive_path,
        "w",
        ZIP_DEFLATED,
    ) as archive:
        for path in files:
            archive.write(
                path,
                path.relative_to(ROOT),
            )

        archive.writestr(
            "PACKAGE_CONTENTS.json",
            json.dumps(
                package_contents,
                ensure_ascii=False,
                indent=2,
            ),
        )

    checksum = sha256_file(
        archive_path
    )

    manifest = {
        "version": VERSION,
        "built_at": utc_now(),
        "archive": archive_path.name,
        "archive_path": str(
            archive_path
        ),
        "file_count": len(files),
        "size_bytes": (
            archive_path.stat().st_size
        ),
        "sha256": checksum,
        "preflight": preflight["summary"],
    }

    manifest_path = (
        RELEASE_DIR
        / (
            archive_path.stem
            + ".manifest.json"
        )
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    checksum_path = (
        RELEASE_DIR
        / (
            archive_path.name
            + ".sha256"
        )
    )

    checksum_path.write_text(
        (
            checksum
            + "  "
            + archive_path.name
            + "\n"
        ),
        encoding="utf-8",
    )

    manifest["manifest_path"] = str(
        manifest_path
    )

    manifest["checksum_path"] = str(
        checksum_path
    )

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "DocuRapi Release Candidate Tool."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    preflight_parser = subparsers.add_parser(
        "preflight"
    )

    preflight_parser.add_argument(
        "--strict",
        action="store_true",
    )

    subparsers.add_parser(
        "build"
    )

    arguments = parser.parse_args()

    if arguments.command == "preflight":
        report = run_preflight()

        print_preflight(report)

        if (
            arguments.strict
            and not report["summary"]["ready"]
        ):
            raise SystemExit(1)

    elif arguments.command == "build":
        result = build_release()

        print("")
        print("DOCURAPI RELEASE PACKAGE")
        print("------------------------------------------------------------")
        print("Version  :", result["version"])
        print("Archive  :", result["archive_path"])
        print("Manifest :", result["manifest_path"])
        print("SHA-256  :", result["sha256"])
        print("Files    :", result["file_count"])
        print("")
        print("RELEASE_PACKAGE_BUILD_PASSED")


if __name__ == "__main__":
    main()

from __future__ import annotations

import html as html_module
import json
import os
import re
from services import database_adapter as sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(
    __file__
).resolve().parents[1]

REPORT_DIR = (
    ROOT
    / "storage"
    / "readiness"
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LATEST_JSON = (
    REPORT_DIR
    / "latest_report.json"
)

LATEST_TEXT = (
    REPORT_DIR
    / "latest_report.txt"
)

LATEST_HTML = (
    REPORT_DIR
    / "latest_report.html"
)


EXCLUDED_DIRECTORIES = {
    ".venv",
    ".git",
    "__pycache__",
    "storage",
    "releases",
    "release",
    "dist",
    "build",
    "node_modules",
}


PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "replace-me",
    "replace-with-strong-password",
    "ganti-dengan-secret-kuat",
    "ganti-dengan-password-kuat",
    "local-development-secret",
    "secret",
    "password",
    "your-secret",
}


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def add_result(
    results: list[dict[str, Any]],
    category: str,
    name: str,
    status: str,
    detail: str,
    action: str = "",
) -> None:
    results.append(
        {
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
            "action": action,
        }
    )


def parse_environment_file(
    path: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}

    if not path.exists():
        return values

    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    for raw_line in content.splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        name, value = line.split(
            "=",
            1,
        )

        values[
            name.strip()
        ] = value.strip().strip(
            '"'
        ).strip(
            "'"
        )

    return values


def load_environment() -> tuple[
    dict[str, str],
    list[str],
]:
    candidates = [
        ROOT / ".env.production",
        ROOT / ".env",
        ROOT / "infra" / ".env",
        ROOT / ".env.production.example",
    ]

    merged: dict[str, str] = {}
    loaded_files: list[str] = []

    for path in candidates:
        values = parse_environment_file(
            path
        )

        if not values:
            continue

        loaded_files.append(
            str(path)
        )

        for name, value in values.items():
            if (
                name not in merged
                or not merged[name]
            ):
                merged[name] = value

    for name, value in os.environ.items():
        if name.startswith(
            "DOCURAPI_"
        ):
            merged[name] = value

    return merged, loaded_files


def project_python_files() -> list[Path]:
    files: list[Path] = []

    for path in ROOT.rglob(
        "*.py"
    ):
        relative_parts = path.relative_to(
            ROOT
        ).parts

        if any(
            part in EXCLUDED_DIRECTORIES
            or part.startswith(
                "_backup_"
            )
            for part in relative_parts
        ):
            continue

        files.append(path)

    return sorted(files)


def check_python(
    results: list[dict[str, Any]],
) -> None:
    files = project_python_files()

    if not files:
        add_result(
            results,
            "Code",
            "Python source",
            "BLOCKER",
            "Tidak ditemukan source Python.",
        )

        return

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            *[
                str(path)
                for path in files
            ],
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if process.returncode == 0:
        add_result(
            results,
            "Code",
            "Python syntax",
            "PASS",
            (
                f"{len(files)} file Python "
                "berhasil dikompilasi."
            ),
        )
    else:
        detail = (
            process.stderr.strip()
            or process.stdout.strip()
            or "Python compilation failed."
        )

        add_result(
            results,
            "Code",
            "Python syntax",
            "BLOCKER",
            detail[-3000:],
            "Perbaiki syntax sebelum pengujian berikutnya.",
        )

    import_code = """
from app import app
print(len(app.routes))
print(len(app.user_middleware))
"""

    import_process = subprocess.run(
        [
            sys.executable,
            "-c",
            import_code,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if import_process.returncode == 0:
        lines = [
            line.strip()
            for line in import_process.stdout.splitlines()
            if line.strip()
        ]

        route_count = (
            lines[-2]
            if len(lines) >= 2
            else "unknown"
        )

        middleware_count = (
            lines[-1]
            if lines
            else "unknown"
        )

        add_result(
            results,
            "Code",
            "FastAPI import",
            "PASS",
            (
                f"app.py berhasil diimpor. "
                f"Routes: {route_count}; "
                f"middleware: {middleware_count}."
            ),
        )
    else:
        detail = (
            import_process.stderr.strip()
            or import_process.stdout.strip()
        )

        add_result(
            results,
            "Code",
            "FastAPI import",
            "BLOCKER",
            detail[-3000:],
            "Perbaiki error import atau binding router.",
        )


def check_databases(
    results: list[dict[str, Any]],
) -> None:
    storage = ROOT / "storage"

    database_files = sorted(
        storage.rglob("*.db")
    ) if storage.exists() else []

    if not database_files:
        add_result(
            results,
            "Database",
            "SQLite databases",
            "WARN",
            "Belum ditemukan file database SQLite.",
        )

        return

    failed: list[str] = []

    for database_path in database_files:
        try:
            connection = sqlite3.connect(
                database_path
            )

            row = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            connection.close()

            if (
                not row
                or row[0] != "ok"
            ):
                failed.append(
                    (
                        f"{database_path.name}: "
                        f"{row[0] if row else 'no result'}"
                    )
                )

        except Exception as exc:
            failed.append(
                (
                    f"{database_path.name}: "
                    f"{exc}"
                )
            )

    if failed:
        add_result(
            results,
            "Database",
            "SQLite integrity",
            "BLOCKER",
            "; ".join(failed),
            "Pulihkan database dari backup sebelum deployment.",
        )
    else:
        add_result(
            results,
            "Database",
            "SQLite integrity",
            "PASS",
            (
                f"{len(database_files)} database "
                "lulus PRAGMA quick_check."
            ),
        )


def check_acceptance(
    results: list[dict[str, Any]],
) -> None:
    candidates = [
        (
            ROOT
            / "storage"
            / "acceptance"
            / "reports"
            / "latest_report.json"
        ),
        (
            ROOT
            / "storage"
            / "acceptance"
            / "latest_report.json"
        ),
    ]

    report_path = next(
        (
            path
            for path in candidates
            if path.exists()
        ),
        None,
    )

    if not report_path:
        add_result(
            results,
            "Quality",
            "Acceptance report",
            "WARN",
            "Laporan Acceptance Test terbaru tidak ditemukan.",
            "Jalankan Acceptance Test lengkap.",
        )

        return

    try:
        report = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        add_result(
            results,
            "Quality",
            "Acceptance report",
            "BLOCKER",
            f"Laporan tidak dapat dibaca: {exc}",
        )

        return

    summary = report.get(
        "summary",
        {}
    )

    fail = int(
        summary.get(
            "fail",
            summary.get(
                "failed",
                0,
            ),
        )
        or 0
    )

    score = summary.get(
        "score"
    )

    readiness = summary.get(
        "readiness",
        "UNKNOWN",
    )

    if fail > 0:
        add_result(
            results,
            "Quality",
            "Acceptance report",
            "BLOCKER",
            (
                f"Readiness={readiness}; "
                f"score={score}; FAIL={fail}."
            ),
            "Perbaiki seluruh hasil FAIL.",
        )
    else:
        add_result(
            results,
            "Quality",
            "Acceptance report",
            "PASS",
            (
                f"Readiness={readiness}; "
                f"score={score}; FAIL=0."
            ),
        )


def check_manifest(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest_path = (
        ROOT
        / "FEATURE_MANIFEST.json"
    )

    if not manifest_path.exists():
        add_result(
            results,
            "Release",
            "Feature manifest",
            "WARN",
            "FEATURE_MANIFEST.json tidak ditemukan.",
        )

        return {}

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        add_result(
            results,
            "Release",
            "Feature manifest",
            "BLOCKER",
            f"Manifest tidak valid: {exc}",
        )

        return {}

    add_result(
        results,
        "Release",
        "Feature manifest",
        "PASS",
        (
            f"Versi {manifest.get('version', 'unknown')}; "
            f"package {manifest.get('package', 'unknown')}."
        ),
    )

    return manifest


def check_runtime_errors(
    results: list[dict[str, Any]],
) -> None:
    search_roots = [
        ROOT / "logs",
        ROOT / "storage" / "server_logs",
        ROOT / "storage" / "logs",
    ]

    patterns = [
        "expected a bytes-like object, tuple found",
        "sequence item 1",
    ]

    matches: list[str] = []

    for search_root in search_roots:
        if not search_root.exists():
            continue

        for path in search_root.rglob("*"):
            if (
                not path.is_file()
                or path.suffix.lower()
                not in {
                    ".log",
                    ".txt",
                    ".out",
                    ".err",
                }
            ):
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                continue

            lowered = content.lower()

            if any(
                pattern in lowered
                for pattern in patterns
            ):
                relevant_lines = [
                    line.strip()
                    for line in content.splitlines()
                    if (
                        "bytes-like object" in line.lower()
                        or "sequence item" in line.lower()
                    )
                ]

                preview = (
                    relevant_lines[-1]
                    if relevant_lines
                    else "error ditemukan"
                )

                matches.append(
                    (
                        f"{path.relative_to(ROOT)}: "
                        f"{preview}"
                    )
                )

    if matches:
        add_result(
            results,
            "Runtime",
            "Document processing error",
            "BLOCKER",
            " | ".join(matches[-5:]),
            (
                "Perbaiki error tuple/bytes sebelum "
                "menguji dokumen nyata."
            ),
        )
    else:
        add_result(
            results,
            "Runtime",
            "Document processing error",
            "PASS",
            (
                "Error tuple/bytes tidak ditemukan "
                "pada log yang tersedia."
            ),
        )


def check_environment(
    results: list[dict[str, Any]],
    environment: dict[str, str],
    loaded_files: list[str],
    manifest: dict[str, Any],
) -> None:
    production_path = (
        ROOT
        / ".env.production"
    )

    if production_path.exists():
        add_result(
            results,
            "Configuration",
            "Production environment",
            "PASS",
            (
                ".env.production tersedia dan "
                "tidak ditampilkan dalam laporan."
            ),
        )
    else:
        add_result(
            results,
            "Configuration",
            "Production environment",
            "BLOCKER",
            ".env.production belum tersedia.",
            (
                "Buat konfigurasi production terpisah "
                "dari development."
            ),
        )

    public_url = environment.get(
        "DOCURAPI_PUBLIC_BASE_URL",
        "",
    )

    if (
        public_url.startswith("https://")
        and "127.0.0.1" not in public_url
        and "localhost" not in public_url
    ):
        add_result(
            results,
            "Deployment",
            "Public URL and HTTPS",
            "PASS",
            public_url,
        )
    else:
        add_result(
            results,
            "Deployment",
            "Public URL and HTTPS",
            "BLOCKER",
            (
                public_url
                or "Public base URL belum dikonfigurasi."
            ),
            "Siapkan domain publik dan HTTPS.",
        )

    database_url = (
        environment.get(
            "DOCURAPI_DATABASE_URL"
        )
        or environment.get(
            "DATABASE_URL",
            "",
        )
    )

    if database_url.startswith(
        (
            "postgresql://",
            "postgresql+",
            "postgres://",
        )
    ):
        add_result(
            results,
            "Infrastructure",
            "Production database",
            "PASS",
            "Konfigurasi PostgreSQL ditemukan.",
        )
    else:
        add_result(
            results,
            "Infrastructure",
            "Production database",
            "BLOCKER",
            (
                "Database produksi belum menggunakan PostgreSQL."
            ),
            (
                "Siapkan migrasi SQLite ke PostgreSQL "
                "dengan validasi jumlah data."
            ),
        )

    payment_mode = environment.get(
        "DOCURAPI_PAYMENT_MODE",
        "simulation",
    ).lower()

    features = manifest.get(
        "features",
        {}
    )

    real_gateway = bool(
        features.get(
            "real_payment_gateway",
            False,
        )
    )

    if (
        payment_mode in {
            "gateway",
            "production",
            "live",
        }
        and real_gateway
    ):
        add_result(
            results,
            "Billing",
            "Real payment gateway",
            "PASS",
            (
                f"Payment mode={payment_mode}; "
                "gateway ditandai aktif."
            ),
        )
    else:
        add_result(
            results,
            "Billing",
            "Real payment gateway",
            "BLOCKER",
            (
                f"Payment mode={payment_mode}; "
                f"real gateway={real_gateway}."
            ),
            (
                "Integrasikan Midtrans atau Xendit "
                "beserta webhook terverifikasi."
            ),
        )

    secret_names = [
        "DOCURAPI_SECRET_KEY",
        "DOCURAPI_SESSION_SECRET",
        "SESSION_SECRET",
        "SECRET_KEY",
    ]

    configured_secrets = [
        environment.get(name, "")
        for name in secret_names
        if environment.get(name)
    ]

    strong_secret = any(
        len(secret) >= 32
        and secret.lower()
        not in PLACEHOLDER_VALUES
        for secret in configured_secrets
    )

    if strong_secret:
        add_result(
            results,
            "Security",
            "Application secret",
            "PASS",
            "Secret aplikasi dengan panjang memadai ditemukan.",
        )
    else:
        add_result(
            results,
            "Security",
            "Application secret",
            "BLOCKER",
            (
                "Secret aplikasi belum ada, terlalu pendek, "
                "atau masih placeholder."
            ),
            "Gunakan random secret minimal 32 karakter.",
        )

    webhook_secret = environment.get(
        "DOCURAPI_PAYMENT_WEBHOOK_SECRET",
        "",
    )

    if (
        len(webhook_secret) >= 32
        and webhook_secret.lower()
        not in PLACEHOLDER_VALUES
    ):
        add_result(
            results,
            "Security",
            "Payment webhook secret",
            "PASS",
            "Webhook secret terlihat memadai.",
        )
    else:
        add_result(
            results,
            "Security",
            "Payment webhook secret",
            "WARN",
            (
                "Webhook secret belum memadai untuk "
                "payment gateway live."
            ),
        )

    dev_mode = environment.get(
        "DOCURAPI_DEV_MODE",
        "0",
    ).lower()

    debug_mode = environment.get(
        "DEBUG",
        "false",
    ).lower()

    if (
        dev_mode in {
            "0",
            "false",
            "off",
        }
        and debug_mode in {
            "0",
            "false",
            "off",
            "",
        }
    ):
        add_result(
            results,
            "Security",
            "Debug mode",
            "PASS",
            "Development/debug mode tidak aktif.",
        )
    else:
        add_result(
            results,
            "Security",
            "Debug mode",
            "BLOCKER",
            (
                f"DOCURAPI_DEV_MODE={dev_mode}; "
                f"DEBUG={debug_mode}."
            ),
            "Matikan debug pada production.",
        )

    redis_url = environment.get(
        "DOCURAPI_REDIS_URL",
        "",
    )

    if (
        redis_url
        and "127.0.0.1" not in redis_url
        and "localhost" not in redis_url
    ):
        add_result(
            results,
            "Infrastructure",
            "Redis queue",
            "PASS",
            "Redis production dikonfigurasi.",
        )
    else:
        add_result(
            results,
            "Infrastructure",
            "Redis queue",
            "WARN",
            (
                "Redis production belum dikonfigurasi. "
                "Worker masih berisiko bergantung pada proses web."
            ),
        )

    object_endpoint = environment.get(
        "DOCURAPI_OBJECT_STORAGE_ENDPOINT",
        "",
    )

    if (
        object_endpoint
        and "127.0.0.1" not in object_endpoint
        and "localhost" not in object_endpoint
    ):
        add_result(
            results,
            "Infrastructure",
            "Object storage",
            "PASS",
            "Object storage eksternal dikonfigurasi.",
        )
    else:
        add_result(
            results,
            "Infrastructure",
            "Object storage",
            "WARN",
            (
                "Penyimpanan file masih lokal atau "
                "endpoint belum tersedia."
            ),
        )

    smtp_host = environment.get(
        "DOCURAPI_SMTP_HOST",
        environment.get(
            "SMTP_HOST",
            "",
        ),
    )

    smtp_user = environment.get(
        "DOCURAPI_SMTP_USER",
        environment.get(
            "SMTP_USER",
            "",
        ),
    )

    if smtp_host and smtp_user:
        add_result(
            results,
            "Communication",
            "SMTP email",
            "PASS",
            "SMTP production dikonfigurasi.",
        )
    else:
        add_result(
            results,
            "Communication",
            "SMTP email",
            "WARN",
            (
                "Email masih lokal atau SMTP "
                "belum dikonfigurasi."
            ),
        )

    if loaded_files:
        add_result(
            results,
            "Configuration",
            "Environment sources",
            "PASS",
            (
                f"{len(loaded_files)} sumber environment "
                "berhasil dibaca."
            ),
        )


def check_source_security(
    results: list[dict[str, Any]],
) -> None:
    app_path = ROOT / "app.py"

    if not app_path.exists():
        return

    content = app_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    wildcard_patterns = [
        r"allow_origins\s*=\s*\[\s*[\"']\*[\"']",
        r"allow_origin_regex\s*=\s*[\"']\.\*[\"']",
    ]

    wildcard_found = any(
        re.search(
            pattern,
            content,
            re.IGNORECASE,
        )
        for pattern in wildcard_patterns
    )

    if wildcard_found:
        add_result(
            results,
            "Security",
            "CORS policy",
            "BLOCKER",
            "CORS wildcard ditemukan pada app.py.",
            (
                "Batasi origin hanya ke domain "
                "frontend resmi."
            ),
        )
    else:
        add_result(
            results,
            "Security",
            "CORS policy",
            "PASS",
            "CORS wildcard eksplisit tidak ditemukan.",
        )

    gitignore_path = ROOT / ".gitignore"

    if gitignore_path.exists():
        gitignore = gitignore_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        missing = [
            rule
            for rule in [
                ".env.production",
                "infra/.env",
            ]
            if rule not in gitignore
        ]

        if missing:
            add_result(
                results,
                "Security",
                "Secret file protection",
                "WARN",
                (
                    "Aturan .gitignore belum mencakup: "
                    + ", ".join(missing)
                ),
            )
        else:
            add_result(
                results,
                "Security",
                "Secret file protection",
                "PASS",
                (
                    "File environment rahasia "
                    "tercantum di .gitignore."
                ),
            )
    else:
        add_result(
            results,
            "Security",
            "Secret file protection",
            "BLOCKER",
            ".gitignore tidak ditemukan.",
        )


def check_backups(
    results: list[dict[str, Any]],
) -> None:
    backups = [
        path
        for path in ROOT.iterdir()
        if (
            path.is_dir()
            and path.name.startswith(
                "_backup_"
            )
        )
    ]

    if backups:
        add_result(
            results,
            "Operations",
            "Source backups",
            "PASS",
            (
                f"{len(backups)} folder backup "
                "lokal ditemukan."
            ),
        )
    else:
        add_result(
            results,
            "Operations",
            "Source backups",
            "WARN",
            "Belum ditemukan backup source lokal.",
        )

    backup_storage = (
        ROOT
        / "storage"
        / "backups"
    )

    if (
        backup_storage.exists()
        and any(
            backup_storage.rglob("*")
        )
    ):
        add_result(
            results,
            "Operations",
            "Data backups",
            "PASS",
            "Backup data aplikasi ditemukan.",
        )
    else:
        add_result(
            results,
            "Operations",
            "Data backups",
            "WARN",
            (
                "Backup data terjadwal belum dapat "
                "dikonfirmasi."
            ),
        )


def calculate_summary(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers = sum(
        1
        for item in results
        if item["status"] == "BLOCKER"
    )

    warnings = sum(
        1
        for item in results
        if item["status"] == "WARN"
    )

    passed = sum(
        1
        for item in results
        if item["status"] == "PASS"
    )

    score = max(
        0,
        100
        - blockers * 10
        - warnings * 2,
    )

    if blockers == 0:
        readiness = (
            "READY_FOR_STAGING"
            if warnings <= 3
            else "STAGING_WITH_WARNINGS"
        )
    else:
        readiness = "NOT_READY_FOR_PUBLIC_SAAS"

    return {
        "readiness": readiness,
        "score": score,
        "pass": passed,
        "warning": warnings,
        "blocker": blockers,
        "total": len(results),
    }


def write_reports(
    report: dict[str, Any],
) -> None:
    LATEST_JSON.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]

    text_lines = [
        "DOCURAPI SAAS READINESS REPORT",
        "",
        (
            "Readiness : "
            + str(
                summary["readiness"]
            )
        ),
        (
            "Score     : "
            + str(
                summary["score"]
            )
            + "/100"
        ),
        (
            "PASS      : "
            + str(
                summary["pass"]
            )
        ),
        (
            "WARNING   : "
            + str(
                summary["warning"]
            )
        ),
        (
            "BLOCKER   : "
            + str(
                summary["blocker"]
            )
        ),
        "",
    ]

    for status in [
        "BLOCKER",
        "WARN",
        "PASS",
    ]:
        text_lines.append(status)
        text_lines.append(
            "-" * len(status)
        )

        for item in report["results"]:
            if item["status"] != status:
                continue

            text_lines.append(
                (
                    f"[{item['category']}] "
                    f"{item['name']}: "
                    f"{item['detail']}"
                )
            )

            if item.get("action"):
                text_lines.append(
                    (
                        "  Tindakan: "
                        + item["action"]
                    )
                )

        text_lines.append("")

    LATEST_TEXT.write_text(
        "\n".join(text_lines),
        encoding="utf-8",
    )

    status_styles = {
        "PASS": (
            "background:#e6f5ef;"
            "color:#086248;"
        ),
        "WARN": (
            "background:#fff4d6;"
            "color:#805913;"
        ),
        "BLOCKER": (
            "background:#fdeaea;"
            "color:#a62828;"
        ),
    }

    cards = []

    ordered_results = sorted(
        report["results"],
        key=lambda item: {
            "BLOCKER": 0,
            "WARN": 1,
            "PASS": 2,
        }.get(
            item["status"],
            3,
        ),
    )

    for item in ordered_results:
        action_html = ""

        if item.get("action"):
            action_html = (
                "<p class='action'><strong>Tindakan:</strong> "
                + html_module.escape(
                    item["action"]
                )
                + "</p>"
            )

        cards.append(
            """
            <article class="check-card">
                <div class="check-heading">
                    <div>
                        <small>{category}</small>
                        <h3>{name}</h3>
                    </div>
                    <span style="{style}">
                        {status}
                    </span>
                </div>
                <p>{detail}</p>
                {action}
            </article>
            """.format(
                category=html_module.escape(
                    item["category"]
                ),
                name=html_module.escape(
                    item["name"]
                ),
                style=status_styles[
                    item["status"]
                ],
                status=item["status"],
                detail=html_module.escape(
                    item["detail"]
                ),
                action=action_html,
            )
        )

    html_content = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>DocuRapi SaaS Readiness</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: #f2f7f6;
            color: #172326;
            font-family: "Segoe UI", Arial, sans-serif;
        }}

        main {{
            width: min(1100px, calc(100% - 32px));
            margin: 32px auto 80px;
        }}

        .hero {{
            padding: 28px;
            border-radius: 20px;
            background: #0f6b5d;
            color: white;
        }}

        .hero h1 {{
            margin: 0 0 8px;
        }}

        .summary {{
            margin-top: 18px;
            display: grid;
            grid-template-columns:
                repeat(5, minmax(0, 1fr));
            gap: 12px;
        }}

        .summary div {{
            padding: 16px;
            border-radius: 14px;
            background: white;
            color: #172326;
        }}

        .summary span,
        .summary strong {{
            display: block;
        }}

        .summary span {{
            color: #68787c;
            font-size: 12px;
        }}

        .summary strong {{
            margin-top: 5px;
            font-size: 22px;
        }}

        .checks {{
            margin-top: 20px;
            display: grid;
            gap: 12px;
        }}

        .check-card {{
            padding: 20px;
            border: 1px solid #dce7e4;
            border-radius: 15px;
            background: white;
        }}

        .check-heading {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
        }}

        .check-heading small {{
            color: #0f6b5d;
            font-weight: 800;
        }}

        .check-heading h3 {{
            margin: 4px 0 0;
        }}

        .check-heading span {{
            padding: 6px 9px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 900;
        }}

        .check-card p {{
            color: #68787c;
            line-height: 1.55;
        }}

        .check-card .action {{
            padding: 11px;
            border-radius: 9px;
            background: #f5f8f7;
            color: #33484c;
        }}

        @media (max-width: 760px) {{
            .summary {{
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }}
        }}
    </style>
</head>
<body>
    <main>
        <section class="hero">
            <p>DOCURAPI RELEASE GATE</p>
            <h1>{readiness}</h1>
            <p>
                Pemeriksaan ini tidak menyatakan aplikasi
                siap produksi selama masih terdapat BLOCKER.
            </p>
        </section>

        <section class="summary">
            <div>
                <span>Score</span>
                <strong>{score}/100</strong>
            </div>
            <div>
                <span>PASS</span>
                <strong>{passed}</strong>
            </div>
            <div>
                <span>WARNING</span>
                <strong>{warnings}</strong>
            </div>
            <div>
                <span>BLOCKER</span>
                <strong>{blockers}</strong>
            </div>
            <div>
                <span>Total Check</span>
                <strong>{total}</strong>
            </div>
        </section>

        <section class="checks">
            {cards}
        </section>
    </main>
</body>
</html>
""".format(
        readiness=html_module.escape(
            str(
                summary["readiness"]
            )
        ),
        score=summary["score"],
        passed=summary["pass"],
        warnings=summary["warning"],
        blockers=summary["blocker"],
        total=summary["total"],
        cards="\n".join(cards),
    )

    LATEST_HTML.write_text(
        html_content,
        encoding="utf-8",
    )


def run_readiness_audit() -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    if (ROOT / "app.py").exists():
        add_result(
            results,
            "Code",
            "Application entrypoint",
            "PASS",
            "app.py ditemukan.",
        )
    else:
        add_result(
            results,
            "Code",
            "Application entrypoint",
            "BLOCKER",
            "app.py tidak ditemukan.",
        )

    manifest = check_manifest(
        results
    )

    check_python(
        results
    )

    check_databases(
        results
    )

    check_acceptance(
        results
    )

    check_runtime_errors(
        results
    )

    environment, loaded_files = (
        load_environment()
    )

    check_environment(
        results,
        environment,
        loaded_files,
        manifest,
    )

    check_source_security(
        results
    )

    check_backups(
        results
    )

    summary = calculate_summary(
        results
    )

    report = {
        "generated_at": utc_now(),
        "project": "DocuRapi",
        "gate": "SaaS Readiness",
        "summary": summary,
        "results": results,
        "report_files": {
            "json": str(
                LATEST_JSON
            ),
            "text": str(
                LATEST_TEXT
            ),
            "html": str(
                LATEST_HTML
            ),
        },
    }

    write_reports(
        report
    )

    return report

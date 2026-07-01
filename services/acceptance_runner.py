from __future__ import annotations

import asyncio
import html
import importlib
import inspect
import json
import py_compile
import re
from services import database_adapter as sqlite3
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from services.acceptance_factory import (
    ACCEPTANCE_DIR,
    FIXTURE_DIR,
    OUTPUT_DIR,
    create_acceptance_fixtures,
)


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_DIR = (
    ACCEPTANCE_DIR
    / "reports"
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LATEST_JSON = (
    REPORT_DIR
    / "latest_report.json"
)

LATEST_HTML = (
    REPORT_DIR
    / "latest_report.html"
)

LATEST_MARKDOWN = (
    REPORT_DIR
    / "latest_report.md"
)


class AcceptanceRecorder:
    def __init__(self) -> None:
        self.results: list[
            dict[str, Any]
        ] = []

    def add(
        self,
        category: str,
        name: str,
        status: str,
        detail: str,
        duration_ms: float = 0,
        evidence: Any = None,
    ) -> None:
        normalized_status = (
            status.upper().strip()
        )

        if normalized_status not in {
            "PASS",
            "FAIL",
            "WARNING",
            "SKIPPED",
        }:
            normalized_status = "WARNING"

        self.results.append(
            {
                "category": category,
                "name": name,
                "status": normalized_status,
                "detail": detail,
                "duration_ms": round(
                    float(duration_ms),
                    2,
                ),
                "evidence": evidence,
            }
        )


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def milliseconds_since(
    started: float,
) -> float:
    import time

    return (
        time.perf_counter()
        - started
    ) * 1000


def excluded_path(
    path: Path,
) -> bool:
    backup_name = path.name.lower()

    if (
        "_before_" in backup_name
        or "before_fix" in backup_name
        or "before_startup" in backup_name
        or backup_name.endswith(".backup.py")
    ):
        return True

    try:
        relative = path.resolve().relative_to(
            BASE_DIR.resolve()
        )
    except ValueError:
        return True

    excluded_names = {
        ".venv",
        "__pycache__",
        "storage",
        ".git",
    }

    for part in relative.parts:
        if part in excluded_names:
            return True

        if part.startswith(
            "_backup_"
        ):
            return True

    return False


def check_required_files(
    recorder: AcceptanceRecorder,
) -> None:
    required = [
        "app.py",
        "config.py",
        "database.py",
        "formatter.py",
        "templates",
        "static",
        "services",
        "FEATURE_MANIFEST.json",
        "saas_database.py",
        "workspace_database.py",
        "background_database.py",
        "system_database.py",
    ]

    for item in required:
        path = BASE_DIR / item

        if path.exists():
            recorder.add(
                "Struktur Proyek",
                item,
                "PASS",
                "File atau folder tersedia.",
            )
        else:
            recorder.add(
                "Struktur Proyek",
                item,
                "WARNING",
                "File atau folder tidak ditemukan.",
            )


def check_python_sources(
    recorder: AcceptanceRecorder,
) -> None:
    python_files = [
        path
        for path in BASE_DIR.rglob("*.py")
        if not excluded_path(path)
    ]

    failures: list[str] = []

    for path in python_files:
        try:
            py_compile.compile(
                str(path),
                doraise=True,
            )
        except Exception as exc:
            failures.append(
                f"{path.relative_to(BASE_DIR)}: {exc}"
            )

    if failures:
        recorder.add(
            "Source Code",
            "Kompilasi Python",
            "FAIL",
            (
                f"{len(failures)} file "
                "mengandung kesalahan sintaks."
            ),
            evidence=failures[:30],
        )
    else:
        recorder.add(
            "Source Code",
            "Kompilasi Python",
            "PASS",
            (
                f"{len(python_files)} file Python "
                "berhasil dikompilasi."
            ),
        )


def load_fastapi_app() -> Any:
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(
            0,
            str(BASE_DIR),
        )

    app_module = importlib.import_module(
        "app"
    )

    return app_module.app


def route_inventory(
    app: Any,
) -> list[dict[str, Any]]:
    inventory: list[
        dict[str, Any]
    ] = []

    for route in getattr(
        app,
        "routes",
        [],
    ):
        path = getattr(
            route,
            "path",
            None,
        )

        methods = getattr(
            route,
            "methods",
            None,
        )

        if not isinstance(path, str):
            continue

        inventory.append(
            {
                "path": path,
                "methods": sorted(
                    methods or []
                ),
                "name": getattr(
                    route,
                    "name",
                    "",
                ),
            }
        )

    return inventory


def check_routes_and_middleware(
    recorder: AcceptanceRecorder,
    app: Any,
) -> None:
    inventory = route_inventory(app)

    existing_paths = {
        item["path"]
        for item in inventory
    }

    required_paths = {
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

    missing = sorted(
        required_paths
        - existing_paths
    )

    if missing:
        recorder.add(
            "Routing",
            "Route wajib",
            "FAIL",
            (
                f"{len(missing)} route wajib "
                "belum tersedia."
            ),
            evidence=missing,
        )
    else:
        recorder.add(
            "Routing",
            "Route wajib",
            "PASS",
            (
                f"Seluruh {len(required_paths)} "
                "route wajib tersedia."
            ),
        )

    route_keys: list[
        tuple[str, str]
    ] = []

    for item in inventory:
        methods = (
            item["methods"]
            or ["ANY"]
        )

        for method in methods:
            route_keys.append(
                (
                    item["path"],
                    method,
                )
            )

    duplicates = [
        {
            "path": key[0],
            "method": key[1],
            "count": count,
        }
        for key, count in Counter(
            route_keys
        ).items()
        if count > 1
        and key[1] not in {
            "HEAD",
            "OPTIONS",
        }
    ]

    if duplicates:
        recorder.add(
            "Routing",
            "Konflik route",
            "WARNING",
            (
                f"Ditemukan {len(duplicates)} "
                "route dengan method ganda."
            ),
            evidence=duplicates,
        )
    else:
        recorder.add(
            "Routing",
            "Konflik route",
            "PASS",
            "Tidak ditemukan konflik route.",
        )

    middleware_names = [
        middleware.cls.__name__
        for middleware in getattr(
            app,
            "user_middleware",
            [],
        )
    ]

    duplicate_middleware = {
        name: count
        for name, count in Counter(
            middleware_names
        ).items()
        if count > 1
    }

    if duplicate_middleware:
        recorder.add(
            "Middleware",
            "Middleware ganda",
            "FAIL",
            "Middleware terpasang lebih dari satu kali.",
            evidence=duplicate_middleware,
        )
    else:
        recorder.add(
            "Middleware",
            "Middleware ganda",
            "PASS",
            (
                f"{len(middleware_names)} middleware "
                "terpasang tanpa duplikasi."
            ),
            evidence=middleware_names,
        )


def is_sqlite_database(
    path: Path,
) -> bool:
    try:
        with path.open("rb") as handle:
            return (
                handle.read(16)
                == b"SQLite format 3\x00"
            )
    except OSError:
        return False


def check_databases(
    recorder: AcceptanceRecorder,
) -> None:
    search_roots = [
        BASE_DIR / "storage",
        BASE_DIR / "database",
        BASE_DIR,
    ]

    discovered: set[Path] = set()

    for search_root in search_roots:
        if not search_root.exists():
            continue

        for candidate in search_root.rglob("*.db"):
            lowered_parts = [
                part.lower()
                for part in candidate.parts
            ]

            if ".venv" in lowered_parts:
                continue

            if "__pycache__" in lowered_parts:
                continue

            if "system_backups" in lowered_parts:
                continue

            if any(
                part.startswith("_backup_")
                for part in lowered_parts
            ):
                continue

            try:
                resolved = candidate.resolve()
            except OSError:
                continue

            if is_sqlite_database(resolved):
                discovered.add(resolved)

    database_paths = sorted(
        discovered,
        key=lambda item: str(item),
    )

    if not database_paths:
        recorder.add(
            "Database",
            "Deteksi SQLite",
            "FAIL",
            "Tidak ditemukan database SQLite aktif.",
        )

        return

    problems: list[str] = []
    checked: list[str] = []

    for database_path in database_paths:
        try:
            connection = sqlite3.connect(
                str(database_path),
                timeout=10,
            )

            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            connection.close()

            try:
                display_path = str(
                    database_path.relative_to(
                        BASE_DIR
                    )
                )
            except ValueError:
                display_path = str(database_path)

            checked.append(display_path)

            if (
                not result
                or result[0] != "ok"
            ):
                problems.append(
                    f"{display_path}: {result}"
                )

        except sqlite3.Error as exc:
            problems.append(
                f"{database_path}: {exc}"
            )

    if problems:
        recorder.add(
            "Database",
            "SQLite quick_check",
            "FAIL",
            (
                f"{len(problems)} database "
                "mengalami masalah."
            ),
            evidence=problems,
        )

    else:
        recorder.add(
            "Database",
            "SQLite quick_check",
            "PASS",
            (
                f"{len(database_paths)} database SQLite "
                "berhasil dideteksi dan diverifikasi."
            ),
            evidence=checked,
        )


def check_frontend_duplicates(
    recorder: AcceptanceRecorder,
) -> None:
    templates_directory = (
        BASE_DIR
        / "templates"
    )

    if not templates_directory.exists():
        recorder.add(
            "Frontend",
            "Template HTML",
            "FAIL",
            "Folder templates tidak tersedia.",
        )
        return

    duplicate_findings: list[
        dict[str, Any]
    ] = []

    markers = [
        "security_client.js",
        "background_client.js",
        'class="security-center-launch"',
        'class="workspace-launch"',
        'class="task-center-launch"',
        'class="system-health-launch"',
        'class="test-center-launch"',
    ]

    checked = 0

    for html_path in templates_directory.glob(
        "*.html"
    ):
        checked += 1

        content = html_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for marker in markers:
            count = content.count(marker)

            if count > 1:
                duplicate_findings.append(
                    {
                        "file": html_path.name,
                        "marker": marker,
                        "count": count,
                    }
                )

    if duplicate_findings:
        recorder.add(
            "Frontend",
            "Injeksi elemen ganda",
            "WARNING",
            (
                f"Ditemukan {len(duplicate_findings)} "
                "indikasi elemen atau script ganda."
            ),
            evidence=duplicate_findings,
        )
    else:
        recorder.add(
            "Frontend",
            "Injeksi elemen ganda",
            "PASS",
            (
                f"{checked} template diperiksa "
                "tanpa injeksi ganda."
            ),
        )


def resolve_callable(
    candidates: list[
        tuple[str, str]
    ],
) -> tuple[
    Callable[..., Any] | None,
    str | None,
]:
    errors: list[str] = []

    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(
                module_name
            )

            function = getattr(
                module,
                function_name,
                None,
            )

            if callable(function):
                return (
                    function,
                    (
                        f"{module_name}."
                        f"{function_name}"
                    ),
                )

        except Exception as exc:
            errors.append(
                (
                    f"{module_name}."
                    f"{function_name}: {exc}"
                )
            )

    return (
        None,
        "; ".join(errors),
    )


def execute_callable(
    function: Callable[..., Any],
    available_values: dict[str, Any],
) -> Any:
    signature = inspect.signature(
        function
    )

    arguments: dict[str, Any] = {}

    missing_required: list[str] = []

    for name, parameter in (
        signature.parameters.items()
    ):
        if name in available_values:
            arguments[name] = (
                available_values[name]
            )
            continue

        if (
            parameter.default
            is inspect.Parameter.empty
            and parameter.kind
            not in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
        ):
            missing_required.append(name)

    if missing_required:
        raise RuntimeError(
            "Parameter wajib tidak dikenali: "
            + ", ".join(
                missing_required
            )
        )

    result = function(
        **arguments
    )

    if inspect.isawaitable(result):
        return asyncio.run(result)

    return result


def check_document_services(
    recorder: AcceptanceRecorder,
    fixtures: dict[str, Any],
) -> None:
    academic_input = Path(
        fixtures["academic_document"]
    )

    formatted_output = (
        OUTPUT_DIR
        / "formatted_acceptance.docx"
    )

    journal_output = (
        OUTPUT_DIR
        / "journal_acceptance.docx"
    )

    common_values = {
        "input_path": str(
            academic_input
        ),
        "source_path": str(
            academic_input
        ),
        "document_path": str(
            academic_input
        ),
        "file_path": str(
            academic_input
        ),
        "path": str(
            academic_input
        ),
        "output_path": str(
            formatted_output
        ),
        "destination_path": str(
            formatted_output
        ),
        "preset": "skripsi",
        "preset_name": "skripsi",
        "custom_rules": {},
        "rules": {},
        "include_toc": False,
        "include_table_list": False,
        "include_figure_list": False,
        "include_appendix_list": False,
        "include_page_numbers": True,
    }

    formatter, formatter_name = resolve_callable(
        [
            (
                "final_formatter",
                "format_document",
            ),
            (
                "formatter",
                "format_document",
            ),
            (
                "services.final_formatter",
                "format_document",
            ),
        ]
    )

    if formatter:
        try:
            execute_callable(
                formatter,
                common_values,
            )

            if formatted_output.exists():
                recorder.add(
                    "Document Engine",
                    "Formatter",
                    "PASS",
                    (
                        "Formatter berhasil membuat "
                        "dokumen output."
                    ),
                    evidence={
                        "callable": formatter_name,
                        "output": str(
                            formatted_output
                        ),
                        "size_bytes": (
                            formatted_output
                            .stat()
                            .st_size
                        ),
                    },
                )
            else:
                recorder.add(
                    "Document Engine",
                    "Formatter",
                    "WARNING",
                    (
                        "Formatter selesai tanpa "
                        "menghasilkan file output standar."
                    ),
                    evidence={
                        "callable": formatter_name,
                    },
                )

        except Exception as exc:
            recorder.add(
                "Document Engine",
                "Formatter",
                "FAIL",
                str(exc),
                evidence=traceback.format_exc()[
                    -5000:
                ],
            )
    else:
        recorder.add(
            "Document Engine",
            "Formatter",
            "WARNING",
            (
                "Callable formatter tidak ditemukan "
                "dengan nama yang dikenali."
            ),
            evidence=formatter_name,
        )

    analyzer, analyzer_name = resolve_callable(
        [
            (
                "analyzer",
                "analyze_document",
            ),
            (
                "document_analyzer",
                "analyze_document",
            ),
            (
                "services.analyzer",
                "analyze_document",
            ),
            (
                "services.document_analyzer",
                "analyze_document",
            ),
        ]
    )

    if analyzer:
        try:
            result = execute_callable(
                analyzer,
                {
                    "path": str(
                        academic_input
                    ),
                    "input_path": str(
                        academic_input
                    ),
                    "document_path": str(
                        academic_input
                    ),
                    "file_path": str(
                        academic_input
                    ),
                },
            )

            if isinstance(result, dict):
                recorder.add(
                    "Document Engine",
                    "Analyzer",
                    "PASS",
                    (
                        "Analyzer mengembalikan "
                        "laporan berbentuk dictionary."
                    ),
                    evidence={
                        "callable": analyzer_name,
                        "keys": list(
                            result.keys()
                        )[:30],
                    },
                )
            else:
                recorder.add(
                    "Document Engine",
                    "Analyzer",
                    "WARNING",
                    (
                        "Analyzer berjalan tetapi "
                        "hasilnya bukan dictionary."
                    ),
                    evidence={
                        "callable": analyzer_name,
                        "result_type": (
                            type(result).__name__
                        ),
                    },
                )

        except Exception as exc:
            recorder.add(
                "Document Engine",
                "Analyzer",
                "FAIL",
                str(exc),
                evidence=traceback.format_exc()[
                    -5000:
                ],
            )
    else:
        recorder.add(
            "Document Engine",
            "Analyzer",
            "WARNING",
            (
                "Callable analyzer tidak ditemukan "
                "dengan nama yang dikenali."
            ),
            evidence=analyzer_name,
        )

    converter, converter_name = resolve_callable(
        [
            (
                "journal_converter",
                "convert_to_journal",
            ),
            (
                "services.journal_converter",
                "convert_to_journal",
            ),
            (
                "journal_formatter",
                "convert_to_journal",
            ),
        ]
    )

    if converter:
        try:
            execute_callable(
                converter,
                {
                    "input_path": str(
                        academic_input
                    ),
                    "source_path": str(
                        academic_input
                    ),
                    "output_path": str(
                        journal_output
                    ),
                    "destination_path": str(
                        journal_output
                    ),
                },
            )

            status = (
                "PASS"
                if journal_output.exists()
                else "WARNING"
            )

            recorder.add(
                "Document Engine",
                "Journal converter",
                status,
                (
                    "Konversi jurnal berhasil "
                    "menghasilkan file."
                    if journal_output.exists()
                    else (
                        "Converter berjalan tetapi "
                        "file output standar tidak ditemukan."
                    )
                ),
                evidence={
                    "callable": converter_name,
                    "output_exists": (
                        journal_output.exists()
                    ),
                },
            )

        except Exception as exc:
            recorder.add(
                "Document Engine",
                "Journal converter",
                "FAIL",
                str(exc),
                evidence=traceback.format_exc()[
                    -5000:
                ],
            )
    else:
        recorder.add(
            "Document Engine",
            "Journal converter",
            "WARNING",
            (
                "Callable journal converter tidak "
                "ditemukan dengan nama yang dikenali."
            ),
            evidence=converter_name,
        )


def parse_admin_credentials() -> tuple[
    str | None,
    str | None,
]:
    path = (
        BASE_DIR
        / "LOCAL_ADMIN.txt"
    )

    if not path.exists():
        return None, None

    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    email_match = re.search(
        r"Email\s*:\s*(\S+)",
        content,
        flags=re.IGNORECASE,
    )

    password_match = re.search(
        r"Kata sandi\s*:\s*(\S+)",
        content,
        flags=re.IGNORECASE,
    )

    return (
        (
            email_match.group(1)
            if email_match
            else None
        ),
        (
            password_match.group(1)
            if password_match
            else None
        ),
    )


def check_http_application(
    recorder: AcceptanceRecorder,
    app: Any,
) -> None:
    try:
        from fastapi.testclient import (
            TestClient,
        )
    except Exception as exc:
        recorder.add(
            "HTTP",
            "FastAPI TestClient",
            "FAIL",
            str(exc),
        )
        return

    public_paths = [
        "/",
        "/login",
        "/register",
        "/pricing",
        "/security-center",
        "/workspaces",
        "/task-center",
        "/system-health",
        "/test-center",
        "/api/security/health",
        "/api/background/health",
        "/api/system/health",
        "/api/tests/health",
    ]

    try:
        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:
            failures: list[
                dict[str, Any]
            ] = []

            warnings: list[
                dict[str, Any]
            ] = []

            for path in public_paths:
                response = client.get(
                    path
                )

                if response.status_code >= 500:
                    failures.append(
                        {
                            "path": path,
                            "status": (
                                response.status_code
                            ),
                            "body": (
                                response.text[:500]
                            ),
                        }
                    )
                elif response.status_code >= 400:
                    warnings.append(
                        {
                            "path": path,
                            "status": (
                                response.status_code
                            ),
                        }
                    )

            if failures:
                recorder.add(
                    "HTTP",
                    "Endpoint publik",
                    "FAIL",
                    (
                        f"{len(failures)} endpoint "
                        "mengembalikan server error."
                    ),
                    evidence=failures,
                )
            elif warnings:
                recorder.add(
                    "HTTP",
                    "Endpoint publik",
                    "WARNING",
                    (
                        f"{len(warnings)} endpoint "
                        "mengembalikan status 4xx."
                    ),
                    evidence=warnings,
                )
            else:
                recorder.add(
                    "HTTP",
                    "Endpoint publik",
                    "PASS",
                    (
                        f"{len(public_paths)} endpoint "
                        "dapat diakses tanpa server error."
                    ),
                )

            email, password = (
                parse_admin_credentials()
            )

            if not email or not password:
                recorder.add(
                    "Autentikasi",
                    "Login administrator",
                    "SKIPPED",
                    (
                        "LOCAL_ADMIN.txt tidak tersedia "
                        "atau tidak dapat dibaca."
                    ),
                )
                return

            client.get(
                "/api/security/csrf"
            )

            csrf_token = client.cookies.get(
                "docurapi_csrf"
            )

            headers = {}

            if csrf_token:
                headers[
                    "X-CSRF-Token"
                ] = csrf_token

            login_response = client.post(
                "/api/auth/login",
                data={
                    "email": email,
                    "password": password,
                },
                headers=headers,
            )

            if login_response.status_code >= 400:
                recorder.add(
                    "Autentikasi",
                    "Login administrator",
                    "FAIL",
                    (
                        "Login administrator gagal "
                        f"dengan HTTP "
                        f"{login_response.status_code}."
                    ),
                    evidence=login_response.text[
                        :1000
                    ],
                )
                return

            recorder.add(
                "Autentikasi",
                "Login administrator",
                "PASS",
                (
                    "Akun administrator berhasil "
                    "membuat sesi autentikasi."
                ),
            )

            protected_paths = [
                "/api/auth/me",
                "/api/account/usage",
                "/api/workspaces",
                "/api/background/jobs?limit=5",
                "/api/system/health/detail",
                "/api/system/backups",
            ]

            protected_failures = []

            for path in protected_paths:
                response = client.get(path)

                if response.status_code >= 400:
                    protected_failures.append(
                        {
                            "path": path,
                            "status": (
                                response.status_code
                            ),
                            "body": (
                                response.text[:500]
                            ),
                        }
                    )

            if protected_failures:
                recorder.add(
                    "Autentikasi",
                    "Endpoint administrator",
                    "FAIL",
                    (
                        f"{len(protected_failures)} "
                        "endpoint terlindungi gagal."
                    ),
                    evidence=protected_failures,
                )
            else:
                recorder.add(
                    "Autentikasi",
                    "Endpoint administrator",
                    "PASS",
                    (
                        f"{len(protected_paths)} "
                        "endpoint terlindungi dapat diakses."
                    ),
                )

    except Exception as exc:
        recorder.add(
            "HTTP",
            "FastAPI TestClient",
            "FAIL",
            str(exc),
            evidence=traceback.format_exc()[
                -7000:
            ],
        )


def calculate_summary(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = Counter(
        item["status"]
        for item in results
    )

    fail_count = counts.get(
        "FAIL",
        0,
    )

    warning_count = counts.get(
        "WARNING",
        0,
    )

    skipped_count = counts.get(
        "SKIPPED",
        0,
    )

    score = max(
        0,
        100
        - fail_count * 15
        - warning_count * 4
        - skipped_count * 1,
    )

    if fail_count == 0 and warning_count == 0:
        readiness = "READY"
    elif fail_count == 0:
        readiness = "CONDITIONAL"
    elif score >= 60:
        readiness = "NOT READY"
    else:
        readiness = "CRITICAL"

    return {
        "total": len(results),
        "pass": counts.get(
            "PASS",
            0,
        ),
        "fail": fail_count,
        "warning": warning_count,
        "skipped": skipped_count,
        "score": score,
        "readiness": readiness,
    }


def render_html_report(
    report: dict[str, Any],
) -> str:
    rows = []

    for item in report["results"]:
        evidence = item.get(
            "evidence"
        )

        evidence_html = ""

        if evidence is not None:
            evidence_html = (
                "<details>"
                "<summary>Lihat evidence</summary>"
                "<pre>"
                + html.escape(
                    json.dumps(
                        evidence,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
                + "</pre>"
                "</details>"
            )

        rows.append(
            "".join(
                [
                    "<tr>",
                    (
                        f"<td>"
                        f"{html.escape(item['category'])}"
                        f"</td>"
                    ),
                    (
                        f"<td>"
                        f"{html.escape(item['name'])}"
                        f"</td>"
                    ),
                    (
                        f"<td>"
                        f"<span class='status "
                        f"{item['status'].lower()}'>"
                        f"{html.escape(item['status'])}"
                        f"</span>"
                        f"</td>"
                    ),
                    (
                        f"<td>"
                        f"{html.escape(item['detail'])}"
                        f"{evidence_html}"
                        f"</td>"
                    ),
                    "</tr>",
                ]
            )
        )

    summary = report["summary"]

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>DocuRapi Release Readiness</title>
<style>
body {{
    margin: 0;
    padding: 32px;
    background: #f2f7f6;
    color: #172326;
    font-family: Arial, sans-serif;
}}
main {{
    max-width: 1200px;
    margin: auto;
}}
header, section {{
    margin-bottom: 20px;
    padding: 24px;
    border: 1px solid #dce7e4;
    border-radius: 18px;
    background: white;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
}}
.grid article {{
    padding: 16px;
    border-radius: 12px;
    background: #e5f3ef;
}}
.grid strong {{
    display: block;
    margin-top: 5px;
    color: #0f6b5d;
    font-size: 25px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th, td {{
    padding: 11px;
    border-bottom: 1px solid #dce7e4;
    text-align: left;
    vertical-align: top;
}}
.status {{
    padding: 5px 8px;
    border-radius: 999px;
    font-weight: bold;
}}
.pass {{
    background: #e5f3ef;
    color: #084d43;
}}
.fail {{
    background: #fff0f0;
    color: #b63b3b;
}}
.warning {{
    background: #fff4d8;
    color: #946013;
}}
.skipped {{
    background: #eef0f2;
    color: #5b6469;
}}
pre {{
    max-width: 650px;
    overflow: auto;
    padding: 12px;
    border-radius: 8px;
    background: #172326;
    color: white;
}}
</style>
</head>
<body>
<main>
<header>
    <p>DOCURAPI ACCEPTANCE TEST</p>
    <h1>Release Readiness Report</h1>
    <p>Dibuat: {html.escape(report['generated_at'])}</p>
    <p>Mode: {html.escape(report['mode'])}</p>
</header>
<section class="grid">
    <article>Total<strong>{summary['total']}</strong></article>
    <article>Pass<strong>{summary['pass']}</strong></article>
    <article>Fail<strong>{summary['fail']}</strong></article>
    <article>Warning<strong>{summary['warning']}</strong></article>
    <article>Score<strong>{summary['score']}/100</strong></article>
</section>
<section>
    <h2>Status: {html.escape(summary['readiness'])}</h2>
    <table>
        <thead>
            <tr>
                <th>Kategori</th>
                <th>Pemeriksaan</th>
                <th>Status</th>
                <th>Keterangan</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</section>
</main>
</body>
</html>"""


def render_markdown_report(
    report: dict[str, Any],
) -> str:
    summary = report["summary"]

    lines = [
        "# DocuRapi Release Readiness",
        "",
        f"- Waktu: {report['generated_at']}",
        f"- Mode: {report['mode']}",
        f"- Status: **{summary['readiness']}**",
        f"- Skor: **{summary['score']}/100**",
        f"- PASS: {summary['pass']}",
        f"- FAIL: {summary['fail']}",
        f"- WARNING: {summary['warning']}",
        f"- SKIPPED: {summary['skipped']}",
        "",
        "## Hasil Pemeriksaan",
        "",
        "| Kategori | Pemeriksaan | Status | Keterangan |",
        "|---|---|---:|---|",
    ]

    for item in report["results"]:
        detail = (
            item["detail"]
            .replace("|", "\\|")
            .replace("\n", " ")
        )

        lines.append(
            (
                f"| {item['category']} "
                f"| {item['name']} "
                f"| {item['status']} "
                f"| {detail} |"
            )
        )

    lines.extend(
        [
            "",
            "## Interpretasi",
            "",
        ]
    )

    if summary["readiness"] == "READY":
        lines.append(
            "Seluruh pemeriksaan utama lulus."
        )
    elif summary["readiness"] == "CONDITIONAL":
        lines.append(
            "Tidak ada kegagalan kritis, tetapi warning "
            "perlu ditinjau sebelum deployment."
        )
    else:
        lines.append(
            "Masih terdapat kegagalan yang harus diperbaiki "
            "sebelum aplikasi dinyatakan siap rilis."
        )

    return "\n".join(lines) + "\n"


def save_report(
    report: dict[str, Any],
) -> None:
    LATEST_JSON.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    LATEST_HTML.write_text(
        render_html_report(report),
        encoding="utf-8",
    )

    LATEST_MARKDOWN.write_text(
        render_markdown_report(report),
        encoding="utf-8",
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    historical_path = (
        REPORT_DIR
        / f"acceptance_{timestamp}.json"
    )

    historical_path.write_text(
        LATEST_JSON.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )


def load_latest_report() -> dict[str, Any] | None:
    if not LATEST_JSON.exists():
        return None

    try:
        return json.loads(
            LATEST_JSON.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


def run_acceptance_suite(
    mode: str = "full",
) -> dict[str, Any]:
    normalized_mode = (
        mode.lower().strip()
    )

    if normalized_mode not in {
        "structural",
        "full",
    }:
        normalized_mode = "full"

    recorder = AcceptanceRecorder()

    fixtures = create_acceptance_fixtures()

    recorder.add(
        "Fixtures",
        "Dokumen uji",
        "PASS",
        (
            f"{len(fixtures['fixtures'])} "
            "dokumen DOCX uji berhasil dibuat."
        ),
        evidence=fixtures["fixtures"],
    )

    check_required_files(recorder)
    check_python_sources(recorder)
    check_databases(recorder)
    check_frontend_duplicates(recorder)

    app = None

    try:
        app = load_fastapi_app()

        recorder.add(
            "Aplikasi",
            "Import FastAPI",
            "PASS",
            "Objek FastAPI berhasil diimpor.",
        )

        check_routes_and_middleware(
            recorder,
            app,
        )

    except Exception as exc:
        recorder.add(
            "Aplikasi",
            "Import FastAPI",
            "FAIL",
            str(exc),
            evidence=traceback.format_exc()[
                -10000:
            ],
        )

    if normalized_mode == "full":
        check_document_services(
            recorder,
            fixtures,
        )

        if app is not None:
            check_http_application(
                recorder,
                app,
            )
    else:
        recorder.add(
            "Runtime",
            "Document engine",
            "SKIPPED",
            (
                "Pemeriksaan runtime dilewati "
                "pada mode structural."
            ),
        )

        recorder.add(
            "Runtime",
            "HTTP application",
            "SKIPPED",
            (
                "Pemeriksaan HTTP dilewati "
                "pada mode structural."
            ),
        )

    summary = calculate_summary(
        recorder.results
    )

    report = {
        "generated_at": utc_now(),
        "mode": normalized_mode,
        "summary": summary,
        "fixtures": fixtures,
        "results": recorder.results,
        "report_files": {
            "json": str(LATEST_JSON),
            "html": str(LATEST_HTML),
            "markdown": str(
                LATEST_MARKDOWN
            ),
        },
    }

    save_report(report)

    return report

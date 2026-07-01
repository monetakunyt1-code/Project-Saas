from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import (
    FileResponse,
)

from services.auth_service import (
    require_admin,
)


BASE_DIR = Path(__file__).resolve().parent

ACCEPTANCE_DIRECTORY = (
    BASE_DIR
    / "storage"
    / "acceptance"
)

FIXTURE_DIRECTORY = (
    ACCEPTANCE_DIRECTORY
    / "fixtures"
)

REPORT_DIRECTORY = (
    ACCEPTANCE_DIRECTORY
    / "reports"
)

TEST_CENTER_PAGE = (
    BASE_DIR
    / "templates"
    / "test_center.html"
)

router = APIRouter()


@router.get("/test-center")
def test_center_page() -> FileResponse:
    if not TEST_CENTER_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Halaman Test Center "
                "belum tersedia."
            ),
        )

    return FileResponse(
        TEST_CENTER_PAGE
    )


@router.get("/api/tests/health")
def test_center_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "modes": [
            "structural",
            "full",
        ],
        "report_available": (
            REPORT_DIRECTORY
            .joinpath(
                "latest_report.json"
            )
            .exists()
        ),
    }


@router.post("/api/tests/run")
def run_tests(
    mode: str = Query("full"),
    admin=Depends(require_admin),
) -> dict[str, Any]:
    from services.acceptance_runner import (
        run_acceptance_suite,
    )

    report = run_acceptance_suite(
        mode=mode
    )

    report["requested_by"] = (
        admin["email"]
    )

    return report


@router.get("/api/tests/latest")
def latest_test_report(
    admin=Depends(require_admin),
) -> dict[str, Any]:
    from services.acceptance_runner import (
        load_latest_report,
    )

    report = load_latest_report()

    if not report:
        raise HTTPException(
            status_code=404,
            detail=(
                "Belum ada laporan acceptance test."
            ),
        )

    report["requested_by"] = (
        admin["email"]
    )

    return report


@router.get("/api/tests/report/download")
def download_test_report(
    format: str = Query("html"),
    admin=Depends(require_admin),
) -> FileResponse:
    formats = {
        "html": (
            "latest_report.html",
            "text/html",
        ),
        "json": (
            "latest_report.json",
            "application/json",
        ),
        "markdown": (
            "latest_report.md",
            "text/markdown",
        ),
    }

    selected = formats.get(
        format.lower()
    )

    if not selected:
        raise HTTPException(
            status_code=400,
            detail=(
                "Format laporan tidak didukung."
            ),
        )

    path = (
        REPORT_DIRECTORY
        / selected[0]
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Laporan acceptance test "
                "belum tersedia."
            ),
        )

    return FileResponse(
        path,
        filename=(
            f"DocuRapi_Acceptance_"
            f"{selected[0]}"
        ),
        media_type=selected[1],
    )


@router.get("/api/tests/fixtures")
def list_test_fixtures(
    admin=Depends(require_admin),
) -> dict[str, Any]:
    files = []

    if FIXTURE_DIRECTORY.exists():
        for path in sorted(
            FIXTURE_DIRECTORY.glob(
                "*.docx"
            )
        ):
            files.append(
                {
                    "name": path.name,
                    "size_bytes": (
                        path.stat().st_size
                    ),
                    "download_url": (
                        "/api/tests/fixtures/"
                        + path.name
                    ),
                }
            )

    return {
        "fixtures": files,
        "requested_by": admin["email"],
    }


@router.get(
    "/api/tests/fixtures/{filename}"
)
def download_test_fixture(
    filename: str,
    admin=Depends(require_admin),
) -> FileResponse:
    safe_name = Path(
        filename
    ).name

    if safe_name != filename:
        raise HTTPException(
            status_code=400,
            detail="Nama file tidak valid.",
        )

    path = (
        FIXTURE_DIRECTORY
        / safe_name
    )

    if (
        not path.exists()
        or path.suffix.lower() != ".docx"
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Dokumen uji tidak ditemukan."
            ),
        )

    return FileResponse(
        path,
        filename=path.name,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )

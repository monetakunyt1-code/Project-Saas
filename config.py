import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
_IS_VERCEL_RUNTIME = bool(
    os.getenv("VERCEL")
    or os.getenv("VERCEL_ENV")
    or os.getenv("NOW_REGION")
)

_RUNTIME_ROOT = Path(
    os.getenv(
        "DOCURAPI_RUNTIME_ROOT",
        "/tmp/docurapi-runtime",
    )
).resolve()

STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
REPORT_DIR = STORAGE_DIR / "reports"
HISTORY_DIR = STORAGE_DIR / "history"
TEMPLATE_DIR = STORAGE_DIR / "templates"

DATABASE_PATH = STORAGE_DIR / "docurapi.db"
LOG_FILE = (
    _RUNTIME_ROOT / "logs" / "docurapi.log"
    if _IS_VERCEL_RUNTIME
    else BASE_DIR / "logs" / "docurapi.log"
)

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSION = ".docx"

DIRECTORIES = (
    STORAGE_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    REPORT_DIR,
    HISTORY_DIR,
    TEMPLATE_DIR,
    LOG_FILE.parent,
)

# DOCURAPI VERCEL WRITABLE RUNTIME PATHS
import os as _docurapi_runtime_os
from pathlib import Path as _DocuRapiRuntimePath

_docurapi_is_vercel = bool(
    _docurapi_runtime_os.environ.get(
        "VERCEL"
    )
    or _docurapi_runtime_os.environ.get(
        "VERCEL_ENV"
    )
    or _docurapi_runtime_os.environ.get(
        "NOW_REGION"
    )
)

_docurapi_project_storage_root = (
    _DocuRapiRuntimePath(__file__)
    .resolve()
    .parent
    / "storage"
)

_docurapi_runtime_root = (
    _DocuRapiRuntimePath(
        _docurapi_runtime_os.environ.get(
            "DOCURAPI_RUNTIME_ROOT",
            "/tmp/docurapi-runtime",
        )
    )
)

_docurapi_runtime_storage_root = (
    _docurapi_runtime_root
    / "storage"
)


def _docurapi_remap_runtime_path(value):
    if not isinstance(
        value,
        _DocuRapiRuntimePath,
    ):
        return value

    try:
        if value.is_absolute():
            relative = (
                value.resolve()
                .relative_to(
                    _docurapi_project_storage_root
                    .resolve()
                )
            )

            return (
                _docurapi_runtime_storage_root
                / relative
            )

        parts = value.parts

        if parts and parts[0] == "storage":
            return (
                _docurapi_runtime_storage_root
                .joinpath(*parts[1:])
            )

    except ValueError:
        pass

    return value


def _docurapi_remap_runtime_value(value):
    mapped_path = (
        _docurapi_remap_runtime_path(
            value
        )
    )

    if mapped_path is not value:
        return mapped_path

    if type(value) is list:
        return [
            _docurapi_remap_runtime_value(item)
            for item in value
        ]

    if type(value) is tuple:
        return tuple(
            _docurapi_remap_runtime_value(item)
            for item in value
        )

    if type(value) is set:
        return {
            _docurapi_remap_runtime_value(item)
            for item in value
        }

    if type(value) is dict:
        return {
            _docurapi_remap_runtime_value(key):
                _docurapi_remap_runtime_value(item)
            for key, item in value.items()
        }

    return value


_docurapi_remapped_path_names = []

if _docurapi_is_vercel:
    for _docurapi_name, _docurapi_value in list(
        globals().items()
    ):
        if _docurapi_name.startswith(
            "_docurapi_"
        ):
            continue

        _docurapi_mapped_value = (
            _docurapi_remap_runtime_value(
                _docurapi_value
            )
        )

        if _docurapi_mapped_value != _docurapi_value:
            globals()[
                _docurapi_name
            ] = _docurapi_mapped_value

            _docurapi_remapped_path_names.append(
                _docurapi_name
            )

    _docurapi_runtime_storage_root.mkdir(
        parents=True,
        exist_ok=True,
    )

for directory in DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)

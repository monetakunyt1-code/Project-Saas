"""Hybrid local dan object storage bridge DocuRapi.

Lapisan ini memungkinkan modul lama tetap menggunakan path lokal,
sementara modul baru dapat menggunakan referensi object storage:

    object://jobs/workspaces/.../result.docx

Mode runtime object storage belum otomatis diaktifkan. Pemilihan
referensi dilakukan melalui DOCURAPI_OBJECT_STORAGE_RUNTIME_ENABLED.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from fastapi.responses import (
    FileResponse,
    RedirectResponse,
)
from starlette.background import BackgroundTask
from starlette.responses import Response

from services.object_storage import (
    ObjectNotFoundError,
    ObjectStorage,
    StoredObject,
    create_object_storage,
    normalize_key,
)


OBJECT_REFERENCE_PREFIX = "object://"

RUNTIME_ENABLED_ENV = (
    "DOCURAPI_OBJECT_STORAGE_RUNTIME_ENABLED"
)

KEEP_LOCAL_COPY_ENV = (
    "DOCURAPI_OBJECT_STORAGE_KEEP_LOCAL_COPY"
)

CACHE_ROOT_ENV = (
    "DOCURAPI_OBJECT_STORAGE_CACHE_ROOT"
)


class StorageBridgeError(
    RuntimeError
):
    """Kesalahan pada hybrid storage bridge."""


@dataclass(frozen=True)
class HybridStoredFile:
    active_reference: str
    object_reference: str
    object_key: str
    local_path: str | None
    backend: str
    size: int
    content_type: str | None


def _environment_boolean(
    name: str,
    default: bool,
) -> bool:
    raw = os.environ.get(
        name,
        "",
    ).strip().lower()

    if not raw:
        return default

    if raw in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }:
        return True

    if raw in {
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }:
        return False

    raise StorageBridgeError(
        f"Environment variable {name} "
        "harus berupa true atau false."
    )


def runtime_enabled() -> bool:
    return _environment_boolean(
        RUNTIME_ENABLED_ENV,
        False,
    )


def keep_local_copy() -> bool:
    return _environment_boolean(
        KEEP_LOCAL_COPY_ENV,
        True,
    )


def is_object_reference(
    value: str | os.PathLike[str] | None,
) -> bool:
    if value is None:
        return False

    return os.fspath(
        value
    ).strip().lower().startswith(
        OBJECT_REFERENCE_PREFIX
    )


def object_reference(
    key: str,
) -> str:
    return (
        OBJECT_REFERENCE_PREFIX
        + normalize_key(key)
    )


def object_key_from_reference(
    reference: str | os.PathLike[str],
) -> str:
    value = os.fspath(
        reference
    ).strip()

    if not is_object_reference(
        value
    ):
        raise StorageBridgeError(
            "Nilai bukan referensi object storage: "
            f"{value}"
        )

    key = value[
        len(OBJECT_REFERENCE_PREFIX):
    ]

    return normalize_key(
        key
    )


def _safe_segment(
    value: str,
    *,
    fallback: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    normalized = normalized.encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii"
    )

    normalized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        normalized,
    ).strip(
        ".-_"
    )

    return (
        normalized[:120]
        if normalized
        else fallback
    )


def _safe_filename(
    filename: str,
) -> str:
    path = Path(
        str(filename).replace(
            "\\",
            "/",
        )
    )

    name = path.name

    if name in {
        "",
        ".",
        "..",
    }:
        return "document.bin"

    suffixes = "".join(
        path.suffixes
    )

    stem = name[
        : len(name) - len(suffixes)
    ] if suffixes else name

    safe_stem = _safe_segment(
        stem,
        fallback="document",
    )

    safe_suffix = re.sub(
        r"[^A-Za-z0-9.]+",
        "",
        suffixes,
    ).lower()

    result = (
        safe_stem
        + safe_suffix[:40]
    )

    return result[:180]


def build_object_key(
    category: str,
    filename: str,
    *,
    user_id: str | None = None,
    workspace_id: str | None = None,
    resource_id: str | None = None,
) -> str:
    parts = [
        _safe_segment(
            category,
            fallback="documents",
        ),
    ]

    if workspace_id:
        parts.extend(
            (
                "workspaces",
                _safe_segment(
                    workspace_id,
                    fallback="workspace",
                ),
            )
        )

    if user_id:
        parts.extend(
            (
                "users",
                _safe_segment(
                    user_id,
                    fallback="user",
                ),
            )
        )

    if resource_id:
        parts.extend(
            (
                "resources",
                _safe_segment(
                    resource_id,
                    fallback="resource",
                ),
            )
        )

    parts.append(
        _safe_filename(
            filename
        )
    )

    return normalize_key(
        "/".join(parts)
    )


def _remove_temporary_file(
    path: str,
) -> None:
    Path(path).unlink(
        missing_ok=True
    )


class HybridStorageBridge:
    def __init__(
        self,
        storage: ObjectStorage | None = None,
        *,
        enabled: bool | None = None,
        preserve_local: bool | None = None,
        cache_root: str | os.PathLike[str] | None = None,
    ) -> None:
        self.storage = (
            storage
            if storage is not None
            else create_object_storage()
        )

        self.enabled = (
            runtime_enabled()
            if enabled is None
            else bool(enabled)
        )

        self.preserve_local = (
            keep_local_copy()
            if preserve_local is None
            else bool(preserve_local)
        )

        configured_cache = (
            cache_root
            if cache_root is not None
            else os.environ.get(
                CACHE_ROOT_ENV,
                "/tmp/docurapi-object-cache",
            )
        )

        self.cache_root = Path(
            configured_cache
        ).expanduser().resolve()

        self.cache_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def persist_file(
        self,
        source: str | os.PathLike[str],
        key: str,
        *,
        content_type: str | None = None,
        activate: bool | None = None,
        remove_source: bool = False,
    ) -> HybridStoredFile:
        source_path = Path(
            source
        ).expanduser().resolve()

        if not source_path.is_file():
            raise FileNotFoundError(
                source_path
            )

        normalized_key = normalize_key(
            key
        )

        stored = self.storage.put_file(
            source_path,
            normalized_key,
            content_type=content_type,
            metadata={
                "docurapi-source":
                    source_path.name,
            },
        )

        use_object_reference = (
            self.enabled
            if activate is None
            else bool(activate)
        )

        reference = object_reference(
            normalized_key
        )

        active_reference = (
            reference
            if use_object_reference
            else str(source_path)
        )

        should_remove_source = (
            remove_source
            and use_object_reference
            and not self.preserve_local
        )

        if should_remove_source:
            source_path.unlink(
                missing_ok=True
            )

        local_path = (
            str(source_path)
            if source_path.exists()
            else None
        )

        return HybridStoredFile(
            active_reference=
                active_reference,
            object_reference=
                reference,
            object_key=
                normalized_key,
            local_path=
                local_path,
            backend=
                stored.backend,
            size=
                stored.size,
            content_type=
                stored.content_type,
        )

    def persist_bytes(
        self,
        data: bytes,
        key: str,
        *,
        local_path: str | os.PathLike[str] | None = None,
        content_type: str | None = None,
        activate: bool | None = None,
    ) -> HybridStoredFile:
        if not isinstance(
            data,
            bytes,
        ):
            raise TypeError(
                "data harus berupa bytes."
            )

        normalized_key = normalize_key(
            key
        )

        use_object_reference = (
            self.enabled
            if activate is None
            else bool(activate)
        )

        resolved_local: Path | None = None

        should_write_local = (
            local_path is not None
            and (
                not use_object_reference
                or self.preserve_local
            )
        )

        if should_write_local:
            resolved_local = Path(
                local_path
            ).expanduser().resolve()

            resolved_local.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            descriptor, temporary_name = (
                tempfile.mkstemp(
                    prefix=".docurapi-bridge-",
                    dir=resolved_local.parent,
                )
            )

            try:
                with os.fdopen(
                    descriptor,
                    "wb",
                ) as output:
                    output.write(
                        data
                    )

                    output.flush()
                    os.fsync(
                        output.fileno()
                    )

                os.replace(
                    temporary_name,
                    resolved_local,
                )

            except Exception:
                try:
                    os.unlink(
                        temporary_name
                    )
                except FileNotFoundError:
                    pass

                raise

        stored = self.storage.put_bytes(
            normalized_key,
            data,
            content_type=content_type,
            metadata={
                "docurapi-origin":
                    "hybrid-storage-bridge",
            },
        )

        reference = object_reference(
            normalized_key
        )

        if use_object_reference:
            active_reference = reference
        elif resolved_local is not None:
            active_reference = str(
                resolved_local
            )
        else:
            active_reference = reference

        return HybridStoredFile(
            active_reference=
                active_reference,
            object_reference=
                reference,
            object_key=
                normalized_key,
            local_path=(
                str(resolved_local)
                if resolved_local is not None
                else None
            ),
            backend=
                stored.backend,
            size=
                stored.size,
            content_type=
                stored.content_type,
        )

    def exists(
        self,
        reference: str | os.PathLike[str],
    ) -> bool:
        if is_object_reference(
            reference
        ):
            return self.storage.exists(
                object_key_from_reference(
                    reference
                )
            )

        return Path(
            reference
        ).expanduser().is_file()

    def read_bytes(
        self,
        reference: str | os.PathLike[str],
    ) -> bytes:
        if is_object_reference(
            reference
        ):
            return self.storage.get_bytes(
                object_key_from_reference(
                    reference
                )
            )

        path = Path(
            reference
        ).expanduser()

        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        return path.read_bytes()

    @contextmanager
    def materialize(
        self,
        reference: str | os.PathLike[str],
    ) -> Iterator[Path]:
        if not is_object_reference(
            reference
        ):
            path = Path(
                reference
            ).expanduser().resolve()

            if not path.is_file():
                raise FileNotFoundError(
                    path
                )

            yield path
            return

        key = object_key_from_reference(
            reference
        )

        suffix = Path(
            key
        ).suffix

        descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix="docurapi-object-",
                suffix=suffix,
                dir=self.cache_root,
            )
        )

        os.close(
            descriptor
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            self.storage.download_file(
                key,
                temporary_path,
            )

            yield temporary_path

        finally:
            temporary_path.unlink(
                missing_ok=True
            )

    def delete(
        self,
        reference: str | os.PathLike[str],
        *,
        delete_local: bool = False,
    ) -> bool:
        if is_object_reference(
            reference
        ):
            return self.storage.delete(
                object_key_from_reference(
                    reference
                )
            )

        path = Path(
            reference
        ).expanduser()

        if not path.exists():
            return False

        if not delete_local:
            return False

        path.unlink()

        return True

    def build_download_response(
        self,
        reference: str | os.PathLike[str],
        *,
        filename: str | None = None,
        media_type: str | None = None,
        expires_in: int | None = None,
    ) -> Response:
        if not is_object_reference(
            reference
        ):
            path = Path(
                reference
            ).expanduser().resolve()

            if not path.is_file():
                raise FileNotFoundError(
                    path
                )

            return FileResponse(
                path,
                filename=(
                    filename
                    or path.name
                ),
                media_type=media_type,
            )

        key = object_key_from_reference(
            reference
        )

        if not self.storage.exists(
            key
        ):
            raise ObjectNotFoundError(
                key
            )

        if self.storage.backend == "s3":
            url = (
                self.storage
                .presigned_get_url(
                    key,
                    expires_in=expires_in,
                )
            )

            return RedirectResponse(
                url=url,
                status_code=307,
            )

        suffix = Path(
            key
        ).suffix

        digest = hashlib.sha256(
            key.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=(
                    "docurapi-download-"
                    + digest
                    + "-"
                ),
                suffix=suffix,
                dir=self.cache_root,
            )
        )

        os.close(
            descriptor
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            self.storage.download_file(
                key,
                temporary_path,
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )

            raise

        return FileResponse(
            temporary_path,
            filename=(
                filename
                or Path(key).name
            ),
            media_type=media_type,
            background=BackgroundTask(
                _remove_temporary_file,
                str(temporary_path),
            ),
        )


def create_storage_bridge(
    *,
    enabled: bool | None = None,
    preserve_local: bool | None = None,
) -> HybridStorageBridge:
    return HybridStorageBridge(
        enabled=enabled,
        preserve_local=preserve_local,
    )

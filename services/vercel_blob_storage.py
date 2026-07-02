from __future__ import annotations

import hashlib
import inspect
import json
import mimetypes
import os
import tempfile
import time
import uuid

from datetime import UTC, datetime
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from services.object_storage import (
    ObjectNotFoundError,
    ObjectStorage,
    ObjectStorageError,
    StoredObject,
    guess_content_type,
    normalize_key,
)


DEFAULT_BLOB_API_URL = (
    "https://vercel.com/api/blob"
)

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_CACHE_CONTROL_SECONDS = 60
BLOB_API_VERSION = "12"


def _nonempty_environment(
    name: str,
) -> str | None:
    value = os.environ.get(
        name,
        "",
    ).strip()

    return value or None


def _normalize_store_id(
    value: str,
) -> str:
    normalized = value.strip()

    if normalized.startswith(
        "store_"
    ):
        normalized = normalized[
            len("store_"):
        ]

    if not normalized:
        raise ObjectStorageError(
            "BLOB_STORE_ID kosong."
        )

    return normalized


def _store_id_from_static_token(
    token: str,
) -> str | None:
    parts = token.split("_")

    if len(parts) < 4:
        return None

    value = parts[3].strip()

    return value or None


def _is_optional_annotation(
    annotation: Any,
) -> bool:
    origin = get_origin(
        annotation
    )

    return (
        origin in {
            Union,
            UnionType,
        }
        and type(None)
        in get_args(annotation)
    )


def _default_for_annotation(
    annotation: Any,
) -> Any:
    if _is_optional_annotation(
        annotation
    ):
        return None

    origin = get_origin(
        annotation
    )

    if origin is list:
        return []

    if origin is dict:
        return {}

    if annotation in {
        str,
        "str",
    }:
        return ""

    if annotation in {
        int,
        "int",
    }:
        return 0

    if annotation in {
        bool,
        "bool",
    }:
        return False

    if annotation in {
        bytes,
        "bytes",
    }:
        return b""

    return None


class VercelBlobObjectStorage(
    ObjectStorage
):
    """Private Vercel Blob adapter for DocuRapi.

    Read/write operations use either Vercel OIDC or a static
    BLOB_READ_WRITE_TOKEN. OIDC credentials are resolved for
    every operation so request-scoped tokens can be used.
    """

    backend = "vercel_blob"

    def __init__(
        self,
        *,
        timeout_seconds: int | None = None,
    ) -> None:
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else int(
                os.environ.get(
                    "DOCURAPI_VERCEL_BLOB_TIMEOUT",
                    str(
                        DEFAULT_TIMEOUT_SECONDS
                    ),
                )
            )
        )

        self._api_url = (
            os.environ.get(
                "VERCEL_BLOB_API_URL",
                DEFAULT_BLOB_API_URL,
            )
            .strip()
            .rstrip("/")
        )

    def _resolve_oidc_token(
        self,
    ) -> str | None:
        try:
            from vercel.oidc import (
                get_vercel_oidc_token,
            )

            token = (
                get_vercel_oidc_token()
                .strip()
            )

            if token:
                return token

        except Exception:
            pass

        return _nonempty_environment(
            "VERCEL_OIDC_TOKEN"
        )

    def _credentials(
        self,
    ) -> tuple[str, str]:
        store_id_value = (
            _nonempty_environment(
                "BLOB_STORE_ID"
            )
        )

        oidc_token = (
            self._resolve_oidc_token()
        )

        if (
            oidc_token
            and store_id_value
        ):
            return (
                oidc_token,
                _normalize_store_id(
                    store_id_value
                ),
            )

        static_token = (
            _nonempty_environment(
                "BLOB_READ_WRITE_TOKEN"
            )
            or _nonempty_environment(
                "VERCEL_BLOB_READ_WRITE_TOKEN"
            )
        )

        if static_token:
            store_id = (
                store_id_value
                or _store_id_from_static_token(
                    static_token
                )
            )

            if store_id:
                return (
                    static_token,
                    _normalize_store_id(
                        store_id
                    ),
                )

        raise ObjectStorageError(
            "Kredensial Vercel Blob tidak tersedia. "
            "Diperlukan VERCEL_OIDC_TOKEN + BLOB_STORE_ID "
            "atau BLOB_READ_WRITE_TOKEN."
        )

    def _blob_url(
        self,
        key: str,
    ) -> str:
        normalized = normalize_key(
            key
        )

        _, store_id = (
            self._credentials()
        )

        encoded_path = urllib_parse.quote(
            normalized,
            safe="/-_.~",
        )

        return (
            f"https://{store_id}."
            "private.blob.vercel-storage.com/"
            f"{encoded_path}"
        )

    def _api_headers(
        self,
        *,
        content_length: int | None = None,
    ) -> dict[str, str]:
        token, store_id = (
            self._credentials()
        )

        headers = {
            "Authorization":
                f"Bearer {token}",

            "X-Vercel-Blob-Store-Id":
                store_id,

            "X-Api-Version":
                os.environ.get(
                    "VERCEL_BLOB_API_VERSION_OVERRIDE",
                    BLOB_API_VERSION,
                ),

            "X-Api-Blob-Request-Id":
                (
                    f"{store_id}:"
                    f"{int(time.time() * 1000)}:"
                    f"{uuid.uuid4().hex}"
                ),

            "X-Api-Blob-Request-Attempt":
                "0",
        }

        if content_length is not None:
            headers[
                "X-Content-Length"
            ] = str(
                content_length
            )

        return headers

    def _read_http_error(
        self,
        error: urllib_error.HTTPError,
    ) -> str:
        try:
            raw = error.read()
        except Exception:
            raw = b""

        if not raw:
            return str(error)

        try:
            payload = json.loads(
                raw.decode(
                    "utf-8",
                    errors="replace",
                )
            )

            nested = payload.get(
                "error",
                {},
            )

            if isinstance(
                nested,
                dict,
            ):
                message = nested.get(
                    "message"
                )

                if message:
                    return str(message)

        except Exception:
            pass

        return raw.decode(
            "utf-8",
            errors="replace",
        )[:500]

    def _json_api_request(
        self,
        path: str,
        *,
        method: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        object_key: str | None = None,
    ) -> dict[str, Any]:
        url = (
            self._api_url
            + (
                path
                if path.startswith(
                    (
                        "/",
                        "?",
                    )
                )
                else "/" + path
            )
        )

        request_headers = (
            self._api_headers(
                content_length=(
                    len(body)
                    if body is not None
                    else None
                )
            )
        )

        if headers:
            request_headers.update(
                headers
            )

        request = urllib_request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method,
        )

        try:
            with urllib_request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read()

        except urllib_error.HTTPError as exc:
            message = (
                self._read_http_error(
                    exc
                )
            )

            if exc.code == 404:
                raise ObjectNotFoundError(
                    object_key or url
                ) from exc

            raise ObjectStorageError(
                "Vercel Blob API gagal "
                f"(HTTP {exc.code}): {message}"
            ) from exc

        except urllib_error.URLError as exc:
            raise ObjectStorageError(
                "Koneksi ke Vercel Blob gagal: "
                f"{exc.reason}"
            ) from exc

        is_delete_response = (
            method.upper() == "POST"
            and path.rstrip("/") == "/delete"
        )

        if not raw:
            return {}

        try:
            decoded = json.loads(
                raw.decode(
                    "utf-8"
                )
            )

        except Exception as exc:
            if is_delete_response:
                return {}

            raise ObjectStorageError(
                "Respons Vercel Blob bukan JSON yang valid."
            ) from exc

        if not isinstance(
            decoded,
            dict,
        ):
            if is_delete_response:
                return {}

            raise ObjectStorageError(
                "Format respons Vercel Blob tidak sesuai."
            )

        return decoded

    def _private_get(
        self,
        key: str,
    ) -> tuple[
        bytes,
        dict[str, str],
    ]:
        normalized = normalize_key(
            key
        )

        token, _ = (
            self._credentials()
        )

        request = urllib_request.Request(
            self._blob_url(
                normalized
            ),
            headers={
                "Authorization":
                    f"Bearer {token}",
            },
            method="GET",
        )

        try:
            with urllib_request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                data = response.read()

                headers = {
                    str(name).lower():
                        str(value)

                    for name, value
                    in response.headers.items()
                }

                return data, headers

        except urllib_error.HTTPError as exc:
            if exc.code == 404:
                raise ObjectNotFoundError(
                    normalized
                ) from exc

            message = (
                self._read_http_error(
                    exc
                )
            )

            raise ObjectStorageError(
                "Download Private Blob gagal "
                f"(HTTP {exc.code}): {message}"
            ) from exc

        except urllib_error.URLError as exc:
            raise ObjectStorageError(
                "Koneksi download Private Blob gagal: "
                f"{exc.reason}"
            ) from exc

    def _head(
        self,
        key: str,
    ) -> dict[str, Any]:
        normalized = normalize_key(
            key
        )

        query = urllib_parse.urlencode(
            {
                "url":
                    self._blob_url(
                        normalized
                    ),
            }
        )

        return self._json_api_request(
            f"?{query}",
            method="GET",
            object_key=normalized,
        )

    def _stored_object(
        self,
        *,
        key: str,
        size: int,
        content_type: str,
        etag: str,
        url: str,
        checksum: str,
    ) -> StoredObject:
        signature = inspect.signature(
            StoredObject
        )

        now = datetime.now(
            UTC
        )

        values: dict[str, Any] = {
            "key":
                key,

            "object_key":
                key,

            "pathname":
                key,

            "name":
                key,

            "size":
                size,

            "size_bytes":
                size,

            "content_length":
                size,

            "content_type":
                content_type,

            "mime_type":
                content_type,

            "etag":
                etag,

            "checksum":
                checksum,

            "sha256":
                checksum,

            "backend":
                self.backend,

            "storage_backend":
                self.backend,

            "url":
                url,

            "download_url":
                (
                    url
                    + (
                        "&download=1"
                        if "?" in url
                        else "?download=1"
                    )
                ),

            "bucket":
                _normalize_store_id(
                    self._credentials()[1]
                ),

            "store_id":
                _normalize_store_id(
                    self._credentials()[1]
                ),

            "uploaded_at":
                now,

            "created_at":
                now,

            "modified_at":
                now,

            "last_modified":
                now,

            "metadata":
                {
                    "private":
                        True,

                    "backend":
                        self.backend,
                },
        }

        arguments: dict[str, Any] = {}

        for name, parameter in (
            signature.parameters.items()
        ):
            if name == "self":
                continue

            if name in values:
                arguments[name] = (
                    values[name]
                )
                continue

            if (
                parameter.default
                is not inspect.Parameter.empty
            ):
                continue

            fallback = (
                _default_for_annotation(
                    parameter.annotation
                )
            )

            if fallback is None:
                raise ObjectStorageError(
                    "StoredObject memiliki field wajib "
                    f"yang belum didukung: {name}"
                )

            arguments[name] = fallback

        try:
            return StoredObject(
                **arguments
            )

        except Exception as exc:
            raise ObjectStorageError(
                "Gagal membentuk StoredObject "
                f"untuk key {key}: {exc}"
            ) from exc

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Any = None,
    ) -> StoredObject:
        del metadata

        normalized = normalize_key(
            key
        )

        payload = bytes(
            data
        )

        media_type = (
            content_type
            or guess_content_type(
                normalized
            )
            or mimetypes.guess_type(
                normalized
            )[0]
            or "application/octet-stream"
        )

        query = urllib_parse.urlencode(
            {
                "pathname":
                    normalized,
            }
        )

        response = (
            self._json_api_request(
                f"/?{query}",
                method="PUT",
                body=payload,
                headers={
                    "X-Vercel-Blob-Access":
                        "private",

                    "X-Content-Type":
                        media_type,

                    "X-Add-Random-Suffix":
                        "0",

                    "X-Allow-Overwrite":
                        "1",

                    "X-Cache-Control-Max-Age":
                        str(
                            DEFAULT_CACHE_CONTROL_SECONDS
                        ),
                },
                object_key=normalized,
            )
        )

        url = str(
            response.get(
                "url",
                self._blob_url(
                    normalized
                ),
            )
        )

        etag = str(
            response.get(
                "etag",
                "",
            )
        )

        checksum = hashlib.sha256(
            payload
        ).hexdigest()

        return self._stored_object(
            key=normalized,
            size=len(payload),
            content_type=media_type,
            etag=etag,
            url=url,
            checksum=checksum,
        )

    def put_file(
        self,
        source: str | os.PathLike[str],
        key: str,
        *,
        content_type: str | None = None,
        metadata: Any = None,
    ) -> StoredObject:
        source_path = Path(
            source
        )

        if not source_path.is_file():
            raise ObjectStorageError(
                "File sumber tidak ditemukan: "
                f"{source_path}"
            )

        return self.put_bytes(
            key,
            source_path.read_bytes(),
            content_type=(
                content_type
                or guess_content_type(
                    source_path.name
                )
            ),
            metadata=metadata,
        )

    def get_bytes(
        self,
        key: str,
        **_: Any,
    ) -> bytes:
        data, _headers = (
            self._private_get(
                key
            )
        )

        return data

    def download_file(
        self,
        key: str,
        destination_path: str | Path,
        **_: Any,
    ) -> Path:
        destination = Path(
            destination_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self.get_bytes(
            key
        )

        temporary_handle = (
            tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=(
                    destination.name
                    + "."
                ),
                suffix=".tmp",
                dir=str(
                    destination.parent
                ),
                delete=False,
            )
        )

        temporary_path = Path(
            temporary_handle.name
        )

        try:
            with temporary_handle:
                temporary_handle.write(
                    data
                )

                temporary_handle.flush()

                os.fsync(
                    temporary_handle.fileno()
                )

            temporary_path.replace(
                destination
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )
            raise

        return destination

    def exists(
        self,
        key: str,
        **_: Any,
    ) -> bool:
        try:
            self._head(
                key
            )
            return True

        except ObjectNotFoundError:
            return False

    def delete(
        self,
        key: str,
        **_: Any,
    ) -> bool:
        normalized = normalize_key(
            key
        )

        body = json.dumps(
            {
                "urls": [
                    self._blob_url(
                        normalized
                    )
                ],
            }
        ).encode(
            "utf-8"
        )

        self._json_api_request(
            "/delete",
            method="POST",
            body=body,
            headers={
                "Content-Type":
                    "application/json",
            },
            object_key=normalized,
        )

        return True

    def presigned_get_url(
        self,
        key: str,
        expires_in: int | None = None,
        **_: Any,
    ) -> str:
        # Private Blob URLs remain protected. DocuRapi's download
        # bridge retrieves the object with authentication and then
        # streams it to the authorized user.
        del expires_in

        return self._blob_url(
            key
        )

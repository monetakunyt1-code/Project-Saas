"""Object storage adapter DocuRapi.

Backend yang tersedia:

- local: penyimpanan filesystem untuk development dan fallback.
- s3: penyimpanan kompatibel Amazon S3.

Backend dipilih melalui DOCURAPI_OBJECT_STORAGE_BACKEND.
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)


BACKEND_ENV = (
    "DOCURAPI_OBJECT_STORAGE_BACKEND"
)

LOCAL_ROOT_ENV = (
    "DOCURAPI_OBJECT_STORAGE_LOCAL_ROOT"
)

BUCKET_ENV = (
    "DOCURAPI_OBJECT_STORAGE_BUCKET"
)

REGION_ENV = (
    "DOCURAPI_OBJECT_STORAGE_REGION"
)

ENDPOINT_ENV = (
    "DOCURAPI_OBJECT_STORAGE_ENDPOINT"
)

ACCESS_KEY_ENV = (
    "DOCURAPI_OBJECT_STORAGE_ACCESS_KEY"
)

SECRET_KEY_ENV = (
    "DOCURAPI_OBJECT_STORAGE_SECRET_KEY"
)

SESSION_TOKEN_ENV = (
    "DOCURAPI_OBJECT_STORAGE_SESSION_TOKEN"
)

PRESIGNED_TTL_ENV = (
    "DOCURAPI_OBJECT_STORAGE_PRESIGNED_TTL"
)


class ObjectStorageError(
    RuntimeError
):
    """Kesalahan pada object storage."""


class InvalidObjectKeyError(
    ObjectStorageError
):
    """Object key tidak aman atau tidak valid."""


class ObjectNotFoundError(
    ObjectStorageError
):
    """Object tidak ditemukan."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    backend: str
    content_type: str | None = None


class ObjectStorage(Protocol):
    backend: str

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        ...

    def put_file(
        self,
        source: str | os.PathLike[str],
        key: str,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        ...

    def get_bytes(
        self,
        key: str,
    ) -> bytes:
        ...

    def download_file(
        self,
        key: str,
        destination: str | os.PathLike[str],
    ) -> Path:
        ...

    def exists(
        self,
        key: str,
    ) -> bool:
        ...

    def delete(
        self,
        key: str,
    ) -> bool:
        ...

    def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int | None = None,
    ) -> str:
        ...


def backend_name() -> str:
    value = os.environ.get(
        BACKEND_ENV,
        "local",
    ).strip().lower()

    aliases = {
        "filesystem": "local",
        "file": "local",
        "minio": "s3",
        "aws": "s3",
    }

    value = aliases.get(
        value,
        value,
    )

    if value not in {
        "local",
        "s3",
    }:
        raise ObjectStorageError(
            "Backend object storage tidak valid: "
            f"{value!r}"
        )

    return value


def normalize_key(
    key: str,
) -> str:
    if not isinstance(
        key,
        str,
    ):
        raise InvalidObjectKeyError(
            "Object key harus berupa string."
        )

    normalized = key.strip().replace(
        "\\",
        "/",
    )

    if not normalized:
        raise InvalidObjectKeyError(
            "Object key tidak boleh kosong."
        )

    path = PurePosixPath(
        normalized
    )

    if path.is_absolute():
        raise InvalidObjectKeyError(
            "Object key tidak boleh absolut."
        )

    parts = tuple(
        part
        for part in path.parts
        if part not in {
            "",
            ".",
        }
    )

    if not parts:
        raise InvalidObjectKeyError(
            "Object key tidak valid."
        )

    if any(
        part == ".."
        for part in parts
    ):
        raise InvalidObjectKeyError(
            "Object key tidak boleh mengandung '..'."
        )

    if any(
        "\x00" in part
        for part in parts
    ):
        raise InvalidObjectKeyError(
            "Object key mengandung karakter terlarang."
        )

    return "/".join(
        parts
    )


def guess_content_type(
    key: str,
) -> str:
    guessed, _ = mimetypes.guess_type(
        key
    )

    return (
        guessed
        or "application/octet-stream"
    )


def default_presigned_ttl() -> int:
    raw = os.environ.get(
        PRESIGNED_TTL_ENV,
        "900",
    ).strip()

    try:
        value = int(raw)
    except ValueError as exc:
        raise ObjectStorageError(
            "TTL presigned URL harus berupa angka."
        ) from exc

    if value < 60 or value > 604800:
        raise ObjectStorageError(
            "TTL presigned URL harus antara "
            "60 dan 604800 detik."
        )

    return value


class LocalObjectStorage:
    backend = "local"

    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
    ) -> None:
        configured = (
            root
            if root is not None
            else os.environ.get(
                LOCAL_ROOT_ENV,
                "storage/object_store",
            )
        )

        self.root = Path(
            configured
        ).expanduser().resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _object_path(
        self,
        key: str,
    ) -> Path:
        normalized = normalize_key(
            key
        )

        candidate = (
            self.root
            / Path(*normalized.split("/"))
        ).resolve()

        try:
            candidate.relative_to(
                self.root
            )
        except ValueError as exc:
            raise InvalidObjectKeyError(
                "Object key keluar dari storage root."
            ) from exc

        return candidate

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        del metadata

        if not isinstance(
            data,
            bytes,
        ):
            raise TypeError(
                "data harus berupa bytes."
            )

        normalized = normalize_key(
            key
        )

        destination = self._object_path(
            normalized
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=".docurapi-",
                dir=destination.parent,
            )
        )

        try:
            with os.fdopen(
                file_descriptor,
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
                destination,
            )

        except Exception:
            try:
                os.unlink(
                    temporary_name
                )
            except FileNotFoundError:
                pass

            raise

        return StoredObject(
            key=normalized,
            size=len(data),
            backend=self.backend,
            content_type=(
                content_type
                or guess_content_type(
                    normalized
                )
            ),
        )

    def put_file(
        self,
        source: str | os.PathLike[str],
        key: str,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        del metadata

        source_path = Path(
            source
        ).expanduser().resolve()

        if not source_path.is_file():
            raise FileNotFoundError(
                source_path
            )

        normalized = normalize_key(
            key
        )

        destination = self._object_path(
            normalized
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=".docurapi-",
                dir=destination.parent,
            )
        )

        os.close(
            file_descriptor
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            shutil.copyfile(
                source_path,
                temporary_path,
            )

            os.replace(
                temporary_path,
                destination,
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )

            raise

        return StoredObject(
            key=normalized,
            size=destination.stat().st_size,
            backend=self.backend,
            content_type=(
                content_type
                or guess_content_type(
                    normalized
                )
            ),
        )

    def get_bytes(
        self,
        key: str,
    ) -> bytes:
        path = self._object_path(
            key
        )

        if not path.is_file():
            raise ObjectNotFoundError(
                normalize_key(key)
            )

        return path.read_bytes()

    def download_file(
        self,
        key: str,
        destination: str | os.PathLike[str],
    ) -> Path:
        source = self._object_path(
            key
        )

        if not source.is_file():
            raise ObjectNotFoundError(
                normalize_key(key)
            )

        destination_path = Path(
            destination
        ).expanduser().resolve()

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copyfile(
            source,
            destination_path,
        )

        return destination_path

    def exists(
        self,
        key: str,
    ) -> bool:
        return self._object_path(
            key
        ).is_file()

    def delete(
        self,
        key: str,
    ) -> bool:
        path = self._object_path(
            key
        )

        if not path.exists():
            return False

        path.unlink()

        current = path.parent

        while current != self.root:
            try:
                current.rmdir()
            except OSError:
                break

            current = current.parent

        return True

    def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int | None = None,
    ) -> str:
        del expires_in

        path = self._object_path(
            key
        )

        if not path.is_file():
            raise ObjectNotFoundError(
                normalize_key(key)
            )

        return path.as_uri()


class S3ObjectStorage:
    backend = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
    ) -> None:
        self.bucket = (
            bucket
            or os.environ.get(
                BUCKET_ENV,
                "",
            ).strip()
        )

        if not self.bucket:
            raise ObjectStorageError(
                f"{BUCKET_ENV} belum tersedia."
            )

        region = os.environ.get(
            REGION_ENV,
            "",
        ).strip()

        endpoint = os.environ.get(
            ENDPOINT_ENV,
            "",
        ).strip()

        access_key = os.environ.get(
            ACCESS_KEY_ENV,
            "",
        ).strip()

        secret_key = os.environ.get(
            SECRET_KEY_ENV,
            "",
        ).strip()

        session_token = os.environ.get(
            SESSION_TOKEN_ENV,
            "",
        ).strip()

        client_options: dict[
            str,
            Any,
        ] = {}

        if region:
            client_options[
                "region_name"
            ] = region

        if endpoint:
            client_options[
                "endpoint_url"
            ] = endpoint

        if access_key:
            client_options[
                "aws_access_key_id"
            ] = access_key

        if secret_key:
            client_options[
                "aws_secret_access_key"
            ] = secret_key

        if session_token:
            client_options[
                "aws_session_token"
            ] = session_token

        self.client = boto3.client(
            "s3",
            **client_options,
        )

    @staticmethod
    def _metadata(
        metadata: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if metadata is None:
            return {}

        return {
            str(key): str(value)
            for key, value in metadata.items()
        }

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        normalized = normalize_key(
            key
        )

        if not isinstance(
            data,
            bytes,
        ):
            raise TypeError(
                "data harus berupa bytes."
            )

        resolved_content_type = (
            content_type
            or guess_content_type(
                normalized
            )
        )

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=normalized,
                Body=data,
                ContentType=resolved_content_type,
                Metadata=self._metadata(
                    metadata
                ),
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ObjectStorageError(
                f"Gagal menyimpan object: {normalized}"
            ) from exc

        return StoredObject(
            key=normalized,
            size=len(data),
            backend=self.backend,
            content_type=resolved_content_type,
        )

    def put_file(
        self,
        source: str | os.PathLike[str],
        key: str,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        source_path = Path(
            source
        ).expanduser().resolve()

        if not source_path.is_file():
            raise FileNotFoundError(
                source_path
            )

        normalized = normalize_key(
            key
        )

        resolved_content_type = (
            content_type
            or guess_content_type(
                normalized
            )
        )

        extra_args: dict[
            str,
            Any,
        ] = {
            "ContentType":
                resolved_content_type,
            "Metadata":
                self._metadata(
                    metadata
                ),
        }

        try:
            self.client.upload_file(
                str(source_path),
                self.bucket,
                normalized,
                ExtraArgs=extra_args,
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ObjectStorageError(
                f"Gagal mengunggah object: {normalized}"
            ) from exc

        return StoredObject(
            key=normalized,
            size=source_path.stat().st_size,
            backend=self.backend,
            content_type=resolved_content_type,
        )

    def get_bytes(
        self,
        key: str,
    ) -> bytes:
        normalized = normalize_key(
            key
        )

        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=normalized,
            )

            return response[
                "Body"
            ].read()

        except ClientError as exc:
            code = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "",
                )
            )

            if code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise ObjectNotFoundError(
                    normalized
                ) from exc

            raise ObjectStorageError(
                f"Gagal membaca object: {normalized}"
            ) from exc

        except BotoCoreError as exc:
            raise ObjectStorageError(
                f"Gagal membaca object: {normalized}"
            ) from exc

    def download_file(
        self,
        key: str,
        destination: str | os.PathLike[str],
    ) -> Path:
        normalized = normalize_key(
            key
        )

        destination_path = Path(
            destination
        ).expanduser().resolve()

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self.client.download_file(
                self.bucket,
                normalized,
                str(destination_path),
            )

        except ClientError as exc:
            code = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "",
                )
            )

            if code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise ObjectNotFoundError(
                    normalized
                ) from exc

            raise ObjectStorageError(
                f"Gagal mengunduh object: {normalized}"
            ) from exc

        except BotoCoreError as exc:
            raise ObjectStorageError(
                f"Gagal mengunduh object: {normalized}"
            ) from exc

        return destination_path

    def exists(
        self,
        key: str,
    ) -> bool:
        normalized = normalize_key(
            key
        )

        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=normalized,
            )

            return True

        except ClientError as exc:
            code = str(
                exc.response.get(
                    "Error",
                    {},
                ).get(
                    "Code",
                    "",
                )
            )

            if code in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return False

            raise ObjectStorageError(
                f"Gagal memeriksa object: {normalized}"
            ) from exc

        except BotoCoreError as exc:
            raise ObjectStorageError(
                f"Gagal memeriksa object: {normalized}"
            ) from exc

    def delete(
        self,
        key: str,
    ) -> bool:
        normalized = normalize_key(
            key
        )

        existed = self.exists(
            normalized
        )

        if not existed:
            return False

        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=normalized,
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ObjectStorageError(
                f"Gagal menghapus object: {normalized}"
            ) from exc

        return True

    def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int | None = None,
    ) -> str:
        normalized = normalize_key(
            key
        )

        ttl = (
            expires_in
            if expires_in is not None
            else default_presigned_ttl()
        )

        if ttl < 60 or ttl > 604800:
            raise ObjectStorageError(
                "TTL presigned URL harus antara "
                "60 dan 604800 detik."
            )

        try:
            return str(
                self.client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket":
                            self.bucket,
                        "Key":
                            normalized,
                    },
                    ExpiresIn=ttl,
                )
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ObjectStorageError(
                "Gagal membuat presigned URL."
            ) from exc


def create_object_storage(
    *,
    backend: str | None = None,
) -> ObjectStorage:
    selected = (
        backend.strip().lower()
        if backend is not None
        else backend_name()
    )

    if selected == "local":
        return LocalObjectStorage()

    if selected == "s3":
        return S3ObjectStorage()

    raise ObjectStorageError(
        f"Backend object storage tidak didukung: {selected}"
    )

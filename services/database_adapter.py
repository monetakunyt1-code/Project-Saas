"""Adapter database pusat DocuRapi.

Fase 1 mempertahankan kompatibilitas penuh dengan SQLite.
Fase PostgreSQL akan ditambahkan setelah koneksi cloud tersedia.
"""

from __future__ import annotations

import os
import sqlite3 as _sqlite3
from typing import Any


# Ekspor konstanta, exception, class, dan helper bawaan sqlite3
# agar modul lama tetap kompatibel.
for _name in dir(_sqlite3):
    if not _name.startswith("__"):
        globals().setdefault(
            _name,
            getattr(_sqlite3, _name),
        )


def database_url() -> str:
    return (
        os.environ.get("DOCURAPI_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or ""
    ).strip()


def requested_backend() -> str:
    value = database_url().lower()

    if value.startswith(
        (
            "postgres://",
            "postgresql://",
        )
    ):
        return "postgresql"

    return "sqlite"


def connect(
    *args: Any,
    **kwargs: Any,
) -> _sqlite3.Connection:
    backend = requested_backend()

    if backend != "sqlite":
        raise RuntimeError(
            "PostgreSQL telah diminta melalui environment variable, "
            "tetapi adapter PostgreSQL fase 2 belum diaktifkan."
        )

    return _sqlite3.connect(
        *args,
        **kwargs,
    )


def backend_name() -> str:
    return requested_backend()


def __getattr__(name: str) -> Any:
    return getattr(
        _sqlite3,
        name,
    )

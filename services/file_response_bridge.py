"""Installer object-aware FileResponse pada modul API DocuRapi."""

from __future__ import annotations

import sys
from typing import Any

from services.object_aware_response import (
    ObjectAwareFileResponse,
)


TARGET_MODULES = (
    "app",
    "advanced_api",
    "background_api",
    "journal_api",
    "system_api",
    "test_center_api",
    "workspace_api",
)


def install_file_response_bridge() -> tuple[str, ...]:
    patched: list[str] = []

    for module_name in TARGET_MODULES:
        module = sys.modules.get(
            module_name
        )

        if module is None:
            continue

        current = getattr(
            module,
            "FileResponse",
            None,
        )

        if current is None:
            continue

        if (
            current
            is ObjectAwareFileResponse
        ):
            patched.append(
                module_name
            )

            continue

        setattr(
            module,
            "FileResponse",
            ObjectAwareFileResponse,
        )

        patched.append(
            module_name
        )

    return tuple(
        sorted(
            patched
        )
    )

"""FileResponse yang memahami local path dan object storage."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any, Mapping

from starlette.responses import (
    FileResponse as NativeFileResponse,
)
from starlette.responses import Response

from services.storage_bridge import (
    create_storage_bridge,
    is_object_reference,
)
from services.storage_manifest import (
    get_mirror,
)


def _native_file_response(
    path: str | os.PathLike[str],
    *,
    status_code: int,
    headers: Mapping[str, str] | None,
    media_type: str | None,
    background: Any,
    filename: str | None,
    content_disposition_type: str,
    extra: dict[str, Any],
) -> Response:
    supported = inspect.signature(
        NativeFileResponse
    ).parameters

    arguments: dict[str, Any] = {
        "path": path,
        "status_code":
            status_code,
        "headers":
            dict(headers)
            if headers is not None
            else None,
        "media_type":
            media_type,
        "background":
            background,
        "filename":
            filename,
    }

    if (
        "content_disposition_type"
        in supported
    ):
        arguments[
            "content_disposition_type"
        ] = content_disposition_type

    for name, value in extra.items():
        if name in supported:
            arguments[name] = value

    return NativeFileResponse(
        **arguments
    )


def ObjectAwareFileResponse(
    path: str | os.PathLike[str],
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    media_type: str | None = None,
    background: Any = None,
    filename: str | None = None,
    content_disposition_type: str = "attachment",
    **kwargs: Any,
) -> Response:
    value = os.fspath(
        path
    )

    if is_object_reference(
        value
    ):
        object_reference = value
    else:
        local_path = Path(
            value
        ).expanduser()

        if local_path.is_file():
            return _native_file_response(
                local_path,
                status_code=status_code,
                headers=headers,
                media_type=media_type,
                background=background,
                filename=filename,
                content_disposition_type=
                    content_disposition_type,
                extra=kwargs,
            )

        manifest = get_mirror(
            local_path
        )

        if manifest is None:
            raise FileNotFoundError(
                local_path
            )

        object_reference = (
            manifest.object_reference
        )

    bridge = create_storage_bridge()

    response = (
        bridge.build_download_response(
            object_reference,
            filename=filename,
            media_type=media_type,
        )
    )

    response.status_code = (
        status_code
    )

    if headers is not None:
        response.headers.update(
            dict(headers)
        )

    if (
        background is not None
        and response.background is None
    ):
        response.background = (
            background
        )

    return response

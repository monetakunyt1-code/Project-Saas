"""Runtime mirror file DocuRapi.

Service ini mengamati parameter fungsi database yang menyimpan path
file. File lokal disalin ke object storage tanpa mengubah referensi
aktif di database.

Dengan demikian:

- alur lama tetap memakai path lokal;
- object storage menerima salinan mirror;
- aktivasi object:// dapat dilakukan pada fase berikutnya.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from services.storage_bridge import (
    HybridStorageBridge,
    build_object_key,
    create_storage_bridge,
    is_object_reference,
)

from services.storage_manifest import (
    record_mirror,
)


LOGGER = logging.getLogger(
    "docurapi.storage.mirror"
)

MIRROR_ENABLED_ENV = (
    "DOCURAPI_OBJECT_STORAGE_MIRROR_ENABLED"
)

MIRROR_REQUIRED_ENV = (
    "DOCURAPI_OBJECT_STORAGE_MIRROR_REQUIRED"
)


PATH_FIELDS = frozenset({
    "input_path",
    "output_path",
    "report_path",
    "artifact_path",
    "file_path",
    "local_file_path",
    "template_path",
    "target_path",
    "download_path",
    "upload_path",
})


MAPPING_PARAMETER_NAMES = frozenset({
    "fields",
    "updates",
    "changes",
    "values",
    "payload",
    "data",
    "kwargs",
})


RESOURCE_ID_FIELDS = (
    "job_id",
    "template_id",
    "email_id",
    "notification_id",
    "resource_id",
    "reservation_id",
    "order_id",
    "token_id",
    "user_id",
)


FIELD_CATEGORIES = {
    "input_path":
        "job-inputs",

    "upload_path":
        "uploads",

    "target_path":
        "background-targets",

    "output_path":
        "job-outputs",

    "report_path":
        "job-reports",

    "artifact_path":
        "background-artifacts",

    "file_path":
        "templates",

    "template_path":
        "templates",

    "local_file_path":
        "email-outbox",

    "download_path":
        "downloads",
}


@dataclass(frozen=True)
class MirrorRecord:
    field_name: str
    local_path: str
    object_key: str
    object_reference: str
    size: int
    backend: str


def _environment_boolean(
    name: str,
    default: bool,
) -> bool:
    value = os.environ.get(
        name,
        "",
    ).strip().lower()

    if not value:
        return default

    if value in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }:
        return True

    if value in {
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }:
        return False

    raise RuntimeError(
        f"Environment variable {name} "
        "harus berupa true atau false."
    )


def mirror_enabled() -> bool:
    return _environment_boolean(
        MIRROR_ENABLED_ENV,
        True,
    )


def mirror_required() -> bool:
    return _environment_boolean(
        MIRROR_REQUIRED_ENV,
        False,
    )


def _string_value(
    value: Any,
) -> str | None:
    if isinstance(
        value,
        (
            str,
            os.PathLike,
        ),
    ):
        return os.fspath(
            value
        )

    return None


def _resource_context(
    arguments: Mapping[str, Any],
) -> tuple[
    str | None,
    str | None,
    str | None,
]:
    user_id = arguments.get(
        "user_id"
    )

    workspace_id = arguments.get(
        "workspace_id"
    )

    resource_id = None

    for field in RESOURCE_ID_FIELDS:
        value = arguments.get(
            field
        )

        if value not in {
            None,
            "",
        }:
            resource_id = str(
                value
            )

            break

    return (
        (
            str(user_id)
            if user_id not in {
                None,
                "",
            }
            else None
        ),
        (
            str(workspace_id)
            if workspace_id not in {
                None,
                "",
            }
            else None
        ),
        resource_id,
    )


def _fallback_resource_id(
    path: Path,
) -> str:
    return hashlib.sha256(
        str(path).encode(
            "utf-8"
        )
    ).hexdigest()[:20]


def mirror_local_file(
    value: Any,
    *,
    field_name: str,
    arguments: Mapping[str, Any] | None = None,
    module_name: str = "",
    bridge: HybridStorageBridge | None = None,
) -> MirrorRecord | None:
    if not mirror_enabled():
        return None

    path_value = _string_value(
        value
    )

    if not path_value:
        return None

    if is_object_reference(
        path_value
    ):
        return None

    try:
        path = Path(
            path_value
        ).expanduser().resolve()

    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        return None

    try:
        is_file = path.is_file()
    except OSError:
        return None

    if not is_file:
        return None

    context = dict(
        arguments or {}
    )

    user_id, workspace_id, resource_id = (
        _resource_context(
            context
        )
    )

    if resource_id is None:
        resource_id = (
            _fallback_resource_id(
                path
            )
        )

    category = FIELD_CATEGORIES.get(
        field_name,
        "runtime-files",
    )

    if (
        field_name == "file_path"
        and "notification" in module_name
    ):
        category = "email-outbox"

    object_key = build_object_key(
        category,
        path.name,
        user_id=user_id,
        workspace_id=workspace_id,
        resource_id=resource_id,
    )

    selected_bridge = (
        bridge
        if bridge is not None
        else create_storage_bridge(
            enabled=False,
            preserve_local=True,
        )
    )

    stored = selected_bridge.persist_file(
        path,
        object_key,
        activate=False,
        remove_source=False,
    )

    record_mirror(
        local_path=path,
        object_reference=
            stored.object_reference,
        object_key=
            stored.object_key,
        field_name=
            field_name,
        module_name=
            module_name,
        backend=
            stored.backend,
        size=
            stored.size,
    )

    LOGGER.info(
        "File mirrored: field=%s local=%s object=%s",
        field_name,
        path,
        stored.object_reference,
    )

    return MirrorRecord(
        field_name=field_name,
        local_path=str(path),
        object_key=stored.object_key,
        object_reference=
            stored.object_reference,
        size=stored.size,
        backend=stored.backend,
    )


def _mapping_path_values(
    value: Any,
) -> list[
    tuple[str, Any]
]:
    if not isinstance(
        value,
        Mapping,
    ):
        return []

    return [
        (
            str(key),
            nested_value,
        )
        for key, nested_value
        in value.items()
        if str(key) in PATH_FIELDS
    ]


def mirror_call_arguments(
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    module_name: str,
) -> list[MirrorRecord]:
    if not mirror_enabled():
        return []

    try:
        bound = signature.bind_partial(
            *args,
            **kwargs,
        )
    except TypeError:
        return []

    arguments = dict(
        bound.arguments
    )

    bridge = create_storage_bridge(
        enabled=False,
        preserve_local=True,
    )

    records: list[
        MirrorRecord
    ] = []

    for name, value in arguments.items():
        if name in PATH_FIELDS:
            record = mirror_local_file(
                value,
                field_name=name,
                arguments=arguments,
                module_name=module_name,
                bridge=bridge,
            )

            if record is not None:
                records.append(
                    record
                )

        if (
            name in MAPPING_PARAMETER_NAMES
            or isinstance(
                value,
                Mapping,
            )
        ):
            for (
                nested_name,
                nested_value,
            ) in _mapping_path_values(
                value
            ):
                record = mirror_local_file(
                    nested_value,
                    field_name=
                        nested_name,
                    arguments=arguments,
                    module_name=
                        module_name,
                    bridge=bridge,
                )

                if record is not None:
                    records.append(
                        record
                    )

    return records


def _function_requires_mirror(
    function: Any,
) -> bool:
    try:
        signature = inspect.signature(
            function
        )
    except (
        TypeError,
        ValueError,
    ):
        return False

    parameters = signature.parameters

    if any(
        name in PATH_FIELDS
        for name in parameters
    ):
        return True

    function_name = getattr(
        function,
        "__name__",
        "",
    ).lower()

    has_variable_keywords = any(
        parameter.kind
        == inspect.Parameter.VAR_KEYWORD
        for parameter
        in parameters.values()
    )

    has_mapping_parameter = any(
        name in MAPPING_PARAMETER_NAMES
        for name in parameters
    )

    action_function = any(
        token in function_name
        for token in (
            "create",
            "insert",
            "update",
            "complete",
            "finish",
            "mark",
            "queue",
            "enqueue",
            "save",
            "set",
        )
    )

    return (
        action_function
        and (
            has_variable_keywords
            or has_mapping_parameter
        )
    )


def _decorate_function(
    function: Any,
    *,
    module_name: str,
) -> Any:
    if getattr(
        function,
        "__docurapi_storage_mirror__",
        False,
    ):
        return function

    signature = inspect.signature(
        function
    )

    if inspect.iscoroutinefunction(
        function
    ):
        @functools.wraps(
            function
        )
        async def async_wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            try:
                mirror_call_arguments(
                    signature,
                    args,
                    kwargs,
                    module_name=
                        module_name,
                )
            except Exception:
                if mirror_required():
                    raise

                LOGGER.exception(
                    "Object storage mirror gagal "
                    "pada %s.%s",
                    module_name,
                    function.__name__,
                )

            return await function(
                *args,
                **kwargs,
            )

        async_wrapper\
            .__docurapi_storage_mirror__ = True

        return async_wrapper

    @functools.wraps(
        function
    )
    def wrapper(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        try:
            mirror_call_arguments(
                signature,
                args,
                kwargs,
                module_name=
                    module_name,
            )
        except Exception:
            if mirror_required():
                raise

            LOGGER.exception(
                "Object storage mirror gagal "
                "pada %s.%s",
                module_name,
                function.__name__,
            )

        return function(
            *args,
            **kwargs,
        )

    wrapper\
        .__docurapi_storage_mirror__ = True

    return wrapper


def install_module_file_mirroring(
    namespace: MutableMapping[
        str,
        Any,
    ],
    *,
    module_name: str,
) -> tuple[str, ...]:
    wrapped_names: list[str] = []

    for name, value in list(
        namespace.items()
    ):
        if not inspect.isfunction(
            value
        ):
            continue

        if getattr(
            value,
            "__module__",
            None,
        ) != module_name:
            continue

        if not _function_requires_mirror(
            value
        ):
            continue

        decorated = _decorate_function(
            value,
            module_name=module_name,
        )

        namespace[name] = decorated
        wrapped_names.append(
            name
        )

    result = tuple(
        sorted(
            wrapped_names
        )
    )

    namespace[
        "_DOCURAPI_STORAGE_MIRRORED_FUNCTIONS"
    ] = result

    return result

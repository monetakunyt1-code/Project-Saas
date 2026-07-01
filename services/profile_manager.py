from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from services.format_rules import normalize_rules


BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIRECTORY = BASE_DIR / "storage" / "profiles"
PROFILE_FILE = PROFILE_DIRECTORY / "profiles.json"

_LOCK = RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage() -> None:
    PROFILE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not PROFILE_FILE.exists():
        PROFILE_FILE.write_text(
            json.dumps(
                {"profiles": []},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _read_data() -> dict[str, Any]:
    ensure_storage()

    try:
        data = json.loads(
            PROFILE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        data = {"profiles": []}

    if not isinstance(data, dict):
        data = {"profiles": []}

    if not isinstance(data.get("profiles"), list):
        data["profiles"] = []

    return data


def _write_data(
    data: dict[str, Any],
) -> None:
    ensure_storage()

    temporary_file = PROFILE_FILE.with_suffix(
        ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        PROFILE_FILE
    )


def list_profiles() -> list[dict[str, Any]]:
    with _LOCK:
        profiles = _read_data()["profiles"]

    return sorted(
        profiles,
        key=lambda item: item.get(
            "created_at",
            "",
        ),
        reverse=True,
    )


def get_profile(
    profile_id: str,
) -> dict[str, Any] | None:
    for profile in list_profiles():
        if profile.get("profile_id") == profile_id:
            return profile

    return None


def create_profile(
    name: str,
    rules: dict[str, Any],
    description: str = "",
) -> dict[str, Any]:
    clean_name = name.strip()

    if not clean_name:
        raise ValueError(
            "Nama profil wajib diisi."
        )

    normalized_rules = normalize_rules(
        rules
    )

    if not normalized_rules:
        raise ValueError(
            "Profil harus memiliki sedikitnya satu aturan."
        )

    profile = {
        "profile_id": uuid4().hex,
        "name": clean_name,
        "description": description.strip(),
        "rules": normalized_rules,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }

    with _LOCK:
        data = _read_data()
        data["profiles"].append(profile)
        _write_data(data)

    return profile


def update_profile(
    profile_id: str,
    name: str,
    rules: dict[str, Any],
    description: str = "",
) -> dict[str, Any] | None:
    normalized_rules = normalize_rules(
        rules
    )

    with _LOCK:
        data = _read_data()

        for profile in data["profiles"]:
            if profile.get("profile_id") != profile_id:
                continue

            profile["name"] = name.strip()
            profile["description"] = description.strip()
            profile["rules"] = normalized_rules
            profile["updated_at"] = utc_now()

            _write_data(data)
            return profile

    return None


def delete_profile(
    profile_id: str,
) -> dict[str, Any] | None:
    with _LOCK:
        data = _read_data()

        for index, profile in enumerate(
            data["profiles"]
        ):
            if profile.get("profile_id") != profile_id:
                continue

            removed = data["profiles"].pop(
                index
            )

            _write_data(data)
            return removed

    return None
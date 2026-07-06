from __future__ import annotations

from pathlib import Path
from typing import Any

from docurapi.core.settings import settings
from docurapi.db.connection import connect, utc_now


def register_template(
    template_id: str,
    template_name: str,
    institution_name: str,
    document_type: str,
    file_name: str,
    file_path: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO templates (
                template_id, template_name, institution_name,
                document_type, file_name, file_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                template_name,
                institution_name,
                document_type,
                file_name,
                file_path,
                utc_now(),
            ),
        )
        connection.commit()


def list_templates() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM templates
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_template(template_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM templates WHERE template_id = ?",
            (template_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_template(template_id: str) -> dict[str, Any] | None:
    template = get_template(template_id)

    if not template:
        return None

    with connect() as connection:
        connection.execute(
            "DELETE FROM templates WHERE template_id = ?",
            (template_id,),
        )
        connection.commit()

    return template


def remove_template_file(template: dict[str, Any]) -> None:
    raw_path = template.get("file_path")

    if not raw_path:
        return

    path = Path(raw_path)

    try:
        path.relative_to(settings.STORAGE_DIR)
    except ValueError:
        return

    if path.exists() and path.is_file():
        path.unlink(missing_ok=True)

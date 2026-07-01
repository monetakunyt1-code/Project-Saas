from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document


def _safe_number(
    value: Any,
    attribute: str,
) -> float | None:
    try:
        return round(
            getattr(value, attribute),
            2,
        )
    except (AttributeError, TypeError):
        return None


def extract_template_rules(
    template_path: str | Path,
) -> dict[str, Any]:
    document = Document(template_path)

    normal_style = document.styles["Normal"]
    heading_1 = document.styles["Heading 1"]
    heading_2 = document.styles["Heading 2"]
    heading_3 = document.styles["Heading 3"]

    section = document.sections[0]

    font_name = normal_style.font.name or "Times New Roman"

    font_size = (
        normal_style.font.size.pt
        if normal_style.font.size
        else 12
    )

    heading_1_size = (
        heading_1.font.size.pt
        if heading_1.font.size
        else 14
    )

    heading_2_size = (
        heading_2.font.size.pt
        if heading_2.font.size
        else 12
    )

    heading_3_size = (
        heading_3.font.size.pt
        if heading_3.font.size
        else 12
    )

    line_spacing = (
        normal_style.paragraph_format.line_spacing
        if isinstance(
            normal_style.paragraph_format.line_spacing,
            (int, float),
        )
        else 1.5
    )

    first_line_indent = (
        normal_style.paragraph_format.first_line_indent
    )

    return {
        "font": font_name,
        "font_size": round(font_size, 2),
        "table_font_size": max(
            round(font_size - 2, 2),
            8,
        ),
        "line_spacing": float(line_spacing),
        "first_line_indent_cm": (
            round(first_line_indent.cm, 2)
            if first_line_indent
            else 1.25
        ),
        "margin_top_cm": _safe_number(
            section.top_margin,
            "cm",
        ) or 3,
        "margin_bottom_cm": _safe_number(
            section.bottom_margin,
            "cm",
        ) or 3,
        "margin_left_cm": _safe_number(
            section.left_margin,
            "cm",
        ) or 3,
        "margin_right_cm": _safe_number(
            section.right_margin,
            "cm",
        ) or 3,
        "heading_1_size": round(
            heading_1_size,
            2,
        ),
        "heading_2_size": round(
            heading_2_size,
            2,
        ),
        "heading_3_size": round(
            heading_3_size,
            2,
        ),
    }
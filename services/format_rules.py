from __future__ import annotations

from typing import Any


RULE_LIMITS: dict[str, tuple[float, float]] = {
    "font_size": (8, 24),
    "table_font_size": (7, 18),
    "line_spacing": (1, 3),
    "first_line_indent_cm": (0, 3),
    "margin_top_cm": (1, 6),
    "margin_bottom_cm": (1, 6),
    "margin_left_cm": (1, 6),
    "margin_right_cm": (1, 6),
    "heading_1_size": (9, 28),
    "heading_2_size": (8, 24),
    "heading_3_size": (8, 22),
}

ALLOWED_RULES = {
    "font",
    *RULE_LIMITS.keys(),
}


class FormatRuleError(ValueError):
    """Kesalahan pada aturan format pengguna."""


def parse_number(
    value: Any,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = value

    try:
        number = float(cleaned)
    except (TypeError, ValueError) as exc:
        raise FormatRuleError(
            f"Nilai {field_name} harus berupa angka."
        ) from exc

    minimum, maximum = RULE_LIMITS[field_name]

    if number < minimum or number > maximum:
        raise FormatRuleError(
            f"Nilai {field_name} harus berada antara "
            f"{minimum} dan {maximum}."
        )

    return round(number, 2)


def normalize_rules(
    raw_rules: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    font = str(raw_rules.get("font") or "").strip()

    if font:
        if len(font) > 80:
            raise FormatRuleError(
                "Nama font tidak boleh melebihi 80 karakter."
            )

        normalized["font"] = font

    for field_name in RULE_LIMITS:
        number = parse_number(
            raw_rules.get(field_name),
            field_name,
        )

        if number is not None:
            normalized[field_name] = number

    return normalized


def merge_format_rules(
    *rule_sources: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    for rules in rule_sources:
        if not rules:
            continue

        normalized = normalize_rules(rules)
        merged.update(normalized)

    return merged


def describe_rules(
    rules: dict[str, Any],
) -> list[dict[str, str]]:
    labels = {
        "font": "Jenis font",
        "font_size": "Ukuran isi",
        "table_font_size": "Ukuran tabel",
        "line_spacing": "Spasi baris",
        "first_line_indent_cm": "Indentasi baris pertama",
        "margin_top_cm": "Margin atas",
        "margin_bottom_cm": "Margin bawah",
        "margin_left_cm": "Margin kiri",
        "margin_right_cm": "Margin kanan",
        "heading_1_size": "Ukuran Heading 1",
        "heading_2_size": "Ukuran Heading 2",
        "heading_3_size": "Ukuran Heading 3",
    }

    result: list[dict[str, str]] = []

    for key, value in rules.items():
        if key not in ALLOWED_RULES:
            continue

        unit = ""

        if key.endswith("_cm"):
            unit = " cm"
        elif "size" in key:
            unit = " pt"

        result.append(
            {
                "key": key,
                "label": labels.get(key, key),
                "value": f"{value}{unit}",
            }
        )

    return result
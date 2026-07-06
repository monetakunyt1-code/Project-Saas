from __future__ import annotations

from fastapi import HTTPException

from docurapi.core.settings import settings


PRICE_MODE_MAP = {
    "analyze": "PRICE_ANALYZE",
    "format": "PRICE_FORMAT",
    "journal": "PRICE_JOURNAL",
}


def get_available_prices() -> dict[str, int]:
    return {
        "analyze": settings.PRICE_ANALYZE,
        "format": settings.PRICE_FORMAT,
        "journal": settings.PRICE_JOURNAL,
    }


def get_processing_price(mode: str) -> int:
    normalized_mode = mode.lower().strip()

    if normalized_mode not in PRICE_MODE_MAP:
        raise HTTPException(
            status_code=400,
            detail="Mode pemrosesan tidak valid untuk pricing.",
        )

    price = get_available_prices()[normalized_mode]

    if price <= 0:
        raise HTTPException(
            status_code=500,
            detail=f"Harga untuk mode {normalized_mode} tidak valid.",
        )

    return price

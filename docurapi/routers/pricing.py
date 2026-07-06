from __future__ import annotations

from fastapi import APIRouter

from docurapi.services.pricing_service import get_available_prices

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("")
def pricing_list() -> dict:
    prices = get_available_prices()

    return {
        "success": True,
        "currency": "IDR",
        "prices": prices,
        "notes": {
            "analyze": "Analisis struktur dokumen.",
            "format": "Perapihan format dokumen akademik.",
            "journal": "Pembuatan draft awal artikel jurnal.",
        },
    }

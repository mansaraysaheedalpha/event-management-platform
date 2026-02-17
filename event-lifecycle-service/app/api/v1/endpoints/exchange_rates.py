# app/api/v1/endpoints/exchange_rates.py
"""Public exchange rate endpoint."""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query

from app.utils.exchange_rates import get_exchange_rates_sync

router = APIRouter(tags=["Exchange Rates"])


@router.get("/exchange-rates")
def get_exchange_rates(
    base: str = Query(..., description="Base currency code, e.g. KES"),
    targets: Optional[str] = Query(
        None,
        description="Comma-separated target currencies, e.g. USD,NGN,SLE",
    ),
):
    """Get current cached exchange rates. Public, no auth required."""
    target_list = [t.strip() for t in targets.split(",")] if targets else None

    data = get_exchange_rates_sync(base, targets=target_list)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Exchange rates unavailable. Try again later.",
        )

    return data

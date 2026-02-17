# app/utils/exchange_rates.py
"""
Exchange rate service — fetches rates from external API and caches in Redis.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

import httpx

from app.db.redis import redis_client

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 25 * 3600  # 25 hours
REDIS_KEY_PREFIX = "exchange_rates:"
API_URL = "https://open.er-api.com/v6/latest/{base}"
FALLBACK_API_URL = "https://api.exchangerate-api.com/v4/latest/{base}"

# African + common currencies
DEFAULT_CURRENCIES = ["USD", "KES", "NGN", "SLE", "ZAR", "GHS", "TZS", "UGX", "RWF", "EUR", "GBP"]


def get_exchange_rates_sync(
    base: str,
    targets: Optional[List[str]] = None,
) -> Optional[dict]:
    """
    Get exchange rates from Redis cache, falling back to API on cache miss.
    Returns dict with 'base', 'rates', 'fetched_at', 'source'.
    """
    base = base.upper()
    cache_key = f"{REDIS_KEY_PREFIX}{base}"

    # Try cache first
    try:
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            if targets:
                data["rates"] = {
                    k: v for k, v in data["rates"].items() if k in [t.upper() for t in targets]
                }
            return data
    except Exception as e:
        logger.warning(f"Redis cache read failed for exchange rates: {e}")

    # Cache miss — fetch from API
    data = _fetch_from_api(base)
    if not data:
        return None

    # Cache the full result
    try:
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(data))
    except Exception as e:
        logger.warning(f"Redis cache write failed for exchange rates: {e}")

    # Filter targets if specified
    if targets:
        data["rates"] = {
            k: v for k, v in data["rates"].items() if k in [t.upper() for t in targets]
        }

    return data


def convert_amount(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """Convert an amount from one currency to another using cached rates."""
    if from_currency == to_currency:
        return amount

    # Get rates with 'from_currency' as base
    rates_data = get_exchange_rates_sync(from_currency, targets=[to_currency])
    if not rates_data or to_currency.upper() not in rates_data.get("rates", {}):
        return None

    rate = rates_data["rates"][to_currency.upper()]
    return round(amount * rate, 2)


def fetch_and_cache_rates(base: str) -> Optional[dict]:
    """Fetch from API and store in Redis. Called by Celery task."""
    base = base.upper()
    data = _fetch_from_api(base)
    if not data:
        return None

    cache_key = f"{REDIS_KEY_PREFIX}{base}"
    try:
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(data))
        logger.info(f"Cached exchange rates for {base}")
    except Exception as e:
        logger.error(f"Failed to cache exchange rates for {base}: {e}")

    return data


def _fetch_from_api(base: str) -> Optional[dict]:
    """Fetch exchange rates from the API."""
    for url_template in [API_URL, FALLBACK_API_URL]:
        url = url_template.format(base=base)
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                api_data = response.json()
                rates = api_data.get("rates", {})
                return {
                    "base": base,
                    "rates": rates,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "source": "exchangerate-api.com",
                }
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates from {url}: {e}")
            continue

    logger.error(f"All exchange rate API sources failed for base {base}")
    return None

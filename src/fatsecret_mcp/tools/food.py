import asyncio
import os
import time
from typing import Any

import requests

from ..auth.oauth1 import get_authenticator


def _request(method: str, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(5):
        try:
            payload = get_authenticator().make_authenticated_request(method, endpoint, params)
            if payload.get("error"):
                raise requests.HTTPError(str(payload["error"]))
            return payload
        except requests.RequestException as error:
            status = getattr(error.response, "status_code", None)
            if attempt == 4 or (status is not None and status not in {429, 500, 502, 503, 504}):
                raise
            retry_after = getattr(error.response, "headers", {}).get("Retry-After")
            time.sleep(float(retry_after) if retry_after else 2 ** attempt)
    return {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    return [value] if isinstance(value, dict) else value


async def food_search_tool(
    query: str,
    max_results: int = 10,
    page_number: int = 0,
    region: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50")
    region = (region or os.getenv("FATSECRET_REGION", "ES")).upper()
    language = (language or os.getenv("FATSECRET_LANGUAGE", "es")).lower()
    payload = await asyncio.to_thread(
        _request,
        "GET",
        "/foods/search/v1",
        {
            "search_expression": query,
            "max_results": max_results,
            "page_number": page_number,
            "region": region,
            "language": language,
            "format": "json",
        },
    )
    foods = (payload.get("foods") or {}).get("food")
    return _as_list(foods)


async def food_servings_tool(
    food_id: str,
    region: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    region = (region or os.getenv("FATSECRET_REGION", "ES")).upper()
    language = (language or os.getenv("FATSECRET_LANGUAGE", "es")).lower()
    payload = await asyncio.to_thread(
        _request,
        "GET",
        "/food/v5",
        {"food_id": food_id, "region": region, "language": language, "format": "json"},
    )
    food = payload.get("food") or {}
    servings = (food.get("servings") or {}).get("serving")
    food["servings"] = _as_list(servings)
    return food


async def validate_food_serving(food_id: str, serving_id: str) -> dict[str, Any]:
    food = await food_servings_tool(food_id)
    serving = next(
        (item for item in food.get("servings", []) if str(item.get("serving_id")) == str(serving_id)),
        None,
    )
    if not serving:
        raise ValueError("food_id or serving_id is unavailable for the configured ES/es catalog")
    return {"food": food, "serving": serving}

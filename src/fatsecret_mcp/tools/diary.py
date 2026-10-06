"""Read-only FatSecret food diary access."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests

from ..auth.oauth1 import get_authenticator, make_api_call
from .food import validate_food_serving

EPOCH = date(1970, 1, 1)


def _date_int(value: date) -> int:
    return (value - EPOCH).days


def _as_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    container = payload.get("food_entries") or {}
    entries = container.get("food_entry") if isinstance(container, dict) else None
    if not entries:
        return []
    if isinstance(entries, dict):
        return [entries]
    return entries


def _fetch_day(value: date) -> list[dict[str, Any]]:
    for attempt in range(5):
        try:
            payload = make_api_call(
                "/food-entries/v2",
                {"date": _date_int(value), "format": "json"},
            )
            if payload.get("error"):
                raise requests.HTTPError(str(payload["error"]))
            entries = _as_entries(payload)
            for entry in entries:
                entry["date"] = (EPOCH + timedelta(days=int(entry["date_int"]))).isoformat()
            return entries
        except requests.RequestException as error:
            status = getattr(error.response, "status_code", None)
            if attempt == 4 or (status is not None and status not in {429, 500, 502, 503, 504}):
                raise
            retry_after = getattr(error.response, "headers", {}).get("Retry-After")
            delay = float(retry_after) if retry_after else 2 ** attempt
            import time
            time.sleep(delay)
    return []


async def get_diary_entries(date_from: str = None, date_to: str = None) -> list[dict[str, Any]]:
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else datetime.now(UTC).date()
    start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else end - timedelta(days=89)
    if start > end:
        raise ValueError("date_from must be before or equal to date_to")
    entries: list[dict[str, Any]] = []
    current = start
    while current <= end:
        entries.extend(await asyncio.to_thread(_fetch_day, current))
        current += timedelta(days=1)
        await asyncio.sleep(1)
    unique = {str(entry.get("food_entry_id")): entry for entry in entries}
    return sorted(unique.values(), key=lambda item: (item.get("date", ""), str(item.get("food_entry_id", ""))))


def _require_success(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    if payload.get("error"):
        raise ValueError(f"FatSecret {operation} failed: {payload['error']}")
    return payload


def _entry_id(payload: dict[str, Any]) -> str | None:
    entry = payload.get("food_entry") or (payload.get("food_entries") or {}).get("food_entry")
    if isinstance(entry, list):
        entry = entry[0] if entry else None
    if isinstance(entry, dict) and entry.get("food_entry_id"):
        return str(entry["food_entry_id"])
    if payload.get("food_entry_id"):
        return str(payload["food_entry_id"])
    return None


def _fetch_entry(
    food_entry_id: str,
    allow_missing: bool = False,
    entry_date: date | None = None,
) -> dict[str, Any] | None:
    dates = [entry_date] if entry_date else [date.today() - timedelta(days=offset) for offset in range(93)]
    for value in dates:
        for entry in _fetch_day(value):
            if str(entry.get("food_entry_id")) == str(food_entry_id):
                return entry
    if allow_missing:
        return None
    raise ValueError("food_entry_id was not found in the supported 93-day verification window")


async def create_diary_entry(
    food_id: str,
    food_entry_name: str,
    serving_id: str,
    number_of_units: float,
    meal: str,
    entry_date: str,
) -> dict[str, Any]:
    meal = meal.lower()
    if meal not in {"breakfast", "lunch", "dinner", "other"}:
        raise ValueError("meal must be breakfast, lunch, dinner, or other")
    if number_of_units <= 0:
        raise ValueError("number_of_units must be greater than zero")
    value = datetime.strptime(entry_date, "%Y-%m-%d").date()
    validated = await validate_food_serving(food_id, serving_id)
    canonical_name = validated["food"].get("food_name") or food_entry_name
    params = {
        "food_id": food_id,
        "food_entry_name": canonical_name,
        "serving_id": serving_id,
        "number_of_units": number_of_units,
        "meal": meal,
        "date": _date_int(value),
        "format": "json",
    }
    payload = await asyncio.to_thread(
        get_authenticator().make_authenticated_request,
        "POST",
        "/food-entries/v1",
        params,
    )
    _require_success(payload, "create")
    food_entry_id = _entry_id(payload)
    if not food_entry_id:
        raise ValueError("FatSecret create returned no food_entry_id; result cannot be verified")
    created = await asyncio.to_thread(_fetch_entry, food_entry_id, False, value)
    consistent = created and all(
        str(created.get(key)) == str(expected)
        for key, expected in {
            "food_id": food_id,
            "serving_id": serving_id,
            "date_int": _date_int(value),
        }.items()
    ) and str(created.get("meal", "")).lower() == meal
    if not consistent:
        rollback = await asyncio.to_thread(
            get_authenticator().make_authenticated_request,
            "DELETE",
            "/food-entries/v1",
            {"food_entry_id": food_entry_id, "format": "json"},
        )
        _require_success(rollback, "rollback")
        raise ValueError("Created entry failed verification and was automatically removed")
    created["verified_in_platform_api"] = True
    created["visible_in_fatsecret_app"] = "unknown"
    created["warning"] = (
        "FatSecret Platform API stored and returned this entry, but the consumer FatSecret "
        "web/mobile app may not synchronize API-created diary entries. Do not claim app "
        "visibility unless the user confirms it."
    )
    return created


async def edit_diary_entry(
    food_entry_id: str,
    food_entry_name: str | None = None,
    serving_id: str | None = None,
    number_of_units: float | None = None,
    meal: str | None = None,
) -> dict[str, Any]:
    if meal is not None:
        meal = meal.lower()
        if meal not in {"breakfast", "lunch", "dinner", "other"}:
            raise ValueError("meal must be breakfast, lunch, dinner, or other")
    params: dict[str, Any] = {"food_entry_id": food_entry_id, "format": "json"}
    optional = {
        "food_entry_name": food_entry_name,
        "serving_id": serving_id,
        "number_of_units": number_of_units,
        "meal": meal,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    if len(params) == 2:
        raise ValueError("provide at least one field to edit")
    current = await asyncio.to_thread(_fetch_entry, food_entry_id)
    if serving_id is not None:
        await validate_food_serving(str(current.get("food_id")), serving_id)
    current_date = EPOCH + timedelta(days=int(current["date_int"]))
    payload = await asyncio.to_thread(
        get_authenticator().make_authenticated_request,
        "PUT",
        "/food-entries/v1",
        params,
    )
    _require_success(payload, "edit")
    updated = await asyncio.to_thread(_fetch_entry, food_entry_id, False, current_date)
    if not updated:
        raise ValueError("Edited entry could not be verified")
    updated["verified"] = True
    return updated


async def delete_diary_entry(food_entry_id: str) -> dict[str, Any]:
    current = await asyncio.to_thread(_fetch_entry, food_entry_id)
    current_date = EPOCH + timedelta(days=int(current["date_int"]))
    payload = await asyncio.to_thread(
        get_authenticator().make_authenticated_request,
        "DELETE",
        "/food-entries/v1",
        {"food_entry_id": food_entry_id, "format": "json"},
    )
    _require_success(payload, "delete")
    remaining = await asyncio.to_thread(_fetch_entry, food_entry_id, True, current_date)
    if remaining:
        raise ValueError("Deleted entry is still present")
    return {"success": True, "food_entry_id": food_entry_id, "verified": True}


async def diary_entries_list_tool(date_from: str = None, date_to: str = None) -> list[dict[str, Any]]:
    return await get_diary_entries(date_from, date_to)

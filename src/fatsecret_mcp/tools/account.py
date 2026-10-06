import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from ..auth.oauth1 import get_authenticator
from .diary import EPOCH, _date_int, _require_success, create_diary_entry, delete_diary_entry
from .food import _as_list, validate_food_serving

MEALS = {"breakfast", "lunch", "dinner", "other"}


def _call(method: str, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = get_authenticator().make_authenticated_request(
        method,
        endpoint,
        {**(params or {}), "format": "json"},
    )
    return _require_success(payload, endpoint)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _meal(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.lower()
    if value not in MEALS:
        raise ValueError("meal must be breakfast, lunch, dinner, or other")
    return value


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a positive number") from error
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _extract_id(payload: Any, key: str) -> str | None:
    if isinstance(payload, dict):
        if payload.get(key) is not None:
            return str(payload[key])
        for value in payload.values():
            found = _extract_id(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _extract_id(value, key)
            if found is not None:
                return found
    return None


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    return (EPOCH + timedelta(days=int(value))).isoformat()


def _dated_days(payload: dict[str, Any]) -> dict[str, Any]:
    month = payload.get("month") or {}
    days = _as_list(month.get("day"))
    for day in days:
        day["date"] = _iso_date(day.get("date_int"))
    month["day"] = days
    return month


async def get_profile() -> dict[str, Any]:
    payload = await asyncio.to_thread(_call, "GET", "/profile/v1")
    profile = payload.get("profile") or {}
    if "last_weight_date_int" in profile:
        profile["last_weight_date"] = _iso_date(profile["last_weight_date_int"])
    return profile


async def get_weight_month(month_date: str | None = None) -> dict[str, Any]:
    value = _parse_date(month_date) if month_date else date.today()
    payload = await asyncio.to_thread(_call, "GET", "/weight/month/v2", {"date": _date_int(value)})
    return _dated_days(payload)


async def update_weight(
    current_weight_kg: float,
    entry_date: str,
    goal_weight_kg: float | None = None,
    current_height_cm: float | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    value = _parse_date(entry_date)
    params: dict[str, Any] = {
        "current_weight_kg": _positive(current_weight_kg, "current_weight_kg"),
        "date": _date_int(value),
    }
    if goal_weight_kg is not None:
        params["goal_weight_kg"] = _positive(goal_weight_kg, "goal_weight_kg")
    if current_height_cm is not None:
        params["current_height_cm"] = _positive(current_height_cm, "current_height_cm")
    if comment is not None:
        params["comment"] = comment
    await asyncio.to_thread(_call, "POST", "/weight/v1", params)
    month = await get_weight_month(entry_date)
    expected = float(params["current_weight_kg"])
    matching = next(
        (
            day for day in month.get("day", [])
            if day.get("date") == entry_date
            and abs(float(day.get("weight_kg", day.get("weight", -1))) - expected) < 0.001
        ),
        None,
    )
    return {"success": True, "date": entry_date, "current_weight_kg": expected, "verified": matching is not None, "entry": matching}


async def get_saved_meals(meal: str | None = None) -> list[dict[str, Any]]:
    normalized = _meal(meal)
    payload = await asyncio.to_thread(_call, "GET", "/saved-meals/v2", {"meal": normalized} if normalized else {})
    return _as_list((payload.get("saved_meals") or {}).get("saved_meal"))


async def get_saved_meal_items(saved_meal_id: str) -> list[dict[str, Any]]:
    payload = await asyncio.to_thread(_call, "GET", "/saved-meals/item/v2", {"saved_meal_id": saved_meal_id})
    return _as_list((payload.get("saved_meal_items") or {}).get("saved_meal_item"))


async def create_saved_meal(saved_meal_name: str, meals: str, saved_meal_description: str | None = None) -> dict[str, Any]:
    if not saved_meal_name.strip():
        raise ValueError("saved_meal_name must not be empty")
    normalized = ",".join(_meal(value.strip()) or "" for value in meals.split(","))
    params = {"saved_meal_name": saved_meal_name, "meals": normalized}
    if saved_meal_description is not None:
        params["saved_meal_description"] = saved_meal_description
    payload = await asyncio.to_thread(_call, "POST", "/saved-meals/v1", params)
    saved_meal_id = _extract_id(payload, "saved_meal_id")
    saved_meals = await get_saved_meals()
    created = next((item for item in saved_meals if saved_meal_id and str(item.get("saved_meal_id")) == saved_meal_id), None)
    if created is None:
        created = next((item for item in saved_meals if item.get("saved_meal_name") == saved_meal_name), None)
        saved_meal_id = str(created["saved_meal_id"]) if created else saved_meal_id
    return {"success": True, "saved_meal_id": saved_meal_id, "saved_meal": created, "verified": created is not None}


async def edit_saved_meal(saved_meal_id: str, saved_meal_name: str | None = None, meals: str | None = None, saved_meal_description: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"saved_meal_id": saved_meal_id}
    if saved_meal_name is not None:
        if not saved_meal_name.strip():
            raise ValueError("saved_meal_name must not be empty")
        params["saved_meal_name"] = saved_meal_name
    if meals is not None:
        params["meals"] = ",".join(_meal(value.strip()) or "" for value in meals.split(","))
    if saved_meal_description is not None:
        params["saved_meal_description"] = saved_meal_description
    if len(params) == 1:
        raise ValueError("provide saved_meal_name, meals, or saved_meal_description")
    await asyncio.to_thread(_call, "PUT", "/saved-meals/v1", params)
    meals = await get_saved_meals()
    updated = next((item for item in meals if str(item.get("saved_meal_id")) == str(saved_meal_id)), None)
    verified = updated is not None and all(str(updated.get(key)).lower() == str(expected).lower() for key, expected in params.items() if key != "saved_meal_id")
    return {"success": True, "saved_meal_id": saved_meal_id, "saved_meal": updated, "verified": verified}


async def delete_saved_meal(saved_meal_id: str) -> dict[str, Any]:
    await asyncio.to_thread(_call, "DELETE", "/saved-meals/v1", {"saved_meal_id": saved_meal_id})
    meals = await get_saved_meals()
    present = any(str(item.get("saved_meal_id")) == str(saved_meal_id) for item in meals)
    return {"success": True, "saved_meal_id": saved_meal_id, "verified": not present}


async def add_saved_meal_item(saved_meal_id: str, food_id: str, serving_id: str, number_of_units: float) -> dict[str, Any]:
    units = _positive(number_of_units, "number_of_units")
    await validate_food_serving(food_id, serving_id)
    payload = await asyncio.to_thread(_call, "POST", "/saved-meals/item/v1", {"saved_meal_id": saved_meal_id, "food_id": food_id, "serving_id": serving_id, "number_of_units": units})
    item_id = _extract_id(payload, "saved_meal_item_id")
    items = await get_saved_meal_items(saved_meal_id)
    item = next((entry for entry in items if item_id and str(entry.get("saved_meal_item_id")) == item_id), None)
    if item is None:
        item = next((entry for entry in items if str(entry.get("food_id")) == str(food_id) and str(entry.get("serving_id")) == str(serving_id)), None)
        item_id = str(item["saved_meal_item_id"]) if item and item.get("saved_meal_item_id") else item_id
    return {"success": True, "saved_meal_item_id": item_id, "item": item, "verified": item is not None}


async def edit_saved_meal_item(saved_meal_id: str, saved_meal_item_id: str, number_of_units: float) -> dict[str, Any]:
    units = _positive(number_of_units, "number_of_units")
    await asyncio.to_thread(_call, "PUT", "/saved-meals/item/v1", {"saved_meal_item_id": saved_meal_item_id, "number_of_units": units})
    items = await get_saved_meal_items(saved_meal_id)
    item = next((entry for entry in items if str(entry.get("saved_meal_item_id")) == str(saved_meal_item_id)), None)
    verified = item is not None and abs(float(item.get("number_of_units", -1)) - units) < 0.000001
    return {"success": True, "saved_meal_item_id": saved_meal_item_id, "item": item, "verified": verified}


async def delete_saved_meal_item(saved_meal_id: str, saved_meal_item_id: str) -> dict[str, Any]:
    await asyncio.to_thread(_call, "DELETE", "/saved-meals/item/v1", {"saved_meal_item_id": saved_meal_item_id})
    items = await get_saved_meal_items(saved_meal_id)
    present = any(str(entry.get("saved_meal_item_id")) == str(saved_meal_item_id) for entry in items)
    return {"success": True, "saved_meal_item_id": saved_meal_item_id, "verified": not present}


async def add_saved_meal_to_diary_manual(saved_meal_id: str, meal: str, entry_date: str) -> dict[str, Any]:
    normalized = _meal(meal)
    _parse_date(entry_date)
    items = await get_saved_meal_items(saved_meal_id)
    if not items:
        raise ValueError("saved meal has no items")
    validated = []
    for item in items:
        serving = await validate_food_serving(str(item["food_id"]), str(item["serving_id"]))
        validated.append((item, serving["food"].get("food_name") or item.get("saved_meal_item_name", "Saved meal item")))
    created = []
    try:
        for item, name in validated:
            created.append(await create_diary_entry(str(item["food_id"]), name, str(item["serving_id"]), float(item["number_of_units"]), normalized, entry_date))
    except Exception:
        for entry in reversed(created):
            await delete_diary_entry(str(entry["food_entry_id"]))
        raise
    return {"success": True, "saved_meal_id": saved_meal_id, "entries_created": len(created), "entries": created, "verified": True}


async def get_daily_food_entries(entry_date: str) -> list[dict[str, Any]]:
    value = _parse_date(entry_date)
    payload = await asyncio.to_thread(_call, "GET", "/food-entries/v2", {"date": _date_int(value)})
    entries = _as_list((payload.get("food_entries") or {}).get("food_entry"))
    for entry in entries:
        entry["date"] = _iso_date(entry.get("date_int"))
    return entries


async def copy_saved_meal_to_diary(saved_meal_id: str, meal: str, entry_date: str) -> dict[str, Any]:
    normalized = _meal(meal)
    value = _parse_date(entry_date)
    items = await get_saved_meal_items(saved_meal_id)
    before = await get_daily_food_entries(entry_date)
    payload = await asyncio.to_thread(_call, "POST", "/food-entries/copy/saved-meal/v1", {"saved_meal_id": saved_meal_id, "meal": normalized, "date": _date_int(value)})
    after = await get_daily_food_entries(entry_date)
    before_ids = {str(item.get("food_entry_id")) for item in before}
    added = [item for item in after if str(item.get("food_entry_id")) not in before_ids]
    expected_foods = {str(item.get("food_id")) for item in items}
    added_foods = {str(item.get("food_id")) for item in added if str(item.get("meal", "")).lower() == normalized}
    verified = bool(items) and expected_foods.issubset(added_foods)
    return {"success": True, "saved_meal_id": saved_meal_id, "date": entry_date, "meal": normalized, "entries_added": added, "response": payload, "verified": verified}


add_saved_meal_to_diary = add_saved_meal_to_diary_manual


async def copy_diary_entries(from_date: str, to_date: str, meal: str | None = None) -> dict[str, Any]:
    source = _parse_date(from_date)
    target = _parse_date(to_date)
    normalized = _meal(meal)
    before = await get_daily_food_entries(to_date)
    params: dict[str, Any] = {"from_date": _date_int(source), "to_date": _date_int(target)}
    if normalized:
        params["meal"] = normalized
    payload = await asyncio.to_thread(_call, "POST", "/food-entries/copy/v1", params)
    after = await get_daily_food_entries(to_date)
    source_entries = await get_daily_food_entries(from_date)
    if normalized:
        source_entries = [item for item in source_entries if str(item.get("meal", "")).lower() == normalized]
    before_ids = {str(item.get("food_entry_id")) for item in before}
    added = [item for item in after if str(item.get("food_entry_id")) not in before_ids]
    verified = bool(source_entries) and len(added) >= len(source_entries)
    return {"success": True, "from_date": from_date, "to_date": to_date, "meal": normalized, "entries_added": added, "response": payload, "verified": verified}


async def get_most_eaten_foods(meal: str | None = None) -> list[dict[str, Any]]:
    normalized = _meal(meal)
    payload = await asyncio.to_thread(_call, "GET", "/food/most-eaten/v2", {"meal": normalized} if normalized else {})
    return _as_list((payload.get("foods") or {}).get("food"))


async def get_recently_eaten_foods(meal: str | None = None) -> list[dict[str, Any]]:
    normalized = _meal(meal)
    payload = await asyncio.to_thread(_call, "GET", "/food/recently-eaten/v2", {"meal": normalized} if normalized else {})
    return _as_list((payload.get("foods") or {}).get("food"))


async def get_favorite_foods() -> list[dict[str, Any]]:
    payload = await asyncio.to_thread(_call, "GET", "/food/favorites/v2")
    return _as_list((payload.get("foods") or {}).get("food"))


async def get_favorite_recipes() -> list[dict[str, Any]]:
    payload = await asyncio.to_thread(_call, "GET", "/recipe/favorites/v2")
    return _as_list((payload.get("recipes") or {}).get("recipe"))


async def set_food_favorite(food_id: str, favorite: bool, serving_id: str | None = None, number_of_units: float | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"food_id": food_id}
    if serving_id is not None:
        await validate_food_serving(food_id, serving_id)
        params["serving_id"] = serving_id
    if number_of_units is not None:
        params["number_of_units"] = _positive(number_of_units, "number_of_units")
    await asyncio.to_thread(_call, "POST" if favorite else "DELETE", "/food/favorite/v1", params)
    favorites = await get_favorite_foods()
    present = any(str(item.get("food_id")) == str(food_id) for item in favorites)
    if present != favorite:
        raise ValueError("favorite change could not be verified")
    return {"success": True, "food_id": food_id, "favorite": favorite, "verified": True}


async def set_recipe_favorite(recipe_id: str, favorite: bool) -> dict[str, Any]:
    await asyncio.to_thread(_call, "POST" if favorite else "DELETE", "/recipe/favorites/v1", {"recipe_id": recipe_id})
    favorites = await get_favorite_recipes()
    present = any(str(item.get("recipe_id")) == str(recipe_id) for item in favorites)
    if present != favorite:
        raise ValueError("favorite change could not be verified")
    return {"success": True, "recipe_id": recipe_id, "favorite": favorite, "verified": True}


async def get_monthly_nutrition(month_date: str | None = None) -> dict[str, Any]:
    value = _parse_date(month_date) if month_date else date.today()
    payload = await asyncio.to_thread(_call, "GET", "/food-entries/month/v1", {"date": _date_int(value)})
    return _dated_days(payload)


async def get_exercises() -> list[dict[str, Any]]:
    payload = await asyncio.to_thread(_call, "GET", "/exercises/v2")
    return _as_list((payload.get("exercises") or {}).get("exercise"))


async def get_daily_exercise_entries(entry_date: str) -> list[dict[str, Any]]:
    value = _parse_date(entry_date)
    payload = await asyncio.to_thread(_call, "GET", "/exercise-entries/v2", {"date": _date_int(value)})
    entries = _as_list((payload.get("exercise_entries") or {}).get("exercise_entry"))
    for entry in entries:
        if entry.get("date_int") is not None:
            entry["date"] = _iso_date(entry["date_int"])
    return entries


async def edit_exercise_entries(
    entry_date: str,
    shift_from_id: str,
    shift_to_id: str,
    minutes: int,
    shift_to_name: str | None = None,
    shift_from_name: str | None = None,
    kcal: int | None = None,
) -> dict[str, Any]:
    value = _parse_date(entry_date)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 1440:
        raise ValueError("minutes must be an integer between 1 and 1440")
    if str(shift_to_id) == "0" and (not shift_to_name or kcal is None):
        raise ValueError("shift_to_name and kcal are required when shift_to_id is 0")
    if str(shift_from_id) == "0" and not shift_from_name:
        raise ValueError("shift_from_name is required when shift_from_id is 0")
    params: dict[str, Any] = {"date": _date_int(value), "shift_from_id": shift_from_id, "shift_to_id": shift_to_id, "minutes": minutes}
    if shift_to_name is not None:
        params["shift_to_name"] = shift_to_name
    if shift_from_name is not None:
        params["shift_from_name"] = shift_from_name
    if kcal is not None:
        if isinstance(kcal, bool) or not isinstance(kcal, int) or kcal <= 0:
            raise ValueError("kcal must be a positive integer")
        params["kcal"] = kcal
    await asyncio.to_thread(_call, "PUT", "/exercise-entries/template/v1", params)
    entries = await get_daily_exercise_entries(entry_date)
    return {"success": True, "date": entry_date, "entries": entries, "verified": bool(entries)}


async def commit_exercise_day(entry_date: str) -> dict[str, Any]:
    value = _parse_date(entry_date)
    payload = await asyncio.to_thread(_call, "POST", "/exercise-entries/day/v1", {"date": _date_int(value)})
    entries = await get_daily_exercise_entries(entry_date)
    return {"success": True, "date": entry_date, "entries": entries, "response": payload, "verified": bool(entries)}


async def save_exercise_template(entry_date: str, days: int) -> dict[str, Any]:
    value = _parse_date(entry_date)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 127:
        raise ValueError("days must be an integer bitmask between 1 and 127")
    payload = await asyncio.to_thread(_call, "POST", "/exercise-entries/template/v1", {"date": _date_int(value), "days": days})
    return {"success": True, "date": entry_date, "days": days, "response": payload, "verified": False}


async def get_monthly_exercise(month_date: str | None = None) -> dict[str, Any]:
    value = _parse_date(month_date) if month_date else date.today()
    payload = await asyncio.to_thread(_call, "GET", "/exercise-entries/month/v2", {"date": _date_int(value)})
    return _dated_days(payload)

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from .diary import get_diary_entries

NUMERIC_FIELDS = ("calories", "protein", "carbohydrate", "fat", "fiber", "sugar", "sodium")


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


async def food_history_stats(date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else datetime.now(UTC).date()
    start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else end - timedelta(days=29)
    if (end - start).days > 92:
        raise ValueError("statistics range cannot exceed 93 days")
    entries = await get_diary_entries(start.isoformat(), end.isoformat())
    totals = dict.fromkeys(NUMERIC_FIELDS, 0.0)
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "food_id": None,
        "food_name": "",
        "entries": 0,
        "dates": set(),
        "meals": defaultdict(int),
        "servings": defaultdict(int),
        "first_date": None,
        "last_date": None,
    })
    for entry in entries:
        for field in NUMERIC_FIELDS:
            totals[field] += _number(entry.get(field))
        key = str(entry.get("food_id") or entry.get("food_entry_name") or "unknown")
        item = grouped[key]
        item["food_id"] = entry.get("food_id")
        item["food_name"] = entry.get("food_entry_name", "")
        item["entries"] += 1
        entry_date = entry.get("date")
        if entry_date:
            item["dates"].add(entry_date)
            item["first_date"] = min(item["first_date"] or entry_date, entry_date)
            item["last_date"] = max(item["last_date"] or entry_date, entry_date)
        item["meals"][entry.get("meal", "Unknown")] += 1
        serving = entry.get("food_entry_description") or str(entry.get("serving_id", ""))
        item["servings"][serving] += 1
    foods = []
    for item in grouped.values():
        item["distinct_days"] = len(item.pop("dates"))
        item["meals"] = dict(item["meals"])
        item["usual_servings"] = [
            {"description": value, "count": count}
            for value, count in sorted(item.pop("servings").items(), key=lambda pair: pair[1], reverse=True)[:3]
        ]
        foods.append(item)
    foods.sort(key=lambda item: (-item["entries"], item["food_name"]))
    day_count = (end - start).days + 1
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "days": day_count,
        "entries": len(entries),
        "totals": {key: round(value, 3) for key, value in totals.items()},
        "daily_averages": {key: round(value / day_count, 3) for key, value in totals.items()},
        "most_frequent_foods": foods,
    }


async def daily_nutrition_summary(summary_date: str) -> dict[str, Any]:
    entries = await get_diary_entries(summary_date, summary_date)
    totals = {field: round(sum(_number(entry.get(field)) for entry in entries), 3) for field in NUMERIC_FIELDS}
    meals: dict[str, dict[str, float]] = defaultdict(lambda: dict.fromkeys(NUMERIC_FIELDS, 0.0))
    for entry in entries:
        for field in NUMERIC_FIELDS:
            meals[entry.get("meal", "Unknown")][field] += _number(entry.get(field))
    return {
        "date": summary_date,
        "entries": len(entries),
        "totals": totals,
        "meals": {meal: {key: round(value, 3) for key, value in values.items()} for meal, values in meals.items()},
    }

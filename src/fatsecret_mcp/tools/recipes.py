import asyncio
from typing import Any

from .food import _as_list, _request


async def search_recipes(
    query: str = "",
    max_results: int = 10,
    page_number: int = 0,
    recipe_types: str | None = None,
    must_have_images: bool | None = None,
) -> dict[str, Any]:
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50")
    params: dict[str, Any] = {
        "search_expression": query,
        "max_results": max_results,
        "page_number": page_number,
        "format": "json",
    }
    if recipe_types:
        params["recipe_types"] = recipe_types
    if must_have_images is not None:
        params["must_have_images"] = str(must_have_images).lower()
    payload = await asyncio.to_thread(_request, "GET", "/recipes/search/v3", params)
    recipes = payload.get("recipes") or {}
    recipes["recipe"] = _as_list(recipes.get("recipe"))
    return recipes


async def get_recipe(recipe_id: str) -> dict[str, Any]:
    payload = await asyncio.to_thread(
        _request,
        "GET",
        "/recipe/v2",
        {"recipe_id": recipe_id, "format": "json"},
    )
    return payload.get("recipe") or {}

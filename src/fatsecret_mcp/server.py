#!/usr/bin/env python3
import os
from datetime import datetime, timedelta

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from .auth.oauth1 import get_authenticator
from .auth.oauth2 import SingleUserOAuthProvider
from .tools.account import (
    add_saved_meal_item,
    add_saved_meal_to_diary_manual,
    commit_exercise_day,
    copy_diary_entries,
    copy_saved_meal_to_diary,
    create_saved_meal,
    delete_saved_meal,
    delete_saved_meal_item,
    edit_exercise_entries,
    edit_saved_meal,
    edit_saved_meal_item,
    get_daily_exercise_entries,
    get_exercises,
    get_favorite_foods,
    get_favorite_recipes,
    get_monthly_exercise,
    get_monthly_nutrition,
    get_most_eaten_foods,
    get_profile,
    get_recently_eaten_foods,
    get_saved_meal_items,
    get_saved_meals,
    get_weight_month,
    save_exercise_template,
    set_food_favorite,
    set_recipe_favorite,
    update_weight,
)
from .tools.diary import create_diary_entry, delete_diary_entry, edit_diary_entry, get_diary_entries
from .tools.food import food_search_tool, food_servings_tool
from .tools.recipes import get_recipe, search_recipes
from .tools.stats import daily_nutrition_summary, food_history_stats

PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "https://fatsecret.mcp.development.antonberzins.com")
MCP_RESOURCE = f"{PUBLIC_URL}/mcp"
MCP_PASSWORD = os.environ["MCP_AUTH_PASSWORD"]

authenticator = get_authenticator()
provider = SingleUserOAuthProvider(PUBLIC_URL, MCP_PASSWORD)
server = FastMCP(
    "FatSecret",
    instructions="Search foods and read or manage the owner's existing FatSecret nutrition diary. Before creating, editing, or deleting an entry, clearly confirm the exact food, serving, quantity, meal, and date with the user. API-created entries are verified only in FatSecret Platform API; never claim they are visible in the consumer FatSecret web/mobile app unless the user confirms it, because that interface may not synchronize API writes.",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    auth_server_provider=provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(PUBLIC_URL),
        resource_server_url=AnyHttpUrl(MCP_RESOURCE),
        required_scopes=["fatsecret:read", "fatsecret:write"],
        validate_token_resource=True,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["fatsecret:read", "fatsecret:write"],
            default_scopes=["fatsecret:read", "fatsecret:write"],
        ),
    ),
)


def default_range():
    today = datetime.now().date()
    return (today - timedelta(days=92)).isoformat(), today.isoformat()


@server.tool()
async def diary_entries_list(date_from: str | None = None, date_to: str | None = None):
    """List individual FatSecret diary entries. Defaults to the last three months. Dates use YYYY-MM-DD."""
    if not authenticator.is_authorized():
        raise RuntimeError("FatSecret account is not authorized")
    if not date_from or not date_to:
        date_from, date_to = default_range()
    return await get_diary_entries(date_from, date_to)


@server.tool()
async def search_foods(query: str, max_results: int = 10, page_number: int = 0, region: str = "ES", language: str = "es"):
    """Search foods in the ES/es catalog by default. Use returned food_id before requesting servings."""
    return await food_search_tool(query, max_results, page_number, region, language)


@server.tool()
async def get_food_servings(food_id: str, region: str = "ES", language: str = "es"):
    """Validate a food and return serving choices from the ES/es catalog by default."""
    return await food_servings_tool(food_id, region, language)


@server.tool()
async def add_food_entry(food_id: str, food_entry_name: str, serving_id: str, number_of_units: float, meal: str, entry_date: str):
    """Create a diary entry after user confirms food, serving, quantity, meal, and YYYY-MM-DD date."""
    return await create_diary_entry(food_id, food_entry_name, serving_id, number_of_units, meal, entry_date)


@server.tool()
async def update_food_entry(food_entry_id: str, food_entry_name: str | None = None, serving_id: str | None = None, number_of_units: float | None = None, meal: str | None = None):
    """Edit an existing diary entry. FatSecret cannot change its date; delete and recreate to move dates."""
    return await edit_diary_entry(food_entry_id, food_entry_name, serving_id, number_of_units, meal)


@server.tool()
async def remove_food_entry(food_entry_id: str):
    """Permanently delete a diary entry only after explicit user confirmation."""
    return await delete_diary_entry(food_entry_id)


@server.tool()
async def get_user_profile():
    """Get non-sensitive profile measurements for the linked FatSecret account."""
    return await get_profile()


@server.tool()
async def check_fatsecret_connection():
    """Verify the linked FatSecret account with a real profile API call."""
    profile = await get_profile()
    return {"connected": True, "region": "ES", "language": "es", "profile": profile}


@server.tool()
async def get_weight_history(month_date: str | None = None):
    """Get recorded weights for the month containing optional YYYY-MM-DD date."""
    return await get_weight_month(month_date)


@server.tool()
async def find_recipes(query: str = "", max_results: int = 10, page_number: int = 0, recipe_types: str | None = None, must_have_images: bool | None = None):
    """Search FatSecret recipes with pagination and optional filters."""
    return await search_recipes(query, max_results, page_number, recipe_types, must_have_images)


@server.tool()
async def get_recipe_details(recipe_id: str):
    """Get ingredients, directions, servings, timing, and nutrition for a recipe."""
    return await get_recipe(recipe_id)


@server.tool()
async def list_favorite_foods():
    """List foods saved as favorites in the linked account."""
    return await get_favorite_foods()


@server.tool()
async def change_food_favorite(food_id: str, favorite: bool, serving_id: str | None = None, number_of_units: float | None = None):
    """Add or remove a food favorite after explicit user confirmation."""
    return await set_food_favorite(food_id, favorite, serving_id, number_of_units)


@server.tool()
async def list_favorite_recipes():
    """List recipes saved as favorites in the linked account."""
    return await get_favorite_recipes()


@server.tool()
async def change_recipe_favorite(recipe_id: str, favorite: bool):
    """Add or remove a recipe favorite after explicit user confirmation."""
    return await set_recipe_favorite(recipe_id, favorite)


@server.tool()
async def list_saved_meals(meal: str | None = None):
    """List saved meals, optionally filtered by breakfast, lunch, dinner, or other."""
    return await get_saved_meals(meal)


@server.tool()
async def list_saved_meal_items(saved_meal_id: str):
    """List foods and portions contained in a saved meal."""
    return await get_saved_meal_items(saved_meal_id)


@server.tool()
async def get_most_eaten(meal: str | None = None):
    """List most-eaten foods, optionally filtered by breakfast, lunch, dinner, or other."""
    return await get_most_eaten_foods(meal)


@server.tool()
async def get_recently_eaten(meal: str | None = None):
    """List recently eaten foods, optionally filtered by breakfast, lunch, dinner, or other."""
    return await get_recently_eaten_foods(meal)


@server.tool()
async def copy_food_diary(from_date: str, to_date: str, meal: str | None = None):
    """Copy diary entries between YYYY-MM-DD dates only after explicit user confirmation."""
    return await copy_diary_entries(from_date, to_date, meal)


@server.tool()
async def create_saved_meal_tool(saved_meal_name: str, meals: str, saved_meal_description: str | None = None):
    """Create a saved meal only after explicit user confirmation. Meals is a comma-separated list."""
    return await create_saved_meal(saved_meal_name, meals, saved_meal_description)


@server.tool()
async def edit_saved_meal_tool(saved_meal_id: str, saved_meal_name: str | None = None, meals: str | None = None, saved_meal_description: str | None = None):
    """Edit a saved meal only after explicit user confirmation. Meals is a comma-separated list."""
    return await edit_saved_meal(saved_meal_id, saved_meal_name, meals, saved_meal_description)


@server.tool()
async def delete_saved_meal_tool(saved_meal_id: str):
    """Permanently delete a saved meal only after explicit user confirmation."""
    return await delete_saved_meal(saved_meal_id)


@server.tool()
async def add_saved_meal_item_tool(saved_meal_id: str, food_id: str, serving_id: str, number_of_units: float):
    """Add an item to a saved meal only after explicit user confirmation."""
    return await add_saved_meal_item(saved_meal_id, food_id, serving_id, number_of_units)


@server.tool()
async def edit_saved_meal_item_tool(saved_meal_id: str, saved_meal_item_id: str, number_of_units: float):
    """Edit a saved meal item only after explicit user confirmation."""
    return await edit_saved_meal_item(saved_meal_id, saved_meal_item_id, number_of_units)


@server.tool()
async def delete_saved_meal_item_tool(saved_meal_id: str, saved_meal_item_id: str):
    """Permanently delete a saved meal item only after explicit user confirmation."""
    return await delete_saved_meal_item(saved_meal_id, saved_meal_item_id)


@server.tool()
async def copy_saved_meal(saved_meal_id: str, meal: str, entry_date: str):
    """Copy a saved meal to a diary date through FatSecret only after explicit user confirmation."""
    return await copy_saved_meal_to_diary(saved_meal_id, meal, entry_date)


@server.tool()
async def add_saved_meal(saved_meal_id: str, meal: str, entry_date: str):
    """Add saved-meal items manually after explicit user confirmation; retained for backward compatibility."""
    return await add_saved_meal_to_diary_manual(saved_meal_id, meal, entry_date)


@server.tool()
async def list_exercises():
    """List exercises available in FatSecret's catalog."""
    return await get_exercises()


@server.tool()
async def list_daily_exercise_entries(entry_date: str):
    """List exercise entries for one YYYY-MM-DD date."""
    return await get_daily_exercise_entries(entry_date)


@server.tool()
async def edit_daily_exercise_entries(entry_date: str, shift_from_id: str, shift_to_id: str, minutes: int, shift_to_name: str | None = None, shift_from_name: str | None = None, kcal: int | None = None):
    """Shift daily exercise minutes only after explicit user confirmation."""
    return await edit_exercise_entries(entry_date, shift_from_id, shift_to_id, minutes, shift_to_name, shift_from_name, kcal)


@server.tool()
async def commit_daily_exercise(entry_date: str):
    """Commit exercise entries for one date only after explicit user confirmation."""
    return await commit_exercise_day(entry_date)


@server.tool()
async def save_daily_exercise_template(entry_date: str, days: int):
    """Save exercise entries as a weekday bitmask template only after explicit user confirmation."""
    return await save_exercise_template(entry_date, days)


@server.tool()
async def update_weight_entry(current_weight_kg: float, entry_date: str, goal_weight_kg: float | None = None, current_height_cm: float | None = None, comment: str | None = None):
    """Update weight and optional goal, first-time height, or comment only after explicit user confirmation."""
    return await update_weight(current_weight_kg, entry_date, goal_weight_kg, current_height_cm, comment)


@server.tool()
async def get_food_history_stats(date_from: str | None = None, date_to: str | None = None):
    """Calculate frequent foods, usual servings, meals, and nutrition totals for up to 93 days."""
    return await food_history_stats(date_from, date_to)


@server.tool()
async def get_daily_nutrition_summary(summary_date: str):
    """Summarize calories and nutrients by meal for one YYYY-MM-DD date."""
    return await daily_nutrition_summary(summary_date)


@server.tool()
async def get_monthly_nutrition_summary(month_date: str | None = None):
    """Get FatSecret daily calorie and macro totals for one month."""
    return await get_monthly_nutrition(month_date)


@server.tool()
async def get_monthly_exercise_summary(month_date: str | None = None):
    """Get FatSecret daily exercise calories for one month."""
    return await get_monthly_exercise(month_date)


@server.tool()
def get_last_three_months_range():
    """Return the default inclusive date range used for diary queries."""
    date_from, date_to = default_range()
    return {"date_from": date_from, "date_to": date_to}


@server.custom_route("/fatsecret/reconnect", methods=["GET", "POST"])
async def fatsecret_reconnect(request: Request):
    error = ""
    if request.method == "POST":
        form = await request.form()
        if str(form.get("password", "")) == MCP_PASSWORD:
            token, _ = authenticator.get_request_token(f"{PUBLIC_URL}/fatsecret/callback")
            return RedirectResponse(
                f"https://authentication.fatsecret.com/oauth/authorize?oauth_token={token}",
                status_code=302,
            )
        error = "Contraseña incorrecta."
    return HTMLResponse(f"""<!doctype html><html lang=es><meta name=viewport content='width=device-width'><title>Reconectar FatSecret</title>
    <style>body{{font:16px system-ui;max-width:460px;margin:12vh auto;padding:24px}}input,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:12px}}.error{{color:#b00}}</style>
    <h1>Reconectar FatSecret</h1><p>Inicia una autorización oficial OAuth 1.0 para enlazar la cuenta personal correcta.</p><p class=error>{error}</p>
    <form method=post><input type=password name=password placeholder='Contraseña de conexión' required autofocus><button>Continuar a FatSecret</button></form></html>""")


@server.custom_route("/fatsecret/callback", methods=["GET"])
async def fatsecret_callback(request: Request):
    verifier = request.query_params.get("oauth_verifier")
    token = request.query_params.get("oauth_token")
    if not verifier or not token or token != authenticator.request_token:
        return HTMLResponse("Autorización inválida o caducada.", status_code=400)
    if not authenticator.authorize_user(verifier):
        return HTMLResponse("FatSecret no devolvió un token de acceso.", status_code=400)
    return HTMLResponse("Cuenta FatSecret enlazada. Puedes cerrar esta ventana.")


@server.custom_route("/consent", methods=["GET", "POST"])
async def consent(request: Request):
    request_id = request.query_params.get("request", "")
    error = ""
    if request.method == "POST":
        form = await request.form()
        request_id = str(form.get("request", ""))
        redirect = provider.approve(request_id, str(form.get("password", "")))
        if redirect:
            return RedirectResponse(redirect, status_code=302)
        error = "Contraseña incorrecta o solicitud caducada."
    safe_request = request_id.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return HTMLResponse(f"""<!doctype html><html lang=es><meta name=viewport content='width=device-width'><title>Autorizar FatSecret</title>
    <style>body{{font:16px system-ui;max-width:460px;margin:12vh auto;padding:24px}}input,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:12px}}.error{{color:#b00}}</style>
    <h1>Autorizar FatSecret</h1><p>Permitir acceso de solo lectura al diario nutricional.</p><p class=error>{error}</p>
    <form method=post><input type=hidden name=request value="{safe_request}"><input type=password name=password placeholder='Contraseña de conexión' required autofocus><button>Autorizar</button></form></html>""")


@server.custom_route("/health", methods=["GET"])
async def health(request: Request):
    return HTMLResponse("ok")


def main():
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()

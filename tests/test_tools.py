import unittest
from unittest.mock import AsyncMock, patch

from fatsecret_mcp.tools import account
from fatsecret_mcp.tools.account import _iso_date
from fatsecret_mcp.tools.food import _as_list
from fatsecret_mcp.tools.stats import daily_nutrition_summary, food_history_stats


class NormalizationTests(unittest.TestCase):
    def test_as_list(self):
        self.assertEqual(_as_list(None), [])
        self.assertEqual(_as_list({"id": 1}), [{"id": 1}])
        self.assertEqual(_as_list([{"id": 1}]), [{"id": 1}])

    def test_date_int_conversion(self):
        self.assertEqual(_iso_date(0), "1970-01-01")
        self.assertEqual(_iso_date(20731), "2026-10-05")


class AccountValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_strict_dates_and_meals(self):
        with self.assertRaises(ValueError):
            await account.get_most_eaten_foods("snack")
        with self.assertRaises(ValueError):
            await account.copy_diary_entries("2026-2-01", "2026-02-02")

    async def test_positive_values_and_template_days(self):
        with self.assertRaises(ValueError):
            await account.add_saved_meal_item("1", "2", "3", 0)
        with self.assertRaises(ValueError):
            await account.save_exercise_template("2026-10-05", 128)
        with self.assertRaises(ValueError):
            await account.update_weight(True, "2026-10-05")

    async def test_exercise_shift_validation(self):
        with self.assertRaises(ValueError):
            await account.edit_exercise_entries("2026-10-05", "1", "2", -1)
        with self.assertRaises(ValueError):
            await account.edit_exercise_entries("2026-10-05", "1", "0", 10)
        with self.assertRaises(ValueError):
            await account.edit_exercise_entries("2026-10-05", "0", "2", 10)


class AccountRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_most_eaten_normalizes_and_sends_meal(self):
        with patch("fatsecret_mcp.tools.account._call", return_value={"foods": {"food": {"food_id": "1"}}}) as call:
            result = await account.get_most_eaten_foods("Lunch")
        self.assertEqual(result, [{"food_id": "1"}])
        call.assert_called_once_with("GET", "/food/most-eaten/v2", {"meal": "lunch"})

    async def test_monthly_nutrition_uses_raw_contract_and_normalizes_date(self):
        payload = {"month": {"day": {"date_int": "20731", "calories": "100"}}}
        with patch("fatsecret_mcp.tools.account._call", return_value=payload) as call:
            result = await account.get_monthly_nutrition("2026-10-05")
        self.assertEqual(result["day"][0]["date"], "2026-10-05")
        call.assert_called_once_with("GET", "/food-entries/month/v1", {"date": 20731})

    async def test_create_saved_meal_extracts_nested_id_and_verifies(self):
        with patch("fatsecret_mcp.tools.account._call", return_value={"saved_meal": {"saved_meal_id": 7}}) as call, patch("fatsecret_mcp.tools.account.get_saved_meals", new=AsyncMock(return_value=[{"saved_meal_id": "7", "saved_meal_name": "Lunch"}])):
            result = await account.create_saved_meal("Lunch", "lunch,dinner", "Work meals")
        self.assertTrue(result["verified"])
        self.assertEqual(result["saved_meal_id"], "7")
        call.assert_called_once_with("POST", "/saved-meals/v1", {"saved_meal_name": "Lunch", "meals": "lunch,dinner", "saved_meal_description": "Work meals"})

    async def test_edit_saved_meal_uses_meals_and_description(self):
        updated = {"saved_meal_id": "7", "meals": "breakfast,lunch", "saved_meal_description": "Daily"}
        with patch("fatsecret_mcp.tools.account._call", return_value={}) as call, patch("fatsecret_mcp.tools.account.get_saved_meals", new=AsyncMock(return_value=[updated])):
            await account.edit_saved_meal("7", meals="breakfast,lunch", saved_meal_description="Daily")
        call.assert_called_once_with("PUT", "/saved-meals/v1", {"saved_meal_id": "7", "meals": "breakfast,lunch", "saved_meal_description": "Daily"})

    async def test_add_saved_meal_item_validates_and_rereads(self):
        with patch("fatsecret_mcp.tools.account.validate_food_serving", new=AsyncMock(return_value={})), patch("fatsecret_mcp.tools.account._call", return_value={"saved_meal_item_id": "9"}) as call, patch("fatsecret_mcp.tools.account.get_saved_meal_items", new=AsyncMock(return_value=[{"saved_meal_item_id": "9"}])):
            result = await account.add_saved_meal_item("1", "2", "3", 1.5)
        self.assertTrue(result["verified"])
        call.assert_called_once_with("POST", "/saved-meals/item/v1", {"saved_meal_id": "1", "food_id": "2", "serving_id": "3", "number_of_units": 1.5})

    async def test_copy_saved_meal_uses_official_endpoint(self):
        item = {"food_id": "2"}
        before = [{"food_entry_id": "old"}]
        after = before + [{"food_entry_id": "new", "food_id": "2", "meal": "Lunch"}]
        with patch("fatsecret_mcp.tools.account.get_saved_meal_items", new=AsyncMock(return_value=[item])), patch("fatsecret_mcp.tools.account.get_daily_food_entries", new=AsyncMock(side_effect=[before, after])), patch("fatsecret_mcp.tools.account._call", return_value={"ok": True}) as call:
            result = await account.copy_saved_meal_to_diary("8", "lunch", "2026-10-05")
        self.assertTrue(result["verified"])
        call.assert_called_once_with("POST", "/food-entries/copy/saved-meal/v1", {"saved_meal_id": "8", "meal": "lunch", "date": 20731})

    async def test_copy_diary_uses_date_ints_and_does_not_overclaim(self):
        reads = [[], [], []]
        with patch("fatsecret_mcp.tools.account.get_daily_food_entries", new=AsyncMock(side_effect=reads)), patch("fatsecret_mcp.tools.account._call", return_value={}) as call:
            result = await account.copy_diary_entries("2026-10-04", "2026-10-05", "dinner")
        self.assertFalse(result["verified"])
        call.assert_called_once_with("POST", "/food-entries/copy/v1", {"from_date": 20730, "to_date": 20731, "meal": "dinner"})

    async def test_exercise_edit_exact_endpoint_and_params(self):
        with patch("fatsecret_mcp.tools.account._call", return_value={}) as call, patch("fatsecret_mcp.tools.account.get_daily_exercise_entries", new=AsyncMock(return_value=[{"exercise_id": "0"}])):
            result = await account.edit_exercise_entries("2026-10-05", "0", "0", 45, "Run", "Old run", 300)
        self.assertTrue(result["verified"])
        call.assert_called_once_with("PUT", "/exercise-entries/template/v1", {"date": 20731, "shift_from_id": "0", "shift_to_id": "0", "minutes": 45, "shift_to_name": "Run", "shift_from_name": "Old run", "kcal": 300})

    async def test_save_exercise_template_exact_params(self):
        with patch("fatsecret_mcp.tools.account._call", return_value={}) as call:
            await account.save_exercise_template("2026-10-05", 127)
        call.assert_called_once_with("POST", "/exercise-entries/template/v1", {"date": 20731, "days": 127})

    async def test_weight_write_and_history_verification(self):
        month = {"day": [{"date": "2026-10-05", "weight_kg": "70"}]}
        with patch("fatsecret_mcp.tools.account._call", return_value={}) as call, patch("fatsecret_mcp.tools.account.get_weight_month", new=AsyncMock(return_value=month)):
            result = await account.update_weight(70, "2026-10-05", 65, 175, "Morning")
        self.assertTrue(result["verified"])
        call.assert_called_once_with("POST", "/weight/v1", {"current_weight_kg": 70.0, "date": 20731, "goal_weight_kg": 65.0, "current_height_cm": 175.0, "comment": "Morning"})


class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_groups_food_and_totals(self):
        entries = [
            {"food_id": "1", "food_entry_name": "Rice", "date": "2026-10-01", "meal": "Dinner", "calories": "100", "protein": "2"},
            {"food_id": "1", "food_entry_name": "Rice", "date": "2026-10-02", "meal": "Lunch", "calories": "120", "protein": "3"},
        ]
        with patch("fatsecret_mcp.tools.stats.get_diary_entries", new=AsyncMock(return_value=entries)):
            result = await food_history_stats("2026-10-01", "2026-10-02")
        self.assertEqual(result["entries"], 2)
        self.assertEqual(result["totals"]["calories"], 220.0)
        self.assertEqual(result["most_frequent_foods"][0]["distinct_days"], 2)

    async def test_daily_summary_handles_invalid_numbers(self):
        entries = [{"meal": "Lunch", "calories": "bad", "protein": "4.5"}]
        with patch("fatsecret_mcp.tools.stats.get_diary_entries", new=AsyncMock(return_value=entries)):
            result = await daily_nutrition_summary("2026-10-05")
        self.assertEqual(result["totals"]["calories"], 0.0)
        self.assertEqual(result["totals"]["protein"], 4.5)


if __name__ == "__main__":
    unittest.main()

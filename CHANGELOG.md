# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-10-06

### Added
- Full MCP Streamable HTTP server with OAuth 2.1 protection
- OAuth 1.0 3-legged flow to FatSecret Platform (`/fatsecret/reconnect`, `/fatsecret/callback`)
- **39 tools** across 8 categories:
  - Food search: `search_foods`, `get_food_servings`
  - Diary CRUD: `diary_entries_list`, `add_food_entry`, `update_food_entry`, `remove_food_entry`
  - Diary bulk: `copy_food_diary`, `copy_saved_meal`
  - Saved meals CRUD: `list_saved_meals`, `list_saved_meal_items`, `create_saved_meal_tool`, `edit_saved_meal_tool`, `delete_saved_meal_tool`, `add_saved_meal_item_tool`, `edit_saved_meal_item_tool`, `delete_saved_meal_item_tool`, `add_saved_meal`
  - Frequent/Recent: `get_most_eaten`, `get_recently_eaten`
  - Favorites: `list_favorite_foods`, `change_food_favorite`, `list_favorite_recipes`, `change_recipe_favorite`
  - Recipes: `find_recipes`, `get_recipe_details`
  - Exercise: `list_exercises`, `list_daily_exercise_entries`, `edit_daily_exercise_entries`, `commit_daily_exercise`, `save_daily_exercise_template`
  - Weight: `get_weight_history`, `update_weight_entry`
  - Monthly: `get_monthly_nutrition_summary`, `get_monthly_exercise_summary`
  - Account: `get_user_profile`, `check_fatsecret_connection`
  - Utility: `get_last_three_months_range`, `health`
- ES/es catalog defaults with configurable region/language
- Exponential backoff + `Retry-After` rate-limit handling
- Post-write verification with automatic rollback on inconsistency
- Docker deployment with persistent OAuth token volume
- Comprehensive test suite (17 tests, mocked)
- pyproject.toml with console entry point `fatsecret-mcp`
- MIT license

### Security
- Connection password protects OAuth reconnect endpoint
- Tokens stored in Docker volume, never in image
- No credentials in logs
- Non-root container user

### Documentation
- Accurate README with all 39 tools, ChatGPT/Claude integration guides
- CONTRIBUTING.md, CHANGELOG.md, LICENSE
- Generic docker-compose.yml (no hardcoded domains)
- GitHub Actions CI: lint, type-check, tests, Docker build, Trivy scan
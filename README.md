# FatSecret MCP Server

Model Context Protocol (MCP) server for the **FatSecret Platform API**. Search foods, read and manage your personal nutrition diary, saved meals, exercise, weight, favorites, recipes, and monthly summaries — all from any MCP-compatible client (ChatGPT Web, Claude Desktop, custom agents).

## Features

| Category | Tools |
|----------|-------|
| **Food search** | `search_foods`, `get_food_servings` |
| **Diary (read)** | `diary_entries_list`, `get_daily_nutrition_summary`, `get_food_history_stats` |
| **Diary (write)** | `add_food_entry`, `update_food_entry`, `remove_food_entry` |
| **Diary (bulk)** | `copy_food_diary`, `copy_saved_meal` |
| **Saved meals** | `list_saved_meals`, `list_saved_meal_items`, `create_saved_meal_tool`, `edit_saved_meal_tool`, `delete_saved_meal_tool`, `add_saved_meal_item_tool`, `edit_saved_meal_item_tool`, `delete_saved_meal_item_tool`, `add_saved_meal` |
| **Frequent/Recent foods** | `get_most_eaten`, `get_recently_eaten` |
| **Favorites** | `list_favorite_foods`, `change_food_favorite`, `list_favorite_recipes`, `change_recipe_favorite` |
| **Recipes** | `find_recipes`, `get_recipe_details` |
| **Exercise** | `list_exercises`, `list_daily_exercise_entries`, `edit_daily_exercise_entries`, `commit_daily_exercise`, `save_daily_exercise_template` |
| **Weight** | `get_weight_history`, `update_weight_entry` |
| **Monthly summaries** | `get_monthly_nutrition_summary`, `get_monthly_exercise_summary` |
| **Account** | `get_user_profile`, `check_fatsecret_connection` |
| **Auth/Health** | `fatsecret_reconnect` (HTTPS), `get_last_three_months_range`, `health` |

**39 tools total.** Every mutating tool requires explicit user confirmation. Read-only tools work immediately.

## Quick Start

### Prerequisites
- FatSecret Platform account with **Consumer Key** and **Consumer Secret** from [FatSecret Platform](https://platform.fatsecret.com/)
- Docker (recommended) or Python 3.11+

### 1. Configure credentials

```bash
cp .env.example .env
# Edit .env with your keys
```

Required variables:
```env
FATSECRET_CONSUMER_KEY=your_consumer_key
FATSECRET_CONSUMER_SECRET=your_consumer_secret
MCP_AUTH_PASSWORD=your_strong_connection_password  # protects OAuth reconnect endpoint
```

Optional:
```env
MCP_PUBLIC_URL=https://your-domain.com          # for OAuth callbacks
FATSECRET_REGION=ES
FATSECRET_LANGUAGE=es
```

### 2. Run with Docker (recommended)

```bash
docker compose up -d --build
```

Server listens on `http://0.0.0.0:8000` with MCP endpoint at `/mcp`.

### 3. Authorize your personal FatSecret account

Open in browser:
```
https://your-domain.com/fatsecret/reconnect
```
Enter `MCP_AUTH_PASSWORD`, click **Continue to FatSecret**, log in and click **Authorize**. Done — your personal diary is now linked.

### 4. Connect from ChatGPT Web

1. Settings → **Connectors** → **Add connector**
2. **Name**: `FatSecret`
3. **Description**: `Search foods and manage my personal FatSecret nutrition diary`
4. **Server URL**: `https://your-domain.com/mcp`
5. **Authentication**: `OAuth` → check "I understand and want to continue"
6. **Save**

When prompted for the connection password, enter your `MCP_AUTH_PASSWORD`.

### 5. Connect from Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "fatsecret": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "MCP_AUTH_PASSWORD", "ghcr.io/yourname/fatsecret-mcp:latest"],
      "env": {
        "MCP_AUTH_PASSWORD": "your_password"
      }
    }
  }
}
```
Restart Claude Desktop.

## Tool Examples

```python
# Search foods (ES/es catalog by default)
await search_foods("pollo a la plancha", max_results=5)

# Get servings for a food_id
await get_food_servings("123456")

# List last 3 months of diary entries (default range)
await diary_entries_list()

# Custom date range
await diary_entries_list("2024-07-01", "2024-09-30")

# Add entry (after user confirms food, serving, quantity, meal, date)
await add_food_entry("123456", "Pollo a la plancha", "789", 1.5, "dinner", "2024-10-05")

# Copy today's lunch to tomorrow
await copy_food_diary("2024-10-05", "2024-10-06", "lunch")

# Get most-eaten foods at breakfast
await get_most_eaten("breakfast")

# Create a saved meal
await create_saved_meal_tool("Mi desayuno habitual", "breakfast,lunch", "Tostada + café + fruta")

# Add weight entry
await update_weight_entry(72.5, "2024-10-05", goal_weight_kg=70, current_height_cm=175)

# List exercise catalog
await list_exercises()
```

## Architecture

- **Transport**: MCP Streamable HTTP (`/mcp`), stateless, JSON responses
- **Auth**: OAuth 2.1 server-side (protects MCP endpoints) + OAuth 1.0 3-legged to FatSecret Platform
- **OAuth flow**: HTTPS `/fatsecret/reconnect` → FatSecret authorization → `/fatsecret/callback` stores access token in Docker volume
- **Data**: no persistent storage except OAuth tokens; all calls hit FatSecret API live
- **Rate limits**: respects FatSecret limits with exponential backoff + `Retry-After`
- **Region/Language**: configurable via `FATSECRET_REGION`, `FATSECRET_LANGUAGE` (default ES/es)

## Deployment

### Generic Docker Compose (no hardcoded domains)

```yaml
# docker-compose.yml
services:
  fatsecret-mcp:
    build: .
    container_name: fatsecret-mcp
    restart: unless-stopped
    env_file:
      - .env
    environment:
      MCP_HOST: 0.0.0.0
      MCP_PORT: "8000"
    ports:
      - "8000:8000"
    volumes:
      - fatsecret-data:/app/data

volumes:
  fatsecret-data:
```

Put behind any reverse proxy (Traefik, Nginx, Caddy) for HTTPS. Set `MCP_PUBLIC_URL` to your public URL for OAuth callbacks.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FATSECRET_CONSUMER_KEY` | ✅ | — | FatSecret Platform consumer key |
| `FATSECRET_CONSUMER_SECRET` | ✅ | — | FatSecret Platform consumer secret |
| `MCP_AUTH_PASSWORD` | ✅ | — | Protects `/fatsecret/reconnect` endpoint |
| `MCP_PUBLIC_URL` | For OAuth | `http://localhost:8000` | Public HTTPS URL for callbacks |
| `MCP_HOST` | No | `0.0.0.0` | Bind address |
| `MCP_PORT` | No | `8000` | Port |
| `FATSECRET_REGION` | No | `ES` | Catalog region |
| `FATSECRET_LANGUAGE` | No | `es` | Catalog language |

## Development

```bash
# Install with dev dependencies
pip install -e .[dev]

# Run tests
pytest -v

# Lint
ruff check src tests

# Type check
mypy src

# Run server locally
python -m fatsecret_mcp.server
```

## Data Handling & FatSecret Terms

- **No local caching** of food/diary data beyond request lifetime
- **OAuth tokens** stored in Docker volume (`fatsecret-data`) for session persistence
- **User data** never leaves your infrastructure except to FatSecret API
- **Respects** FatSecret Platform Terms: no bulk export, no redistribution, no medical advice
- **Delete tokens**: `docker volume rm fatsecret-data` or use `/fatsecret/reconnect` to refresh

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This is an independent integration. Not affiliated with FatSecret. API-created entries are verified only in FatSecret Platform API; consumer web/mobile app visibility depends on FatSecret's synchronization (not guaranteed).
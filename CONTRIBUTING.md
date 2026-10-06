# Contributing

Thanks for helping improve FatSecret MCP!

## Quick checklist

- [ ] Tests pass: `pytest -v`
- [ ] Lint clean: `ruff check src tests`
- [ ] Types pass: `mypy src`
- [ ] Commit message follows [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- [ ] New tools follow existing patterns:
  - `async def` in `tools/<domain>.py`
  - Validation helpers (`_parse_date`, `_meal`, `_positive`, `_extract_id`)
  - `_require_success` for API error checking
  - `@server.tool()` with docstring requiring explicit confirmation for mutations
  - Returns structured dict with `verified` boolean only when actually verified
- [ ] New tools have unit tests using `AsyncMock`/`patch` (no real API calls)

## Adding a new tool

1. Implement in `src/fatsecret_mcp/tools/<domain>.py`
2. Import and register in `src/fatsecret_mcp/server.py`
3. Add unit test in `tests/test_tools.py`
4. Run full suite: `pytest -v && ruff check src tests && mypy src`

## Reporting issues

- Use GitHub Issues with template
- Include: Python version, Docker version, steps to reproduce, expected vs actual
- For OAuth issues: include sanitized logs (no tokens/secrets)

## Security

- Never commit `.env`, tokens, or secrets
- Rotate `MCP_AUTH_PASSWORD` and FatSecret credentials if exposed
- Report vulnerabilities privately via GitHub Security Advisories
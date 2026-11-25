"""Source-tree bootstrap for registry launchers that bypass the uv virtualenv.

Glama currently runs `uv sync` and then starts `/usr/local/bin/python -m
fatsecret_mcp.server`, rather than the Python interpreter inside `.venv`.
When running directly from a repository checkout, make that launcher see both
our src-layout package and the dependencies installed by uv.

This shim is not included in the built distribution: setuptools packages are
still discovered only under `src/`.
"""

from __future__ import annotations

import site
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_PACKAGE = _REPO_ROOT / "src" / "fatsecret_mcp"

# uv sync installs dependencies into .venv.  Registry launchers may invoke the
# system interpreter afterwards, so expose that environment to this process.
for _site_packages in sorted((_REPO_ROOT / ".venv" / "lib").glob("python*/site-packages")):
    site.addsitedir(str(_site_packages))

# Resolve submodules (e.g. fatsecret_mcp.server) from the actual src package.
if _REAL_PACKAGE.is_dir():
    __path__.append(str(_REAL_PACKAGE))

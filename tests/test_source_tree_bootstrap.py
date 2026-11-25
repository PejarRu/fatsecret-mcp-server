import os
import subprocess
import sys
from pathlib import Path


def test_source_tree_bootstrap_exposes_src_package():
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import fatsecret_mcp.server as s; "
                "print(s.__file__); "
                "assert '/src/fatsecret_mcp/server.py' in s.__file__"
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

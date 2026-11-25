import os
import subprocess
import sys
from pathlib import Path


def test_server_imports_without_runtime_secrets():
    env = os.environ.copy()
    for key in (
        "MCP_AUTH_PASSWORD",
        "MCP_TRANSPORT",
        "FATSECRET_CONSUMER_KEY",
        "FATSECRET_CONSUMER_SECRET",
    ):
        env.pop(key, None)

    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from fatsecret_mcp.server import MCP_TRANSPORT; "
                "assert MCP_TRANSPORT == 'stdio'; print(MCP_TRANSPORT)"
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "stdio"


def test_server_stays_stdio_when_dummy_password_is_present():
    env = os.environ.copy()
    env.pop("MCP_TRANSPORT", None)
    env["MCP_AUTH_PASSWORD"] = "dummy-auth-password-0001"

    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from fatsecret_mcp.server import MCP_TRANSPORT; "
                "assert MCP_TRANSPORT == 'stdio'; print(MCP_TRANSPORT)"
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "stdio"

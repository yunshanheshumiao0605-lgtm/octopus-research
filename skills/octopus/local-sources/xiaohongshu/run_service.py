#!/usr/bin/env python3
"""Run a user-installed Xiaohongshu service with its private local credentials."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    os.umask(0o077)
    settings = json.loads((ROOT / "runtime/service.json").read_text())
    binary = Path(settings.get("binary_path", "bin/xiaohongshu-mcp")).expanduser()
    if not binary.is_absolute():
        binary = ROOT / binary
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit("Install the Xiaohongshu binary as described in references/local-sources.md.")
    env = os.environ.copy()
    env["AUTH_TOKEN"] = settings["token"]
    env["COOKIES_PATH"] = str(ROOT / "runtime/cookies.json")
    env.pop("XHS_PROXY", None)
    os.chdir(ROOT / "runtime")
    headless = "true" if settings.get("headless", False) else "false"
    os.execve(binary, [str(binary), "-port", "127.0.0.1:18060", "-headless=" + headless], env)


if __name__ == "__main__":
    main()

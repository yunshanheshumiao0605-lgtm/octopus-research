#!/usr/bin/env python3
"""Launch a user-installed RSSHub build on loopback with private settings."""
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "services/rsshub"


def main():
    os.umask(0o077)
    settings = json.loads((ROOT / "runtime/settings.json").read_text())
    node = os.environ.get("NODE_BIN") or shutil.which("node")
    entry = SOURCE / "dist/index.mjs"
    if not node or not Path(node).is_file() or not entry.is_file():
        raise SystemExit("Install Node.js and build RSSHub as described in references/local-sources.md.")
    env = {
        "HOME": str(Path.home()),
        "PATH": str(Path(node).parent) + os.pathsep + os.environ.get("PATH", ""),
        "NODE_ENV": "production",
        "NODE_OPTIONS": "--max-http-header-size=32768",
        "PORT": str(settings["rsshub"]["port"]),
        "LISTEN_INADDR_ANY": "false",
        "CACHE_TYPE": "memory", "CACHE_EXPIRE": "1800",
        "ACCESS_KEY": settings["rsshub"]["access_key"],
        "USER_ROUTES_PATH": str(ROOT / "routes"),
    }
    if os.environ.get("CHROME_BIN"):
        env["CHROMIUM_EXECUTABLE_PATH"] = os.environ["CHROME_BIN"]
    for key in ("WEIBO_COOKIES", "ZHIHU_COOKIES"):
        if settings["rsshub"].get(key):
            env[key] = settings["rsshub"][key]
    os.chdir(SOURCE)
    os.execve(node, [node, str(entry)], env)


if __name__ == "__main__":
    main()

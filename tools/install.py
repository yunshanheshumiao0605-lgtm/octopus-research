#!/usr/bin/env python3
"""Install both skills into a selected directory without overwriting an installation."""
import argparse
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def install(destination):
    names = ("octopus", "octopus-query-alias")
    for name in names:
        target = destination / name
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"{target} already exists; no files were changed.")
    destination.mkdir(parents=True, exist_ok=True)
    completed = []
    try:
        for name in names:
            target = destination / name
            target.mkdir()
            completed.append(target)
            shutil.copytree(
                ROOT / "skills" / name, target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".DS_Store", "runtime", "services",
                    "bin", "node_modules", ".venv", ".env", "preferences.local.md",
                    "sources.json", "settings.json", "service.json",
                ),
            )
    except Exception:
        for target in completed:
            if target.is_dir():
                shutil.rmtree(target)
        raise
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills")
    args = parser.parse_args()
    try:
        for path in install(args.destination.expanduser().resolve()):
            print(f"Installed: {path}")
    except (FileExistsError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

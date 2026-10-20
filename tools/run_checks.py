#!/usr/bin/env python3
"""Run offline checks in separate interpreters; no real services or credentials."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    "skills/octopus/tests/test_personal_workflow.py",
    "skills/octopus/local-sources/domestic/test_collect.py",
    "skills/octopus/local-sources/xiaohongshu/test_adapter_auth.py",
    "tests/test_packaging.py",
]


def main():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["FROM_BROWSER"] = "off"
    env["BROWSER_CONSENT"] = "false"
    for relative in CHECKS:
        print(f"Checking {relative}", flush=True)
        subprocess.run([sys.executable, "-B", str(ROOT / relative)],
                       cwd=ROOT, env=env, check=True)
    print("All offline checks passed.")


if __name__ == "__main__":
    main()

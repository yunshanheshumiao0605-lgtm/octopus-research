#!/usr/bin/env python3
"""Launch user-installed WeRSS, avoiding its upstream main.py environment dump."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "services/werss"


def main():
    os.umask(0o077)
    settings = json.loads((ROOT / "runtime/settings.json").read_text())["werss"]
    if not (SOURCE / "web.py").is_file():
        raise SystemExit("Install WeRSS as described in references/local-sources.md.")
    os.environ["USERNAME"] = settings["username"]
    os.environ["PASSWORD"] = settings["password"]
    os.environ["HEADLESS"] = "true"
    if os.environ.get("CHROME_BIN"):
        os.environ["CHROME_EXECUTABLE_PATH"] = os.environ["CHROME_BIN"]
    os.chdir(SOURCE)
    (SOURCE / "data").mkdir(exist_ok=True)
    sys.path.insert(0, str(SOURCE))
    sys.argv = [sys.argv[0], "-config", str(ROOT / "runtime/werss.yaml")]
    import init_sys
    init_sys.init()
    import uvicorn
    from web import app
    uvicorn.run(app, host="127.0.0.1", port=settings["port"], access_log=False)


if __name__ == "__main__":
    main()

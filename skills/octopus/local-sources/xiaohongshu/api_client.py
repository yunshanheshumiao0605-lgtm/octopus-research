#!/usr/bin/env python3
"""Local API checks without printing authentication or session values."""
import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:18060"


def request(path, payload=None, authenticated=True):
    settings = json.loads((ROOT / "runtime" / "service.json").read_text())
    headers = {}
    if authenticated:
        headers["Authorization"] = "Bearer " + settings["token"]
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=headers,
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=75) as response:
        return json.load(response)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["health", "status", "login", "search", "auth-check"])
    parser.add_argument("--keyword", default="AI 工具")
    parser.add_argument("--wait-login", action="store_true")
    args = parser.parse_args()
    if args.action == "health":
        result = request("/health", authenticated=False)
        print(json.dumps({"healthy": result.get("success")}, ensure_ascii=False))
    elif args.action == "auth-check":
        try:
            request("/api/v1/login/status", authenticated=False)
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise
            print('{"unauthenticated_request_rejected": true}')
        else:
            raise SystemExit("ERROR: protected endpoint accepted an unauthenticated request")
    elif args.action == "status":
        result = request("/api/v1/login/status")
        print(json.dumps({"success": result.get("success"), "logged_in": result.get("data", {}).get("is_logged_in")}))
    elif args.action == "login":
        result = request("/api/v1/login/qrcode")
        data = result.get("data", {})
        if data.get("is_logged_in"):
            print('{"logged_in": true}')
            return
        src = data.get("img", "")
        if not src.startswith("data:image/") or ";base64," not in src:
            raise SystemExit("QR image was not returned as inline image data")
        mime = src.split(";", 1)[0]
        suffix = ".jpg" if mime == "data:image/jpeg" else ".png"
        target = ROOT / "runtime" / ("login-qr-" + datetime.now().strftime("%Y%m%d-%H%M%S") + suffix)
        target.write_bytes(base64.b64decode(src.split(",", 1)[1], validate=True))
        print(json.dumps({"qr_path": str(target), "expires_in": data.get("timeout")}, ensure_ascii=False), flush=True)
        if args.wait_login:
            cookie_file = ROOT / "runtime" / "cookies.json"
            stamp = cookie_file.stat().st_mtime_ns if cookie_file.exists() else 0
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                current = cookie_file.stat().st_mtime_ns if cookie_file.exists() else 0
                if current != stamp:
                    state = request("/api/v1/login/status")
                    if state.get("data", {}).get("is_logged_in"):
                        print('{"logged_in": true}', flush=True)
                        return
                    stamp = current
                time.sleep(3)
            raise SystemExit("QR login timed out; request a fresh code when ready.")
    else:
        result = request("/api/v1/feeds/search", {
            "keyword": args.keyword,
            "filters": {"sort_by": "最新", "note_type": "不限", "publish_time": "一周内", "search_scope": "不限", "location": "不限"},
        })
        (ROOT / "runtime" / "search-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        items = result.get("data", {}).get("feeds", [])
        titles = [(item.get("noteCard") or {}).get("displayTitle", "") for item in items[:3]]
        print(json.dumps({"success": result.get("success"), "result_count": len(items), "sample_titles": titles}, ensure_ascii=False))


if __name__ == "__main__":
    main()

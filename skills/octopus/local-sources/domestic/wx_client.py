#!/usr/bin/env python3
"""Local WeRSS client. Never prints authentication responses or cookies."""
import argparse
import datetime
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Client:
    def __init__(self):
        self.settings = json.loads((ROOT / "runtime" / "settings.json").read_text())["werss"]
        self.base = f"http://127.0.0.1:{self.settings['port']}/api/v1/wx"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        form = urllib.parse.urlencode({
            "username": self.settings["username"],
            "password": self.settings["password"],
        }).encode()
        response = self.request("/auth/login", form, "application/x-www-form-urlencoded")
        self.token = response["data"]["access_token"]

    def request(self, path, data=None, content_type="application/json", timeout=60):
        headers = {"Content-Type": content_type}
        if hasattr(self, "token"):
            headers["Authorization"] = "Bearer " + self.token
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        with self.opener.open(request, timeout=timeout) as response:
            return json.load(response)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "qr", "mp-test"])
    parser.add_argument("--mp-id", default="")
    parser.add_argument("--wait-login", action="store_true")
    args = parser.parse_args()
    client = Client()
    if args.action == "status":
        response = client.request("/weread")["data"]
        qr = client.request("/weread/qr/status")["data"]
        result = {"configured": response["configured"], "account_count": response["account_count"],
                  "qr_session_login_status": qr["login_status"], "qr_session_message": qr["msg"]}
    elif args.action == "qr":
        response = client.request("/weread/qr/code")
        if response.get("code") not in (0, 200):
            raise RuntimeError(response.get("message", "QR generation failed"))
        target = ROOT / "runtime" / ("wechat-login-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".png")
        shutil.copyfile(ROOT / "services" / "werss" / "static" / "weread_qrcode.png", target)
        target.chmod(0o600)
        result = {"qr_image": str(target), "message": "请用微信扫码并确认登录微信读书"}
    else:
        result = client.request("/weread/mp/test", {"mp_id": args.mp_id})
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if args.action == "qr" and args.wait_login:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            state = client.request("/weread/qr/status")["data"]
            if state.get("login_status"):
                print('{"logged_in": true}', flush=True)
                return
            time.sleep(3)
        raise SystemExit("QR login timed out; request a fresh code when ready.")


if __name__ == "__main__":
    main()

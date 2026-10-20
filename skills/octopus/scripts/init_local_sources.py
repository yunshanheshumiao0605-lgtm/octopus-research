#!/usr/bin/env python3
"""Create private local-source configuration. No downloads, login, or service start."""
import argparse
import json
import os
from pathlib import Path
import secrets

SKILL = Path(__file__).resolve().parents[1]


def create_private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return True


def initialize(skill, selected):
    created = []

    def save(path, data):
        if create_private_json(path, data):
            created.append(path.relative_to(skill).as_posix())

    if "domestic" in selected:
        runtime = skill / "local-sources/domestic/runtime"
        save(runtime / "settings.json", {
            "rsshub": {"port": 18200, "access_key": secrets.token_urlsafe(32)},
            "werss": {"port": 18001, "username": "octopus",
                      "password": secrets.token_urlsafe(32)},
        })
        save(runtime / "sources.json", {
            "topics": [],
            "wechat_accounts": [],
            "rsshub": [
                {"id": "weibo", "name": "微博公开热搜", "path": "/local-weibo/hot",
                 "date_semantics": "hotlist_observation"},
                {"id": "zhihu", "name": "知乎热榜", "path": "/zhihu/hot",
                 "date_semantics": "question_created"},
                {"id": "bilibili", "name": "B站科技区排行榜",
                 "path": "/bilibili/ranking/tech", "date_semantics": "video_published"},
            ],
        })
        # JSON is valid YAML; no extra package is needed to initialize settings.
        save(runtime / "werss.yaml", {
            "app_name": "octopus-werss",
            "server": {"enable_job": False, "auto_reload": False,
                       "send_code": False, "auth_web": False,
                       "article_stats_refresh_enabled": False},
            "db": "sqlite:///./data/db.db",
            "secret": secrets.token_urlsafe(48),
            "port": 18001, "debug": False, "max_page": 1, "interval": 10,
            "redis": {"url": "", "server": {"enabled": False}},
            "cascade": {"enabled": False},
            "notice": {"dingding": "", "wechat": "", "feishu": "", "custom": ""},
            "gather": {"model": "weread_mp", "content": True,
                       "content_auto_check": False, "content_mode": "web",
                       "browser_type": "chromium", "content_fetch_timeout": 60},
            "weread": {"cookie": "", "ticket": "", "vid": "",
                       "mp_max_pages": 1, "auto_add_to_shelf": False,
                       "page_interval": 1, "content_interval": 2},
            "rss": {"local": False, "full_context": True, "page_size": 30},
            "cache": {"enabled": False, "views": {"enabled": False}},
            "log": {"level": "WARNING", "file": ""},
            "export": {"pdf": {"enable": False}, "markdown": {"enable": False}},
        })
    if "xiaohongshu" in selected:
        runtime = skill / "local-sources/xiaohongshu/runtime"
        save(runtime / "service.json", {
            "token": secrets.token_urlsafe(32), "headless": False,
            "binary_path": "bin/xiaohongshu-mcp",
        })
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--services", required=True,
                        help="domestic,xiaohongshu or either one")
    args = parser.parse_args()
    selected = set(args.services.split(","))
    if not selected or not selected <= {"domestic", "xiaohongshu"}:
        parser.error("Choose domestic, xiaohongshu, or both.")
    for relative in initialize(SKILL, selected):
        print(f"Created private configuration: {relative}")
    print("Existing files preserved. Install optional services and log in separately.")


if __name__ == "__main__":
    main()

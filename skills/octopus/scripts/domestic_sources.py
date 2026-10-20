#!/usr/bin/env python3
"""Collect selected domestic sources, starting and stopping only required services."""
import argparse
from pathlib import Path
import sys

from source_session import run_with_services

ROOT = Path(__file__).resolve().parents[1] / "local-sources" / "domestic"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True, help="Choose wechat,weibo,zhihu,bilibili, separated by commas")
    parser.add_argument("--sync-wechat", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/latest.json")
    args = parser.parse_args()
    chosen = set(args.sources.split(","))
    if not chosen or not chosen <= {"wechat", "weibo", "zhihu", "bilibili"}:
        parser.error("Unknown source; choose wechat,weibo,zhihu,bilibili.")
    services = []
    if "wechat" in chosen:
        services.append("werss")
    if chosen & {"weibo", "zhihu", "bilibili"}:
        services.append("rsshub")
    command = [sys.executable, str(ROOT / "collect.py"), "--sources", args.sources,
               "--output", str(args.output.resolve())]
    if args.sync_wechat:
        command.append("--sync-wechat")
    return run_with_services(services, command)


if __name__ == "__main__":
    raise SystemExit(main())

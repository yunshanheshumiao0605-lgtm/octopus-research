#!/usr/bin/env python3
"""Fetch local platform feeds into reviewable candidates, without inventing news dates."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignored:
            self.ignored -= 1
        if tag in ("p", "div", "li", "br"):
            self.parts.append(" ")

    def handle_data(self, value):
        if not self.ignored:
            self.parts.append(value)


def plain(value):
    parser = TextOnly()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", html.unescape("".join(parser.parts))).strip()


def parse_date(value):
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    # A naive timestamp cannot establish a precise daily window.
    return parsed.isoformat() if parsed.tzinfo else None


def parse_feed(data, source, observed_at, topics):
    tree = ET.fromstring(data)
    records = []
    seen = set()
    for item in tree.findall("./channel/item"):
        url = (item.findtext("link") or "").strip()
        title = plain(item.findtext("title"))
        if not title or not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        description = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or item.findtext("description") or ""
        description = plain(description)[:12000]
        supplied_date = parse_date(item.findtext("pubDate"))
        semantics = source["date_semantics"]
        # RSS generators sometimes supply today's time for otherwise undated hot topics.
        published_at = supplied_date if semantics in ("video_published", "article_published") else None
        combined = (title + " " + description).casefold()
        matches = [word for word in topics if word.casefold() in combined]
        records.append({
            "source": source["id"], "source_name": source["name"], "title": title,
            "url": url, "summary": description,
            "author": item.findtext("{http://purl.org/dc/elements/1.1/}creator") or item.findtext("author") or None,
            "published_at": published_at, "observed_at": observed_at,
            "question_created_at": supplied_date if semantics == "question_created" else None,
            "unverified_feed_date": supplied_date if semantics == "article_date_unverified" else None,
            "date_semantics": semantics, "topic_matches": matches,
            "needs_fact_check": True,
        })
    return records


def fetch_source(source, settings, observed_at, topics, timeout=90):
    if source["id"] == "wechat":
        url = f"http://127.0.0.1:{settings['werss']['port']}/feed/all.rss?limit=100"
    else:
        path = source["path"]
        code = hashlib.md5((path + settings["rsshub"]["access_key"]).encode()).hexdigest()
        url = f"http://127.0.0.1:{settings['rsshub']['port']}{path}?code={code}&limit=100"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as response:
            data = response.read(10_000_000)
        records = parse_feed(data, source, observed_at, topics)
        status = "ok" if records else "empty"
        return {"source": source["id"], "status": status, "count": len(records), "required": False}, records
    except urllib.error.HTTPError as exc:
        # Do not print the protected URL or HTML error page.
        return {"source": source["id"], "status": "unavailable", "error": f"HTTP {exc.code}", "required": False}, []
    except Exception as exc:
        return {"source": source["id"], "status": "unavailable", "error": type(exc).__name__, "required": False}, []


def collect(sync_wechat=False, selected=None):
    os.umask(0o077)
    config = json.loads((ROOT / "runtime" / "sources.json").read_text())
    settings = json.loads((ROOT / "runtime" / "settings.json").read_text())
    observed_at = dt.datetime.now(dt.timezone.utc).isoformat()
    coverage, candidates = [], []
    selected = set(selected or ("wechat", "weibo", "zhihu", "bilibili"))
    if "wechat" in selected and config["wechat_accounts"]:
        sync_errors = []
        if sync_wechat:
            from wx_client import Client
            try:
                client = Client()
                for account in config["wechat_accounts"]:
                    result = client.request("/weread/collect", {
                        "mp_id": account["id"], "faker_id": account["id"],
                        "mp_name": account["name"], "max_page": 1, "gather_content": True,
                    }, timeout=180)
                    if result.get("code") != 0:
                        sync_errors.append(account["id"])
            except Exception as exc:
                sync_errors.append(type(exc).__name__)
        status, records = fetch_source(
            # WeRSS's cover fallback writes collection time into publication time.
            # Verify dates on original WeChat articles before promoting candidates.
            {"id": "wechat", "name": "微信公众号订阅", "date_semantics": "article_date_unverified"},
            settings, observed_at, config["topics"])
        status["sync_requested"] = sync_wechat
        if sync_errors:
            status.update(status="partial", sync_errors=sync_errors)
        coverage.append(status)
        candidates.extend(records)
    elif "wechat" in selected:
        coverage.append({"source": "wechat", "status": "not_configured",
                         "reason": "等待微信登录和公众号验证", "required": False})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_source, source, settings, observed_at, config["topics"])
                   for source in config["rsshub"] if source["id"] in selected]
        for future in futures:
            status, records = future.result()
            coverage.append(status)
            candidates.extend(records)
    return {
        "collected_at": observed_at, "coverage": coverage,
        "candidates": candidates,
        "topic_candidate_count": sum(bool(item["topic_matches"]) for item in candidates),
        "note": "热榜是发现线索；关键词命中不是重要性评分。原文核验后才能进入每日简报。",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-wechat", action="store_true")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "latest.json")
    args = parser.parse_args()
    selected = set(args.sources.split(","))
    if not selected or not selected <= {"wechat", "weibo", "zhihu", "bilibili"}:
        parser.error("Choose wechat,weibo,zhihu,bilibili.")
    result = collect(args.sync_wechat, selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    args.output.chmod(0o600)
    print(json.dumps({"coverage": result["coverage"], "candidates": len(result["candidates"]),
                      "topic_candidate_count": result["topic_candidate_count"],
                      "output": str(args.output.resolve())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

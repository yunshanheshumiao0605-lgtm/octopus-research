#!/usr/bin/env python3
"""Local daily-brief windows and fact-level history. No network or credentials.

The hosting agent curates semantic event/fact keys from inspected evidence.
This helper filters dates, detects already reported facts and commits only the
events actually included in a saved brief. It does not infer truth or send mail.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
STATE_FILE = "daily-events.json"


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("A timestamp must include its UTC offset")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def load_state(directory: Path) -> dict:
    path = directory / STATE_FILE
    if not path.exists():
        return {"schema": 1, "revision": 0, "last_successful_cutoff": None, "events": {}, "runs": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != 1 or not isinstance(state.get("events"), dict) or not isinstance(state.get("runs"), dict):
        raise ValueError("Unsupported or corrupt daily history; refusing to reset it")
    if not isinstance(state.get("revision"), int):
        raise ValueError("Invalid history revision")
    return state


def make_window(directory: Path, now: datetime) -> dict:
    state = load_state(directory)
    end = now.astimezone(timezone.utc)
    start = timestamp(state["last_successful_cutoff"]) if state["last_successful_cutoff"] else end - timedelta(hours=24)
    if start > end:
        raise ValueError("Research cutoff precedes the last successful run")
    retrieval_start = min(start, end - timedelta(days=7))
    return {
        "schema": 1, "run_id": uuid.uuid4().hex, "state_revision": state["revision"],
        "start": iso(start), "end": iso(end), "retrieval_start": iso(retrieval_start),
        "timezone": "Asia/Shanghai", "start_local": start.astimezone(SHANGHAI).isoformat(),
        "end_local": end.astimezone(SHANGHAI).isoformat(),
        "history_available": bool(state["runs"]),
        "engine_lookback_days": max(2, (end.date() - retrieval_start.date()).days + 1),
    }


def classify_time(raw: str | None, window: dict) -> str:
    if not raw:
        return "undated_review"
    start, end, earliest = (timestamp(window[k]) for k in ("start", "end", "retrieval_start"))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        day = datetime.strptime(raw, "%Y-%m-%d").date()
        if day > end.astimezone(SHANGHAI).date():
            return "future_review"
        if day < earliest.astimezone(SHANGHAI).date():
            return "out_of_window"
        return "date_only_review"
    dt = timestamp(raw)
    if dt > end:
        return "future_review"
    if dt >= start:
        return "in_window"
    return "delayed_evidence" if dt >= earliest else "out_of_window"


def validate_event(raw: dict) -> dict:
    event = dict(raw)
    key = event.get("event_key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Each event requires a stable semantic event_key")
    event["event_key"] = normalized(key)
    event["event_id"] = hashlib.sha256(event["event_key"].encode()).hexdigest()[:20]
    facts = event.get("facts")
    if not isinstance(facts, dict) or not facts or any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip() for k, v in facts.items()):
        raise ValueError("facts must be a nonempty mapping of stable fact keys to nonempty string values")
    event["facts"] = {normalized(k): normalized(v) for k, v in facts.items()}
    if len(event["facts"]) != len(facts):
        raise ValueError("Duplicate normalized fact keys")
    sources = event.get("sources")
    if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or urlsplit(s).scheme not in ("https", "http") or not urlsplit(s).hostname for s in sources):
        raise ValueError("Each event requires actual HTTP(S) source links")
    event["sources"] = list(dict.fromkeys(sources))
    if not isinstance(event.get("claim"), str) or not event["claim"].strip():
        raise ValueError("Each event requires a source-grounded claim")
    if event.get("published_at") is not None and not isinstance(event["published_at"], str):
        raise ValueError("published_at must be a dated source string or null")
    return event


def select_events(directory: Path, window: dict, manifest: dict) -> dict:
    state = load_state(directory)
    if window["state_revision"] != state["revision"]:
        raise ValueError("History changed; prepare and select again")
    start, end, earliest = (timestamp(window[k]) for k in ("start", "end", "retrieval_start"))
    if earliest > start or start > end:
        raise ValueError("Invalid time window")
    coverage = manifest.get("coverage")
    if not isinstance(coverage, list) or not coverage:
        raise ValueError("Record actual source coverage before selection")
    for row in coverage:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str) or row.get("status") not in ("ok", "empty", "error", "unavailable") or not isinstance(row.get("required"), bool):
            raise ValueError("Coverage needs source, status and required boolean")
    if not isinstance(manifest.get("events"), list):
        raise ValueError("events must be a list")
    merged = {}
    for raw in manifest["events"]:
        event = validate_event(raw)
        eid = event["event_id"]
        if eid in merged:
            prior = merged[eid]
            if any(k in prior["facts"] and prior["facts"][k] != v for k, v in event["facts"].items()):
                raise ValueError("Conflicting facts for one event; resolve or preserve uncertainty before selecting")
            if prior.get("published_at") != event.get("published_at"):
                raise ValueError("Duplicate event timestamps differ; curate one evidence-backed update timestamp")
            prior["facts"].update(event["facts"])
            prior["sources"] = list(dict.fromkeys(prior["sources"] + event["sources"]))
        else:
            merged[eid] = event
    result = {"schema": 1, "window": window, "coverage": coverage, "accepted": [], "review": [], "skipped": []}
    for eid, event in merged.items():
        old = state["events"].get(eid)
        changes = {k: v for k, v in event["facts"].items() if not old or old["facts"].get(k) != v}
        event["changed_facts"] = changes
        event["previous_brief"] = old.get("last_brief") if old else None
        event["time_class"] = classify_time(event.get("published_at"), window)
        if not changes:
            event["reason"] = "already_reported"
            result["skipped"].append(event)
        elif event["time_class"] == "out_of_window":
            event["reason"] = "out_of_window"
            result["skipped"].append(event)
        elif event["time_class"] not in ("in_window", "delayed_evidence"):
            event["reason"] = event["time_class"]
            result["review"].append(event)
        elif old and not str(event.get("update_reason") or "").strip():
            event["reason"] = "explain_material_change"
            result["review"].append(event)
        else:
            event["reason"] = "material_update" if old else "new_event"
            result["accepted"].append(event)
    return result


@contextmanager
def history_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".daily-events.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def commit(directory: Path, selection: dict, included: list[str], brief: Path, status: str) -> dict:
    if status not in ("complete", "partial"):
        raise ValueError("status must be complete or partial")
    if not isinstance(included, list) or any(not isinstance(x, str) for x in included) or len(set(included)) != len(included):
        raise ValueError("included must be a JSON list of unique accepted event IDs")
    accepted = {e["event_id"]: e for e in selection["accepted"]}
    if set(included) - accepted.keys():
        raise ValueError("Cannot commit a skipped, unverified or unknown event")
    if not brief.is_file() or not brief.read_text(encoding="utf-8").strip():
        raise ValueError("Save the actual final brief before committing")
    coverage = selection["coverage"]
    if status == "complete" and (not coverage or not any(r["required"] for r in coverage) or any(r["required"] and r["status"] not in ("ok", "empty") for r in coverage)):
        raise ValueError("Required sources are incomplete; use partial and keep the old cutoff")
    window = selection["window"]
    with history_lock(directory):
        state = load_state(directory)
        if window["run_id"] in state["runs"]:
            return {"status": "already_committed", "run_id": window["run_id"]}
        if state["revision"] != window["state_revision"]:
            raise ValueError("History changed; reselect before commit")
        for eid in included:
            event = accepted[eid]
            previous = state["events"].get(eid, {})
            state["events"][eid] = {
                "event_key": event["event_key"], "facts": {**previous.get("facts", {}), **event["facts"]},
                "first_seen": previous.get("first_seen", window["end"]), "last_seen": window["end"],
                "last_changed_facts": event["changed_facts"], "sources": event["sources"],
                "last_brief": str(brief.resolve()), "status": "included_in_saved_brief",
            }
        state["runs"][window["run_id"]] = {
            "status": status, "cutoff": window["end"], "coverage": coverage,
            "brief": str(brief.resolve()), "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
            "included_event_ids": included, "delivery": "not_recorded",
        }
        if status == "complete":
            state["last_successful_cutoff"] = window["end"]
        state["revision"] += 1
        atomic_json(directory / STATE_FILE, state)
        return {"status": "saved", "run_status": status, "run_id": window["run_id"], "events_recorded": len(included), "last_successful_cutoff": state["last_successful_cutoff"], "delivery": "not_recorded"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    window_cmd = sub.add_parser("window")
    window_cmd.add_argument("--now", help="Optional timezone-aware cutoff for reproducibility")
    select_cmd = sub.add_parser("select")
    select_cmd.add_argument("--window", type=Path, required=True)
    select_cmd.add_argument("--manifest", type=Path, required=True)
    commit_cmd = sub.add_parser("commit")
    commit_cmd.add_argument("--selection", type=Path, required=True)
    commit_cmd.add_argument("--included", type=Path, required=True)
    commit_cmd.add_argument("--brief", type=Path, required=True)
    commit_cmd.add_argument("--status", choices=["complete", "partial"], required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    try:
        if args.command == "window":
            result = make_window(args.state_dir, timestamp(args.now) if args.now else datetime.now(timezone.utc))
        elif args.command == "select":
            result = select_events(args.state_dir, read(args.window), read(args.manifest))
        else:
            result = commit(args.state_dir, read(args.selection), read(args.included), args.brief, args.status)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Daily history error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

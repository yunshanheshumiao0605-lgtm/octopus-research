"""Offline regression tests: no real credentials, browsers, or API calls."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import daily_brief as daily
from lib import env, pipeline, render, skill_meta

spec = importlib.util.spec_from_file_location("last30days_cli_test", SCRIPTS / "last30days.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

NOW = datetime(2026, 10, 20, 2, tzinfo=timezone.utc)
COVERAGE = [{"source": "official_cn", "status": "ok", "required": True}, {"source": "official_global", "status": "ok", "required": True}]


def event(**changes):
    result = {"event_key": "示例公司|产品v2发布", "claim": "A verified change", "facts": {"availability": "public_beta"}, "published_at": "2026-10-20T09:00:00+08:00", "sources": ["https://example.com/release"]}
    result.update(changes)
    return result


class BrowserPolicyTests(unittest.TestCase):
    def setUp(self):
        self.extractor = mock.Mock(return_value={})
        self.module = types.ModuleType("lib.cookie_extract")
        self.module.extract_cookies = self.extractor

    def extract(self, config):
        with mock.patch.dict(sys.modules, {"lib.cookie_extract": self.module}):
            return env.extract_browser_credentials(config)

    def test_defaults_false_consent_and_invalid_selector_never_extract(self):
        for config in [{}, {"FROM_BROWSER": "auto"}, {"BROWSER_CONSENT": "true"}, {"FROM_BROWSER": "auto", "BROWSER_CONSENT": "false"}, {"FROM_BROWSER": "typo", "BROWSER_CONSENT": "true"}, {"FROM_BROWSER": "off", "BROWSER_CONSENT": "true"}]:
            with self.subTest(config=config):
                self.assertEqual({}, self.extract(config))
        self.extractor.assert_not_called()

    def test_explicit_consent_scopes_extraction_to_selected_browser(self):
        self.extract({"FROM_BROWSER": "safari", "BROWSER_CONSENT": "true"})
        self.assertGreater(self.extractor.call_count, 0)
        self.assertEqual({"safari"}, {call.args[0] for call in self.extractor.call_args_list})

    def test_existing_supplied_tokens_do_not_extract(self):
        self.extract({"FROM_BROWSER": "auto", "BROWSER_CONSENT": "true", "AUTH_TOKEN": "fake", "CT0": "fake", "TRUTHSOCIAL_TOKEN": "fake"})
        self.extractor.assert_not_called()

    def test_config_loads_preferences_without_reading_real_credentials(self):
        fake_auth = types.SimpleNamespace(token=None, source="none", status="missing", account_id=None, codex_auth_file="unused")
        with mock.patch.dict("os.environ", {"FUN_LEVEL": "low", "ELI5_MODE": "true"}, clear=True), mock.patch.object(env, "_load_keychain", return_value={}), mock.patch.object(env, "_find_project_env", return_value=None), mock.patch.object(env, "load_env_file", return_value={}), mock.patch.object(env, "get_openai_auth", return_value=fake_auth), mock.patch.object(env, "extract_browser_credentials", return_value={}) as read_browser:
            config = env.get_config()
        self.assertEqual("low", config["FUN_LEVEL"])
        self.assertEqual("true", config["ELI5_MODE"])
        self.assertEqual("off", config["FROM_BROWSER"])
        self.assertEqual("false", read_browser.call_args.args[0]["BROWSER_CONSENT"])


class DailyHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.brief = self.directory / "brief.md"
        self.brief.write_text("实际入选的简报内容", encoding="utf-8")
        self.window = daily.make_window(self.directory, NOW)

    def tearDown(self):
        self.tmp.cleanup()

    def select(self, rows, window=None, coverage=None):
        return daily.select_events(self.directory, window or self.window, {"coverage": coverage or COVERAGE, "events": rows})

    def save(self, selection, status="complete", ids=None):
        return daily.commit(self.directory, selection, ids if ids is not None else [e["event_id"] for e in selection["accepted"]], self.brief, status)

    def test_first_window_uses_24_hours_and_shanghai_display(self):
        self.assertEqual("2026-10-20T10:00:00+08:00", self.window["end_local"])
        self.assertEqual(timedelta(hours=24), daily.timestamp(self.window["end"]) - daily.timestamp(self.window["start"]))
        self.assertFalse(self.window["history_available"])

    def test_date_only_unknown_future_and_old_are_not_fresh_events(self):
        rows = [event(event_key=f"topic{i}", published_at=value) for i, value in enumerate(["2026-10-20", None, "2026-10-21T10:00:00+08:00", "2026-09-01T10:00:00+08:00"])]
        result = self.select(rows)
        self.assertEqual([], result["accepted"])
        self.assertEqual(3, len(result["review"]))
        self.assertEqual("out_of_window", result["skipped"][0]["reason"])

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            self.select([event(published_at="2026-10-20T09:00:00")])

    def test_delayed_material_is_explicitly_labelled(self):
        result = self.select([event(published_at="2026-10-16T09:00:00+08:00")])
        self.assertEqual("delayed_evidence", result["accepted"][0]["time_class"])

    def test_reposts_merge_in_batch_and_do_not_repeat_tomorrow(self):
        result = self.select([event(), event(sources=["https://example.com/repost"])])
        self.assertEqual(1, len(result["accepted"]))
        self.save(result)
        tomorrow = daily.make_window(self.directory, NOW + timedelta(days=1))
        repeat = self.select([event(published_at="2026-10-21T09:00:00+08:00", sources=["https://example.com/another-repost"])], tomorrow)
        self.assertEqual([], repeat["accepted"])
        self.assertEqual("already_reported", repeat["skipped"][0]["reason"])

    def test_material_update_needs_reason_then_passes(self):
        self.save(self.select([event()]))
        tomorrow = daily.make_window(self.directory, NOW + timedelta(days=1))
        changed = event(facts={"availability": "general_availability"}, published_at="2026-10-21T09:00:00+08:00")
        self.assertEqual("explain_material_change", self.select([changed], tomorrow)["review"][0]["reason"])
        changed["update_reason"] = "从公测变为正式开放"
        self.assertEqual("material_update", self.select([changed], tomorrow)["accepted"][0]["reason"])

    def test_partial_failure_does_not_advance_success_cutoff(self):
        self.save(self.select([event()]))
        tomorrow = daily.make_window(self.directory, NOW + timedelta(days=1))
        bad = [{"source": "official_cn", "status": "error", "required": True}]
        result = self.select([event(event_key="another", published_at="2026-10-21T09:00:00+08:00")], tomorrow, bad)
        with self.assertRaises(ValueError):
            self.save(result)
        self.save(result, status="partial")
        self.assertEqual(self.window["end"], daily.load_state(self.directory)["last_successful_cutoff"])

    def test_only_selected_events_recorded_and_no_delivery_claim(self):
        result = self.select([event(), event(event_key="another")])
        self.save(result, ids=[result["accepted"][0]["event_id"]])
        state = daily.load_state(self.directory)
        self.assertEqual(1, len(state["events"]))
        self.assertEqual("not_recorded", next(iter(state["runs"].values()))["delivery"])

    def test_commit_idempotent_and_stale_other_run_rejected(self):
        first = self.select([event()])
        other_window = daily.make_window(self.directory, NOW)
        second = self.select([event(event_key="another")], other_window)
        self.save(first)
        self.assertEqual("already_committed", self.save(first)["status"])
        with self.assertRaises(ValueError):
            self.save(second)

    def test_corrupt_history_is_preserved(self):
        path = self.directory / daily.STATE_FILE
        path.write_text("broken")
        with self.assertRaises(ValueError):
            daily.make_window(self.directory, NOW)
        self.assertEqual("broken", path.read_text())

    def test_unverified_event_cannot_be_committed(self):
        result = self.select([event(published_at=None)])
        with self.assertRaises(ValueError):
            self.save(result, ids=[result["review"][0]["event_id"]])

    def test_empty_successful_brief_can_advance_without_invented_items(self):
        self.save(self.select([]), ids=[])
        state = daily.load_state(self.directory)
        self.assertEqual({}, state["events"])
        self.assertEqual(self.window["end"], state["last_successful_cutoff"])

    def test_cli_roundtrip(self):
        manifest = self.directory / "manifest.json"
        manifest.write_text(json.dumps({"coverage": COVERAGE, "events": [event()]}))
        window = self.directory / "window.json"
        window.write_text(json.dumps(self.window))
        base = [sys.executable, str(SCRIPTS / "daily_brief.py"), "--state-dir", str(self.directory)]
        result = subprocess.run(base + ["select", "--window", str(window), "--manifest", str(manifest)], capture_output=True, text=True, check=True)
        selection = self.directory / "selection.json"
        selection.write_text(result.stdout)
        ids = self.directory / "included.json"
        ids.write_text(json.dumps([json.loads(result.stdout)["accepted"][0]["event_id"]]))
        output = subprocess.run(base + ["commit", "--selection", str(selection), "--included", str(ids), "--brief", str(self.brief), "--status", "complete"], capture_output=True, text=True, check=True)
        self.assertEqual("saved", json.loads(output.stdout)["status"])


class EngineRegressionTests(unittest.TestCase):
    def test_chinese_and_same_day_outputs_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for topic in ["AI 商业趋势", "AI 商业趋势", "AI 商业趋势", "科技变化"]:
                target = Path(cli.compute_save_path_display(tmp, topic, "personal", "md"))
                path = cli.save_output(types.SimpleNamespace(topic=topic), "md", tmp, rendered_content=topic, output_path=target)
                self.assertEqual(target, path)
                self.assertEqual(topic, path.read_text())
                paths.append(path)
            self.assertEqual(4, len(set(paths)))

    def test_partial_source_failure_is_not_reported_as_all_done(self):
        report = types.SimpleNamespace(errors_by_source={"x": "unavailable"})
        with mock.patch.object(render, "_build_source_footer_lines", return_value=["HN: 3"]), mock.patch.object(render, "_top_voices_footer_line", return_value=None):
            footer = "\n".join(render._render_emoji_footer(report, None))
        self.assertIn("partial", footer)
        self.assertIn("x", footer)
        self.assertNotIn("All agents reported back", footer)

    def test_mock_pipeline_avoids_network_and_default_fun_scoring(self):
        with mock.patch("lib.http.request", side_effect=AssertionError("unexpected network")), mock.patch.object(pipeline.rerank, "score_fun") as fun:
            report = pipeline.run(topic="AI workflow", config={}, depth="quick", requested_sources=["reddit", "hackernews"], mock=True, web_backend="none")
        fun.assert_not_called()
        self.assertTrue(report.items_by_source)

    def test_metadata_version_and_fun_off(self):
        self.assertEqual("0.1.0", skill_meta.read_skill_version(SCRIPTS.parent / "SKILL.md"))
        self.assertEqual([], render._render_best_takes([types.SimpleNamespace(fun_score=100)], limit=0))


if __name__ == "__main__":
    unittest.main()

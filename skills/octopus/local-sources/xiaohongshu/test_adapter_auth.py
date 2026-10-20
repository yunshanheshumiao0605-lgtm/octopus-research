"""Offline checks for the installed adapter's authenticated API boundary."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "scripts"))
from lib import http


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT.parents[1] / "scripts/lib" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


env = load("lib.xhs_test_env", "env.py")
adapter = load("lib.xhs_test_adapter", "xiaohongshu_api.py")
BASE = "http://127.0.0.1:18060"
TOKEN = "test-only-local-service-token"


class AuthChecks(unittest.TestCase):
    def test_config_loads_separate_token_without_using_x_credentials(self):
        auth = types.SimpleNamespace(token=None, source="none", status="missing", account_id=None, codex_auth_file="")
        with patch.dict(os.environ, {"FROM_BROWSER": "off", "BROWSER_CONSENT": "false"}, clear=True), \
             patch.object(env, "load_env_file", return_value={"XIAOHONGSHU_API_TOKEN": TOKEN, "AUTH_TOKEN": "x-token"}), \
             patch.object(env, "_find_project_env", return_value=None), \
             patch.object(env, "_load_keychain", return_value={}), \
             patch.object(env, "get_openai_auth", return_value=auth):
            config = env.get_config()
        self.assertEqual(config["XIAOHONGSHU_API_TOKEN"], TOKEN)
        self.assertEqual(config["AUTH_TOKEN"], "x-token")

    def test_availability_passes_token_only_to_protected_endpoint(self):
        with patch.object(http, "get", side_effect=[{"success": True}, {"data": {"is_logged_in": True}}]) as get:
            self.assertTrue(env.is_xiaohongshu_available({"XIAOHONGSHU_API_BASE": BASE, "XIAOHONGSHU_API_TOKEN": TOKEN}))
        self.assertNotIn("headers", get.call_args_list[0].kwargs)
        self.assertEqual(get.call_args_list[1].kwargs["headers"], {"Authorization": "Bearer " + TOKEN})

    def test_search_authenticates_login_and_search(self):
        payload = {"data": {"feeds": [{"id": "sample", "noteCard": {"displayTitle": "Sample", "interactInfo": {"likedCount": "12"}}}]}}
        with patch.object(http, "get", return_value={"data": {"is_logged_in": True}}) as get, \
             patch.object(http, "post", return_value=payload) as post:
            result = adapter.search_feeds("AI 工具", "2026-10-13", "2026-10-20", BASE, api_token=TOKEN)
        for call in [get.call_args, post.call_args]:
            self.assertEqual(call.kwargs["headers"], {"Authorization": "Bearer " + TOKEN})
        self.assertEqual(result[0]["title"], "Sample")
        self.assertNotIn(TOKEN, repr(result))

    def test_failed_login_does_not_search(self):
        with patch.object(http, "get", return_value={"data": {"is_logged_in": False}}), \
             patch.object(http, "post") as post:
            with self.assertRaises(http.HTTPError):
                adapter.search_feeds("AI 工具", "2026-10-13", "2026-10-20", BASE, api_token=TOKEN)
        post.assert_not_called()

    def test_legacy_service_does_not_receive_bogus_authorization(self):
        with patch.object(http, "get", return_value={"data": {"is_logged_in": True}}) as get, \
             patch.object(http, "post", return_value={"data": {"feeds": []}}) as post:
            adapter.search_feeds("AI", "2026-10-13", "2026-10-20", BASE)
        self.assertIsNone(get.call_args.kwargs["headers"])
        self.assertIsNone(post.call_args.kwargs["headers"])


if __name__ == "__main__":
    unittest.main()

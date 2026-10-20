"""Offline portability and privacy checks for release installation/configuration."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load("octopus_installer", "tools/install.py")
initializer = load("octopus_initializer", "skills/octopus/scripts/init_local_sources.py")
sessions = load("octopus_sessions", "skills/octopus/scripts/source_session.py")


class PackagingChecks(unittest.TestCase):
    def test_private_configuration_is_random_private_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)
            paths = initializer.initialize(skill, {"domestic", "xiaohongshu"})
            self.assertEqual(4, len(paths))
            snapshots = {p: (skill / p).read_bytes() for p in paths}
            settings = json.loads((skill / "local-sources/domestic/runtime/settings.json").read_text())
            xhs = json.loads((skill / "local-sources/xiaohongshu/runtime/service.json").read_text())
            values = {settings["rsshub"]["access_key"], settings["werss"]["password"], xhs["token"]}
            self.assertEqual(3, len(values))
            self.assertTrue(all(len(value) >= 32 for value in values))
            self.assertEqual([], initializer.initialize(skill, {"domestic", "xiaohongshu"}))
            self.assertEqual(snapshots, {p: (skill / p).read_bytes() for p in paths})
            if os.name == "posix":
                for path in paths:
                    self.assertEqual(0o600, (skill / path).stat().st_mode & 0o777)
            config = json.loads((skill / "local-sources/domestic/runtime/werss.yaml").read_text())
            self.assertFalse(config["server"]["enable_job"])
            self.assertFalse(config["weread"]["auto_add_to_shelf"])

    def test_initialization_only_creates_selected_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)
            initializer.initialize(skill, {"xiaohongshu"})
            self.assertFalse((skill / "local-sources/domestic").exists())

    def test_fresh_install_has_both_portable_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "skills"
            self.assertEqual(2, len(installer.install(destination)))
            alias = destination / "octopus-query-alias/SKILL.md"
            self.assertIn("../octopus/SKILL.md", alias.read_text())
            self.assertTrue((alias.parent / "../octopus/scripts/source_session.py").is_file())
            self.assertFalse(list(destination.rglob("runtime")))

    def test_install_refuses_to_overwrite_an_existing_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            target = destination / "octopus"
            target.mkdir()
            marker = target / "preferences.local.md"
            marker.write_text("existing user preferences")
            with self.assertRaises(FileExistsError):
                installer.install(destination)
            self.assertEqual("existing user preferences", marker.read_text())
            self.assertFalse((destination / "octopus-query-alias").exists())

    def test_install_does_not_copy_configured_source_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "source"
            for name in ("octopus", "octopus-query-alias"):
                source = repo / "skills" / name
                source.mkdir(parents=True)
                (source / "SKILL.md").write_text("test skill")
            runtime = repo / "skills/octopus/local-sources/domestic/runtime"
            runtime.mkdir(parents=True)
            (runtime / "settings.json").write_text('{"password":"test-only"}')
            (repo / "skills/octopus/preferences.local.md").write_text("private")
            with mock.patch.object(installer, "ROOT", repo):
                installer.install(root / "destination")
            self.assertFalse(list((root / "destination").rglob("settings.json")))
            self.assertFalse(list((root / "destination").rglob("preferences.local.md")))

    def test_service_auth_is_scoped_to_research_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)
            initializer.initialize(skill, {"xiaohongshu"})
            config = json.loads((skill / "local-sources/xiaohongshu/runtime/service.json").read_text())
            process = mock.Mock()
            process.wait.return_value = 0
            before = dict(os.environ)
            with mock.patch.object(sessions, "LOCAL", skill / "local-sources"), \
                 mock.patch.object(sessions, "source_services", return_value=contextlib.nullcontext()), \
                 mock.patch.object(sessions, "stop_group"), \
                 mock.patch.object(sessions.subprocess, "Popen", return_value=process) as spawn:
                self.assertEqual(0, sessions.run_with_services(["xiaohongshu"], ["example-command"]))
            env = spawn.call_args.kwargs["env"]
            self.assertEqual(config["token"], env["XIAOHONGSHU_API_TOKEN"])
            self.assertEqual("http://127.0.0.1:18060", env["XIAOHONGSHU_API_BASE"])
            self.assertEqual(before, dict(os.environ))


if __name__ == "__main__":
    unittest.main()

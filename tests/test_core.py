import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "bin" / "villode-desktop"


def load_module():
    loader = SourceFileLoader("villode_desktop_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesktopCoreTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.module.CONFIG_DIR = root / "config"
        self.module.CONFIG_FILE = self.module.CONFIG_DIR / "config.json"
        self.module.CONFIG_LOCK_FILE = self.module.CONFIG_DIR / "config.lock"
        self.module.PID_FILE = root / "cache" / "desktop.pid"
        self.module.PID_LOCK_FILE = root / "cache" / "instance.lock"
        self.module.OPERATION_LOCK_FILE = root / "cache" / "operation.lock"

    def tearDown(self):
        self.temporary.cleanup()

    def config(self, mode, source):
        return {
            "version": 2,
            "mode": mode,
            "source": source,
            "sources": {
                "static": "/wallpaper.png",
                "video": "/wallpaper.mp4",
                "html": "/desktop.html",
            },
            "fit": "cover",
            "background": "#101522",
        }

    def test_legacy_source_is_migrated_to_its_mode(self):
        self.module.CONFIG_DIR.mkdir(parents=True)
        self.module.CONFIG_FILE.write_text(
            json.dumps(
                {
                    "version": 1,
                    "mode": "video",
                    "source": "/legacy.mp4",
                    "fit": "cover",
                    "background": "#101522",
                }
            ),
            encoding="utf-8",
        )
        loaded = self.module.load_config()
        self.assertEqual(loaded["source"], "/legacy.mp4")
        self.assertEqual(loaded["sources"]["video"], "/legacy.mp4")
        self.assertTrue(loaded["sources"]["static"])

    def test_concurrent_saves_remain_atomic(self):
        children = []
        for index in range(24):
            pid = os.fork()
            if pid == 0:
                try:
                    mode = self.module.MODES[index % len(self.module.MODES)]
                    self.module.save_config(self.config(mode, f"/source-{index}"))
                except Exception:
                    os._exit(1)
                os._exit(0)
            children.append(pid)
        for pid in children:
            _, status = os.waitpid(pid, 0)
            self.assertEqual(status, 0)

        payload = json.loads(self.module.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 2)
        self.assertIn(payload["mode"], self.module.MODES)
        self.assertEqual(payload["source"], payload["sources"][payload["mode"]])
        self.assertEqual(list(self.module.CONFIG_DIR.glob(".config.json.*.tmp")), [])

    def test_static_run_delegates_without_importing_gtk(self):
        config = self.config("static", "/wallpaper.png")
        with mock.patch.object(self.module, "load_config", return_value=config), mock.patch.object(
            self.module, "apply_static_wallpaper", return_value=(True, "")
        ) as apply:
            result = self.module.run_desktop(Namespace(url=None, escape_quits=False))
        self.assertEqual(result, 0)
        apply.assert_called_once_with("/wallpaper.png")

    def test_only_bundled_home_is_trusted_for_local_actions(self):
        bundled = self.module.DEFAULT_HTML.resolve().as_uri()
        sibling = self.module.DEFAULT_HTML.with_name("custom.html").resolve().as_uri()
        self.assertTrue(self.module.is_trusted_home_uri(bundled))
        self.assertFalse(self.module.is_trusted_home_uri(sibling))
        self.assertFalse(self.module.is_trusted_home_uri("https://example.com/"))

    def test_instance_lock_rejects_a_second_process(self):
        handle = self.module.acquire_instance_lock()
        self.assertIsNotNone(handle)
        pid = os.fork()
        if pid == 0:
            second = self.module.acquire_instance_lock()
            os._exit(0 if second is None else 1)
        _, status = os.waitpid(pid, 0)
        self.module.release_instance_lock(handle)
        self.assertEqual(status, 0)



    def test_playback_scale_clamped(self):
        self.assertEqual(self.module.clamp_playback_scale(2.0), 1.0)
        self.assertEqual(self.module.clamp_playback_scale(0.1), 0.5)
        self.assertAlmostEqual(self.module.clamp_playback_scale(0.85), 0.85)

    def test_power_save_defaults_roundtrip(self):
        cfg = self.config("video", "/wallpaper.mp4")
        cfg["power_save"] = False
        cfg["playback_scale"] = 0.75
        self.module.save_config(cfg)
        loaded = self.module.load_config()
        self.assertFalse(loaded["power_save"])
        self.assertAlmostEqual(loaded["playback_scale"], 0.75)

    def test_power_save_off_never_pauses(self):
        pause, reason = self.module.hyprland_should_pause_media({"power_save": False})
        self.assertFalse(pause)
        self.assertEqual(reason, "power_save_off")

    def test_power_user_script_defines_hook(self):
        script = self.module.power_user_script()
        self.assertIn("__villodeSetPaused", script)

    def test_pause_ignores_fullscreen_on_other_workspace(self):
        """Regression: FlClash maximize on ws3 must not freeze wallpaper on ws4."""
        mon = {
            "id": 0,
            "width": 1920,
            "height": 1080,
            "focused": True,
            "dpmsStatus": True,
            "activeWorkspace": {"id": 4, "name": "4"},
            "reserved": [60, 10, 10, 88],
        }
        clients = [
            {
                "class": "com.follow.clashx",
                "fullscreen": 1,
                "fullscreenClient": 1,
                "size": [1826, 958],
                "workspace": {"id": 3},
                "monitor": 0,
                "mapped": True,
                "hidden": False,
            },
            {
                "class": "Alacritty",
                "fullscreen": 0,
                "size": [906, 958],
                "workspace": {"id": 4},
                "monitor": 0,
                "mapped": True,
                "hidden": False,
            },
        ]

        def fake_json(cmd):
            if cmd == "monitors":
                return [mon]
            if cmd == "clients":
                return clients
            return None

        orig = self.module.hyprctl_json
        self.module.hyprctl_json = fake_json
        try:
            pause, reason = self.module.hyprland_should_pause_media({"power_save": True})
            self.assertFalse(pause)
            self.assertEqual(reason, "ok")
        finally:
            self.module.hyprctl_json = orig

    def test_pause_on_true_fullscreen_active_workspace(self):
        mon = {
            "id": 0,
            "width": 1920,
            "height": 1080,
            "focused": True,
            "dpmsStatus": True,
            "activeWorkspace": {"id": 2, "name": "2"},
            "reserved": [0, 0, 0, 0],
        }
        clients = [
            {
                "class": "mpv",
                "fullscreen": 2,
                "fullscreenClient": 2,
                "size": [1920, 1080],
                "workspace": {"id": 2},
                "monitor": 0,
                "mapped": True,
                "hidden": False,
            }
        ]

        def fake_json(cmd):
            if cmd == "monitors":
                return [mon]
            if cmd == "clients":
                return clients
            return None

        orig = self.module.hyprctl_json
        self.module.hyprctl_json = fake_json
        try:
            pause, reason = self.module.hyprland_should_pause_media({"power_save": True})
            self.assertTrue(pause)
            self.assertEqual(reason, "fullscreen")
        finally:
            self.module.hyprctl_json = orig

    def test_maximize_on_active_workspace_pauses(self):
        mon = {
            "id": 0,
            "width": 1920,
            "height": 1080,
            "focused": True,
            "dpmsStatus": True,
            "activeWorkspace": {"id": 1, "name": "1"},
            "reserved": [60, 10, 10, 88],
        }
        # 1826x958 fills usable area after reserved insets
        clients = [
            {
                "class": "google-chrome",
                "fullscreen": 1,
                "fullscreenClient": 1,
                "size": [1826, 958],
                "workspace": {"id": 1},
                "monitor": 0,
                "mapped": True,
                "hidden": False,
            }
        ]

        def fake_json(cmd):
            if cmd == "monitors":
                return [mon]
            if cmd == "clients":
                return clients
            return None

        orig = self.module.hyprctl_json
        self.module.hyprctl_json = fake_json
        try:
            pause, reason = self.module.hyprland_should_pause_media({"power_save": True})
            self.assertTrue(pause)
            self.assertIn(reason, ("maximized", "covered"))
        finally:
            self.module.hyprctl_json = orig

if __name__ == "__main__":
    unittest.main()

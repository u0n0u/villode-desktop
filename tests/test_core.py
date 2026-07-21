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
                # Small floating-ish window on active workspace — must not trip cover.
                "class": "Alacritty",
                "fullscreen": 0,
                "size": [400, 300],
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
            pause, reason = self.module.hyprland_should_pause_media(
                {"power_save": True, "pause_cover_threshold": 0.35, "battery_power_boost": False}
            )
            self.assertFalse(pause, reason)
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


    def test_partial_cover_pauses_at_threshold(self):
        mon = {
            "id": 0,
            "width": 1920,
            "height": 1080,
            "focused": True,
            "dpmsStatus": True,
            "activeWorkspace": {"id": 1, "name": "1"},
            "reserved": [60, 10, 10, 88],
        }
        # ~half usable area
        clients = [
            {
                "class": "Alacritty",
                "fullscreen": 0,
                "size": [960, 958],
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
            pause, reason = self.module.hyprland_should_pause_media(
                {"power_save": True, "pause_cover_threshold": 0.35, "battery_power_boost": False}
            )
            self.assertTrue(pause)
            self.assertEqual(reason, "covered")
            pause2, _ = self.module.hyprland_should_pause_media(
                {"power_save": True, "pause_cover_threshold": 0.9, "battery_power_boost": False}
            )
            self.assertFalse(pause2)
        finally:
            self.module.hyprctl_json = orig

    def test_effective_power_params_clamp(self):
        p = self.module.effective_power_params(
            {"playback_scale": 0.9, "pause_cover_threshold": 0.4, "battery_power_boost": False}
        )
        self.assertAlmostEqual(p["playback_scale"], 0.9)
        self.assertAlmostEqual(p["pause_cover_threshold"], 0.4)
        self.assertFalse(p["on_battery"])

    def test_default_playback_scale_is_cooler(self):
        self.assertLessEqual(self.module.DEFAULT_CONFIG["playback_scale"], 0.75)


    def test_mpv_fit_options_cover(self):
        opts = self.module.mpv_fit_options("cover")
        self.assertIn("panscan=1.0", opts)
        self.assertIn("keepaspect=yes", self.module.mpv_fit_options("cover"))
        self.assertIn("keepaspect=no", self.module.mpv_fit_options("stretch"))

    def test_build_mpvpaper_command_shape(self):
        self.module.BUNDLED_MPVPAPER = Path("/usr/bin/true")
        self.module.hyprland_monitor_names = lambda: ["eDP-1"]
        video = Path(self.temporary.name) / "w.mp4"
        video.write_bytes(b"not-real")
        cmd, err = self.module.build_mpvpaper_command(
            {"source": str(video), "fit": "cover"}
        )
        self.assertEqual(err, "")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd[0], "/usr/bin/true")
        self.assertIn("-p", cmd)
        self.assertIn("background", cmd)
        joined = " ".join(cmd)
        self.assertIn("hwdec=auto", joined)
        self.assertIn("loop-file=inf", joined)
        self.assertIn("no-audio", joined)

    def test_default_video_backend_is_mpv(self):
        self.assertEqual(self.module.DEFAULT_CONFIG.get("video_backend"), "mpv")

if __name__ == "__main__":
    unittest.main()

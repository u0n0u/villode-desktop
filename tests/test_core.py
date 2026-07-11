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


if __name__ == "__main__":
    unittest.main()

import queue
import sys
import threading
import unittest
from unittest.mock import Mock

from bluey.tray import Tray, WindowLifecycle


class TrayTests(unittest.TestCase):
    def test_menu_action_is_queued_until_ui_consumes_it(self):
        pending = queue.Queue()
        action = Mock()
        tray = Tray(None, pending.put, {"show": action}, lambda: False, lambda: False, Mock())
        worker = threading.Thread(target=lambda: tray._action("show")(None, None))
        worker.start(); worker.join()
        action.assert_not_called()
        pending.get_nowait()()
        action.assert_called_once()

    def test_close_hides_with_tray_and_quits_without_it(self):
        window, cleanup = Mock(), Mock()
        tray = Mock(); tray.available = threading.Event()
        lifecycle = WindowLifecycle(window, tray, cleanup)
        tray.available.set()
        lifecycle.close()
        window.withdraw.assert_called_once()
        cleanup.assert_not_called()
        lifecycle.show()
        window.deiconify.assert_called_once()
        tray.available.clear()
        lifecycle.close(); lifecycle.quit()
        cleanup.assert_called_once()
        tray.stop.assert_called_once()
        window.destroy.assert_called_once()

    def test_setup_failure_enqueues_visible_fallback(self):
        pending, failed = queue.Queue(), Mock()
        tray = Tray(None, pending.put, {}, lambda: False, lambda: False, failed, backend=object())
        tray.start()
        self.assertFalse(tray.available.is_set())
        failed.assert_not_called()
        pending.get_nowait()()
        failed.assert_called_once()

    def test_quit_cleans_tray_even_if_pairing_cleanup_fails(self):
        window, tray = Mock(), Mock()
        lifecycle = WindowLifecycle(window, tray, Mock(side_effect=RuntimeError))
        with self.assertRaises(RuntimeError):
            lifecycle.quit()
        tray.stop.assert_called_once()
        window.destroy.assert_called_once()

    @unittest.skipUnless(sys.platform == "win32", "Requires Windows tray")
    def test_native_tray_starts_and_stops(self):
        from PIL import Image
        pending = queue.Queue()
        names = ("show", "projects", "sheets", "start", "stop", "wake", "sleep", "control", "quit")
        tray = Tray(Image.new("RGB", (32, 32), "blue"), pending.put,
                    {name: lambda: None for name in names}, lambda: False, lambda: False, lambda: None)
        try:
            tray.start()
            self.assertTrue(tray.available.wait(5), "Native tray did not become available")
            self.assertTrue(tray.icon.visible)
            tray.refresh()
        finally:
            tray.stop()
            if tray.thread:
                tray.thread.join(5)
        self.assertFalse(tray.available.is_set())
        self.assertFalse(tray.thread.is_alive())

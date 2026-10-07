"""Actual Windows UI checks. Skipped explicitly on Linux; run in Windows CI."""
import ctypes
from ctypes import wintypes
import subprocess
import sys
import time
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Requires Windows desktop')
class NativeWindowsTests(unittest.TestCase):
    def test_screen_capture_and_input_backend(self):
        from PIL import ImageGrab
        import pyautogui
        image = ImageGrab.grab(all_screens=False)
        self.assertGreater(image.width, 100)
        self.assertGreater(image.height, 100)
        self.assertEqual(tuple(pyautogui.size()), image.size)
        self.assertEqual(len(pyautogui.position()), 2)

    def test_control_window_launches(self):
        user32 = ctypes.windll.user32
        enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [enum_callback, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        def control_windows():
            matches = set()
            @enum_callback
            def visit(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(hwnd, title, len(title))
                    if title.value == 'Bluey':
                        matches.add(hwnd)
                return True
            user32.EnumWindows(visit, 0)
            return matches
        existing = control_windows()
        process = subprocess.Popen([sys.executable, '-m', 'bluey.app'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 20
            handle = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    _, error = process.communicate()
                    self.fail('Bluey exited before creating its window: ' + error.decode(errors='replace'))
                # Tk overlays can share a title; ignore hidden and unrelated windows.
                handle = next(iter(control_windows() - existing), None)
                if handle:
                    break
                time.sleep(.1)
            self.assertTrue(handle, 'Bluey control window did not appear')
            rect = wintypes.RECT()
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            self.assertTrue(user32.GetWindowRect(handle, ctypes.byref(rect)))
            self.assertGreater(rect.right - rect.left, 300)
            self.assertGreater(rect.bottom - rect.top, 200)
        finally:
            process.terminate()
            process.communicate(timeout=10)


if __name__ == '__main__': unittest.main()

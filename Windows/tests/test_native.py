"""Actual Windows UI checks. Skipped explicitly on Linux; run in Windows CI."""
import ctypes
from ctypes import wintypes
import os
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
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        process = subprocess.Popen([sys.executable, '-m', 'bluey.app'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 20
            handle = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    _, error = process.communicate()
                    self.fail('Bluey exited before creating its window: ' + error.decode(errors='replace'))
                handle = user32.FindWindowW(None, 'Bluey')
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

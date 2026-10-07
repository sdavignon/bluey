import ctypes
from ctypes import wintypes as W
import sys
import unittest
from PIL import Image

from bluey.overlay import Overlay, premultiplied_bgra, render_frame


class OverlayTests(unittest.TestCase):
    def test_partial_alpha_is_premultiplied_without_color_key(self):
        image = Image.new("RGBA", (3, 1))
        image.putdata([(255, 0, 255, 0), (100, 80, 40, 128), (100, 80, 40, 255)])
        self.assertEqual(premultiplied_bgra(image), bytes([0,0,0,0, 20,40,50,128, 40,80,100,255]))

    def test_caption_can_be_removed_without_leaving_background(self):
        art = Image.new("RGBA", (84, 76), (90, 120, 230, 128))
        empty = render_frame(art, "")
        caption = render_frame(art, "A long caption " * 60)
        self.assertEqual(empty.getpixel((2, 4)), (90, 120, 230, 128))
        self.assertEqual(empty.getpixel((100, 100))[3], 0)
        self.assertEqual(caption.getpixel((100, 100))[3], 255)
        self.assertEqual(caption.getpixel((359, 159))[3], 0)

    @unittest.skipUnless(sys.platform == "win32", "Requires native Windows layered windows")
    def test_native_alpha_update_and_lifecycle(self):
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetWindowLongW.argtypes = [W.HWND, ctypes.c_int]
        user.IsWindowVisible.argtypes = [W.HWND]
        user.IsWindow.argtypes = [W.HWND]
        user.GetForegroundWindow.restype = W.HWND
        before = user.GetForegroundWindow()
        overlay = Overlay(Image.new("RGBA", (84, 76), (90, 120, 230, 128)))
        hwnd = overlay.hwnd
        try:
            style = user.GetWindowLongW(hwnd, -20)
            self.assertEqual(style & 0x080800A0, 0x080800A0)
            overlay.update(10, 10, "Caption")
            overlay.show()
            self.assertTrue(user.IsWindowVisible(hwnd))
            self.assertEqual(user.GetForegroundWindow(), before)
            overlay.update(20, 20, "Caption")
            overlay.update(20, 20, "")
            overlay.hide()
            self.assertFalse(user.IsWindowVisible(hwnd))
        finally:
            overlay.close()
        overlay.close()
        self.assertFalse(user.IsWindow(hwnd))

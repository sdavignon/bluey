import ctypes
from ctypes import wintypes as W
import sys
import unittest
from PIL import Image

from bluey.overlay import Overlay, placement, premultiplied_bgra, render_frame


class OverlayTests(unittest.TestCase):
    def test_empty_caption_reaches_right_edge_of_secondary_monitor(self):
        self.assertEqual(placement(3839, 400, (1920, 0, 3840, 1080), ""),
                         (3752, 412, False, 88, 80))

    def test_caption_flips_left_while_character_stays_at_right_edge(self):
        x, y, flip, width, height = placement(3839, 400, (1920, 0, 3840, 1080), "Hi")
        self.assertTrue(flip)
        self.assertEqual(x+274+84, 3838)
        self.assertEqual((x+width, y+height), (3840, 572))
        frame = render_frame(Image.new("RGBA", (84, 76), (90,120,230,255)), "Hi", flip)
        self.assertEqual(frame.getpixel((274, 4)), (90,120,230,255))
        self.assertEqual(frame.getpixel((10, 100)), (238,240,255,255))

    def test_negative_monitor_origin_and_top_edge(self):
        self.assertEqual(placement(-1919, -1199, (-1920,-1200,0,0), "Hi"),
                         (-1907,-1187,False,360,160))
        self.assertEqual(placement(-1, -1, (-1920,-1200,0,0), ""),
                         (-88,-80,False,88,80))

    def test_gap_nearest_monitor_bounds_clamp_to_that_monitor(self):
        self.assertEqual(placement(-100, 200, (0,0,1920,1080), ""),
                         (0,212,False,88,80))
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
        user.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
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
            overlay.update(20, 20, "", animation=((1,-1),1,0))
            animated_pixels = ctypes.string_at(overlay.pixels, overlay.width*overlay.height*4)
            overlay.update(20, 20, "", animation=None)
            static_pixels = ctypes.string_at(overlay.pixels, overlay.width*overlay.height*4)
            self.assertNotEqual(animated_pixels, static_pixels)
            self.assertIsNone(overlay.animation_state)
            rect = W.RECT()
            self.assertTrue(user.GetWindowRect(hwnd, ctypes.byref(rect)))
            self.assertEqual((rect.right-rect.left, rect.bottom-rect.top), (88,80))
            bounds = overlay.monitor_bounds(0, 0)
            self.assertLess(bounds[0], bounds[2])
            self.assertLess(bounds[1], bounds[3])
            overlay.follow(bounds[2]-1, bounds[3]-1, "Caption")
            self.assertTrue(user.GetWindowRect(hwnd, ctypes.byref(rect)))
            self.assertEqual((rect.right, rect.bottom), (bounds[2], bounds[3]))
            overlay.hide()
            self.assertFalse(user.IsWindowVisible(hwnd))
        finally:
            overlay.close()
        overlay.close()
        self.assertFalse(user.IsWindow(hwnd))

"""Per-pixel-alpha Windows companion; all methods run on the Tk UI thread."""
import ctypes
from ctypes import wintypes as W
import os
import math
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont
from .artwork import animated_character


def premultiplied_bgra(image):
    """UpdateLayeredWindow requires premultiplied, top-down BGRA pixels."""
    r,g,b,a = image.convert("RGBA").split()
    return Image.merge("RGBA", (ImageChops.multiply(b,a), ImageChops.multiply(g,a), ImageChops.multiply(r,a), a)).tobytes()


def placement(x, y, bounds, caption):
    """Keep the character next to the pointer on its monitor, not the primary."""
    left, top, right, bottom = bounds
    width, height = (360, 160) if caption else (88, 80)
    avatar_x = max(left, min(right-88, int(x)+12))
    flip = bool(caption and avatar_x+360 > right)
    window_x = avatar_x-272 if flip else avatar_x
    window_x = max(left, min(right-width, window_x))
    window_y = max(top, min(bottom-height, int(y)+12))
    return window_x, window_y, flip, width, height


def render_frame(art, caption, caption_left=False):
    image = Image.new("RGBA", (360, 160))
    image.alpha_composite(art.resize((84, 76), Image.Resampling.LANCZOS), (274 if caption_left else 2, 4))
    if caption:
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"), 14)
        except OSError:
            font = ImageFont.load_default()
        lines, line = [], ""
        # Character-based wrapping also bounds long URLs and unbroken model output.
        for char in caption[:500]:
            if char == "\n" or (line and draw.textlength(line+char, font=font) > 245):
                lines.append(line.rstrip()); line = ""
                if char == "\n":
                    continue
            line += char
        lines.append(line.rstrip())
        if len(lines) > 7:
            lines = lines[:7]
            while lines[-1] and draw.textlength(lines[-1]+"…", font=font) > 245:
                lines[-1] = lines[-1][:-1]
            lines[-1] += "…"
        offset = -90 if caption_left else 0
        draw.rounded_rectangle((92+offset, 8, 358+offset, 152), radius=10, fill="#eef0ff")
        draw.multiline_text((99+offset, 14), "\n".join(lines), font=font, fill="#17151f", spacing=3)
    return image


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("size", W.DWORD), ("width", W.LONG), ("height", W.LONG),
                ("planes", W.WORD), ("bits", W.WORD), ("compression", W.DWORD),
                ("image_size", W.DWORD), ("xppm", W.LONG), ("yppm", W.LONG),
                ("used", W.DWORD), ("important", W.DWORD)]


class _Blend(ctypes.Structure):
    _fields_ = [("op", W.BYTE), ("flags", W.BYTE), ("alpha", W.BYTE), ("format", W.BYTE)]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("size", W.DWORD), ("monitor", W.RECT), ("work", W.RECT), ("flags", W.DWORD)]


class Overlay:
    width, height = 360, 160

    def __init__(self, art):
        self.art = art.convert("RGBA")
        self.caption = None
        self.caption_left = False
        self.animation_state = None
        self.background = None
        self.small_art = self.art.resize((84,76), Image.Resampling.LANCZOS)
        self.hwnd = self.dc = self.bitmap = self.previous = None
        self.visible = False
        self.x = self.y = 0
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        signatures = [
            (self.user.CreateWindowExW, [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID], W.HWND),
            (self.user.UpdateLayeredWindow, [W.HWND, W.HDC, ctypes.POINTER(W.POINT), ctypes.POINTER(W.SIZE), W.HDC, ctypes.POINTER(W.POINT), W.DWORD, ctypes.POINTER(_Blend), W.DWORD], W.BOOL),
            (self.user.SetWindowPos, [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT], W.BOOL),
            (self.user.ShowWindow, [W.HWND, ctypes.c_int], W.BOOL),
            (self.user.DestroyWindow, [W.HWND], W.BOOL),
            (self.user.MonitorFromPoint, [W.POINT, W.DWORD], W.HANDLE),
            (self.user.GetMonitorInfoW, [W.HANDLE, ctypes.POINTER(_MonitorInfo)], W.BOOL),
            (self.gdi.CreateCompatibleDC, [W.HDC], W.HDC),
            (self.gdi.CreateDIBSection, [W.HDC, ctypes.POINTER(_BitmapInfo), W.UINT, ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD], W.HBITMAP),
            (self.gdi.SelectObject, [W.HDC, W.HANDLE], W.HANDLE),
            (self.gdi.DeleteObject, [W.HANDLE], W.BOOL),
            (self.gdi.DeleteDC, [W.HDC], W.BOOL),
        ]
        for fn, args, result in signatures:
            fn.argtypes, fn.restype = args, result
        try:
            # LAYERED | TRANSPARENT | NOACTIVATE | TOOLWINDOW | TOPMOST.
            self.hwnd = self.user.CreateWindowExW(0x080800A8, "STATIC", "Bluey overlay", 0x80000000,
                                                 0, 0, self.width, self.height, None, None, None, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self.dc = self.gdi.CreateCompatibleDC(None)
            info = _BitmapInfo(ctypes.sizeof(_BitmapInfo), self.width, -self.height, 1, 32, 0, 0, 0, 0, 0, 0)
            self.pixels = ctypes.c_void_p()
            self.bitmap = self.gdi.CreateDIBSection(self.dc, ctypes.byref(info), 0, ctypes.byref(self.pixels), None, 0)
            if not self.dc or not self.bitmap or not self.pixels:
                raise ctypes.WinError(ctypes.get_last_error())
            self.previous = self.gdi.SelectObject(self.dc, self.bitmap)
            self.update(0, 0, "")
        except Exception:
            self.close()
            raise

    def monitor_bounds(self, x, y):
        monitor = self.user.MonitorFromPoint(W.POINT(int(x), int(y)), 2)  # nearest monitor
        info = _MonitorInfo()
        info.size = ctypes.sizeof(info)
        if not monitor or not self.user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        rect = info.monitor
        return rect.left, rect.top, rect.right, rect.bottom

    def follow(self, x, y, caption, gaze=(0,0), speaking=False, animate=True):
        px, py, flip, _, _ = placement(x, y, self.monitor_bounds(x, y), caption)
        now = time.monotonic()
        phase = now % 4.2
        closed = math.sin(math.pi*phase/.16) if phase < .16 else 0
        talk = .5+.35*math.sin(now*19)*math.sin(now*7.3) if speaking else 0
        self.update(px, py, caption, flip, (gaze,talk,closed) if animate else None)

    def update(self, x, y, caption, caption_left=False, animation=None):
        if not self.hwnd:
            return
        self.x, self.y = int(x), int(y)
        changed = caption != self.caption or caption_left != self.caption_left
        if changed or animation != self.animation_state:
            if changed:
                self.background = render_frame(Image.new("RGBA", (84,76)), caption, caption_left)
            frame = self.background.copy()
            face = animated_character(*animation) if animation is not None else self.small_art
            frame.alpha_composite(face, (274 if caption_left else 2,4))
            data = premultiplied_bgra(frame)
            ctypes.memmove(self.pixels, data, len(data))
            visible_size = (self.width, self.height) if caption else (88, 80)
            point, source, size = W.POINT(self.x, self.y), W.POINT(0, 0), W.SIZE(*visible_size)
            blend = _Blend(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
            if not self.user.UpdateLayeredWindow(self.hwnd, None, ctypes.byref(point), ctypes.byref(size),
                                                 self.dc, ctypes.byref(source), 0, ctypes.byref(blend), 2):
                raise ctypes.WinError(ctypes.get_last_error())
            self.caption = caption
            self.caption_left = caption_left
            self.animation_state = animation
        else:
            # NOACTIVATE | NOSIZE; preserve click-through while following the pointer.
            self.user.SetWindowPos(self.hwnd, W.HWND(-1), self.x, self.y, 0, 0, 0x11)

    def show(self):
        if self.hwnd:
            self.user.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE
            self.visible = True

    def hide(self):
        if self.hwnd:
            self.user.ShowWindow(self.hwnd, 0)
            self.visible = False

    def close(self):
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self.previous and self.dc:
            self.gdi.SelectObject(self.dc, self.previous)
            self.previous = None
        if self.bitmap:
            self.gdi.DeleteObject(self.bitmap)
            self.bitmap = None
        if self.dc:
            self.gdi.DeleteDC(self.dc)
            self.dc = None
        self.visible = False

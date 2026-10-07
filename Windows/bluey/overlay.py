"""Per-pixel-alpha Windows companion; all methods run on the Tk UI thread."""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def premultiplied_bgra(image):
    """UpdateLayeredWindow requires premultiplied, top-down BGRA pixels."""
    data = bytearray(image.convert("RGBA").tobytes())
    for i in range(0, len(data), 4):
        r, g, b, a = data[i:i+4]
        data[i:i+4] = bytes(((b*a+127)//255, (g*a+127)//255, (r*a+127)//255, a))
    return bytes(data)


def render_frame(art, caption):
    image = Image.new("RGBA", (360, 160))
    image.alpha_composite(art.resize((84, 76), Image.Resampling.LANCZOS), (2, 4))
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
        draw.rounded_rectangle((92, 8, 358, 152), radius=10, fill="#eef0ff")
        draw.multiline_text((99, 14), "\n".join(lines), font=font, fill="#17151f", spacing=3)
    return image


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("size", W.DWORD), ("width", W.LONG), ("height", W.LONG),
                ("planes", W.WORD), ("bits", W.WORD), ("compression", W.DWORD),
                ("image_size", W.DWORD), ("xppm", W.LONG), ("yppm", W.LONG),
                ("used", W.DWORD), ("important", W.DWORD)]


class _Blend(ctypes.Structure):
    _fields_ = [("op", W.BYTE), ("flags", W.BYTE), ("alpha", W.BYTE), ("format", W.BYTE)]


class Overlay:
    width, height = 360, 160

    def __init__(self, art):
        self.art = art.convert("RGBA")
        self.caption = None
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

    def update(self, x, y, caption):
        if not self.hwnd:
            return
        self.x, self.y = int(x), int(y)
        if caption != self.caption:
            data = premultiplied_bgra(render_frame(self.art, caption))
            ctypes.memmove(self.pixels, data, len(data))
            point, source, size = W.POINT(self.x, self.y), W.POINT(0, 0), W.SIZE(self.width, self.height)
            blend = _Blend(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
            if not self.user.UpdateLayeredWindow(self.hwnd, None, ctypes.byref(point), ctypes.byref(size),
                                                 self.dc, ctypes.byref(source), 0, ctypes.byref(blend), 2):
                raise ctypes.WinError(ctypes.get_last_error())
            self.caption = caption
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

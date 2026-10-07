"""Unicode keyboard input without clipboard access or keyboard-layout mapping."""
import ctypes
import sys
import unicodedata

DWORD, WORD, LONG = ctypes.c_uint32, ctypes.c_uint16, ctypes.c_int32
ULONG_PTR = ctypes.c_size_t


class TextInputError(ValueError):
    """Fixed user-facing native input failure, safe to return through the host."""


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD), ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", DWORD), ("data", _INPUTUNION)]


def normalize_text(text):
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError("Use text of at most 2000 characters.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(char != "\n" and unicodedata.category(char) in ("Cc", "Cs") for char in text):
        raise ValueError("Text may include Unicode and newlines, but not tabs or control characters.")
    return text


def character_events(character):
    if len(character) != 1 or normalize_text(character) != character:
        raise ValueError("Expected one normalized Unicode character.")
    if character == "\n":
        codes = [(0x0D, 0, 0)]  # VK_RETURN; no modifier or shortcut events.
    else:
        data = character.encode("utf-16-le")
        codes = [(0, int.from_bytes(data[i:i+2], "little"), 4) for i in range(0,len(data),2)]
    values = []
    for vk, scan, flags in codes:
        for up in (0, 2):
            event = INPUT()
            event.type = 1
            event.ki = KEYBDINPUT(vk, scan, flags | up, 0, 0)
            values.append(event)
    return (INPUT * len(values))(*values)


class UnicodeTextWriter:
    def __init__(self, send_input=None, key_state=None):
        if send_input is None:
            if sys.platform != "win32":
                raise RuntimeError("Native text input requires Windows.")
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
            user.SendInput.restype = ctypes.c_uint
            user.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user.GetAsyncKeyState.restype = ctypes.c_int16
            send_input, key_state = user.SendInput, user.GetAsyncKeyState
        self.send_input = send_input
        self.key_state = key_state or (lambda _: 0)

    def __call__(self, character):
        events = character_events(character)
        if any(self.key_state(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
            raise TextInputError("Release Shift, Ctrl, Alt and Windows keys before typing.")
        sent = self.send_input(len(events), events, ctypes.sizeof(INPUT))
        if sent != len(events):
            # If Windows accepted a key-down only, release that same key; never
            # retry characters automatically because that could duplicate text.
            if 0 < sent < len(events) and sent % 2:
                release = (INPUT * 1)(events[sent])
                self.send_input(1, release, ctypes.sizeof(INPUT))
            raise TextInputError("Windows did not accept all text input. Focus a normal non-administrator text field and retry only the missing text.")

"""Constrained PyAutoGUI adapter. Confirmation and cancellation are enforced by the UI."""
import math
import os
import subprocess
import threading
import time
import webbrowser
from urllib.parse import urlparse

ACTION_TOOLS = [
    {"type": "function", "name": name, "description": description,
     "parameters": {"type": "object", "properties": properties,
                    "required": list(properties), "additionalProperties": False}}
    for name, description, properties in [
        ("click", "Click a primary-display location. Requires local confirmation.",
         {"x": {"type": "number"}, "y": {"type": "number"}}),
        ("type_text", "Type ASCII text into the focused non-password field. Requires local confirmation.",
         {"text": {"type": "string"}}),
        ("press_keys", "Press a shortcut, e.g. ctrl+c. Requires local confirmation.",
         {"keys": {"type": "string"}}),
        ("scroll", "Scroll up/down/left/right by pixels. Requires local confirmation.",
         {"direction": {"type": "string", "enum": ["up", "down", "left", "right"]}, "amount": {"type": "number"}}),
        ("drag", "Drag between primary-display grid locations (0–1000). Requires local confirmation.",
         {"from_x": {"type": "number"}, "from_y": {"type": "number"},
          "to_x": {"type": "number"}, "to_y": {"type": "number"}}),
        ("open_app", "Open an installed Windows app from the allowlist: notepad, calculator, paint.",
         {"name": {"type": "string", "enum": ["notepad", "calculator", "paint"]}}),
        ("open_url", "Open an HTTP(S) URL in the default browser. Requires local confirmation.",
         {"url": {"type": "string"}}),
    ]
]
ACTION_NAMES = {tool["name"] for tool in ACTION_TOOLS}


def number(args, name, maximum=1000):
    value = args.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be a number between 0 and {maximum}")
    return value


def shortcut(value):
    if not isinstance(value, str):
        raise ValueError("keys must be a shortcut string")
    keys = value.lower().replace("command", "ctrl").replace("cmd", "ctrl").replace("option", "alt").split("+")
    keys = [key.strip() for key in keys]
    allowed = {"ctrl", "alt", "shift", "enter", "tab", "esc", "space", "backspace", "delete",
               "up", "down", "left", "right", "home", "end", "pageup", "pagedown"} | set("abcdefghijklmnopqrstuvwxyz0123456789")
    if not keys or len(keys) > 4 or any(key not in allowed for key in keys):
        raise ValueError("Unsupported shortcut (Windows/system keys are unavailable)")
    if set(keys) in ({"ctrl", "alt", "delete"}, {"alt", "tab"}, {"ctrl", "alt", "s"}, {"ctrl", "shift", "esc"}):
        raise ValueError("System and stop shortcuts are refused")
    return keys


class ComputerControl:
    def __init__(self, gui, password_check, confirm, enabled, cancelled=None):
        self.gui, self.password_check, self.confirm, self.enabled = gui, password_check, confirm, enabled
        self.cancelled = cancelled or (lambda: False)
        self.lock = threading.Lock()
        gui.FAILSAFE = True
        gui.PAUSE = 0.15

    def run(self, name, args):
        with self.lock:
            if not self.enabled() or self.cancelled():
                return "Computer control is off. Enable it in the desktop app."
            # Validate everything before showing a prompt or doing anything.
            width, height = self.gui.size()
            def point(x, y):
                return min(width-1, round(number(args, x) * width / 1000)), min(height-1, round(number(args, y) * height / 1000))
            if name == "click":
                target = point("x", "y")
            elif name == "drag":
                origin, target = point("from_x", "from_y"), point("to_x", "to_y")
            elif name == "type_text":
                text = args.get("text")
                if not isinstance(text, str) or not text.isascii() or len(text) > 2000 or any(ord(c) < 32 for c in text):
                    raise ValueError("Use printable ASCII text of at most 2000 characters")
            elif name == "press_keys":
                keys = shortcut(args.get("keys"))
            elif name == "scroll":
                direction = args.get("direction")
                if direction not in ("up", "down", "left", "right"):
                    raise ValueError("Unsupported scroll direction")
                clicks = max(1, round(number(args, "amount", 2000) / 100))
            elif name == "open_url":
                url = args.get("url")
                if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
                    raise ValueError("Invalid URL")
                parsed = urlparse(url)
                if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError("Only HTTP(S) URLs without embedded credentials are allowed")
            elif name == "open_app":
                app = {"notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe"}.get(args.get("name"))
                if not app:
                    raise ValueError("App is not on the allowlist")
            else:
                raise ValueError("Unsupported action")
            if not self.confirm(name, args):
                return "The user declined or cancelled this action."
            if not self.enabled() or self.cancelled():
                return "Computer control stopped."
            if name in ("type_text", "press_keys"):
                # Unknown focus or UI Automation failure is a refusal, not permission to type.
                if self.password_check() is not False:
                    return "Cannot verify a non-password field. Ask the user to enter this themselves."
            previous = self.gui.position()
            try:
                if name == "click": self.gui.click(*target)
                elif name == "drag":
                    self.gui.moveTo(*origin)
                    self.gui.dragTo(*target, duration=0.5)
                elif name == "type_text":
                    for character in text:
                        if self.cancelled() or not self.enabled():
                            return "Computer control stopped during typing."
                        self.gui.write(character, _pause=False)
                        time.sleep(0.005)
                elif name == "press_keys": self.gui.hotkey(*keys)
                elif name == "scroll":
                    if direction in ("left", "right"): self.gui.hscroll(clicks if direction == "right" else -clicks)
                    else: self.gui.scroll(clicks if direction == "up" else -clicks)
                elif name == "open_url":
                    if not webbrowser.open(url):
                        return "The default browser could not open this URL."
                elif name == "open_app": subprocess.Popen([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", app)])
            finally:
                # Do not move away from a failsafe corner or resume after a stop.
                if not self.cancelled() and tuple(self.gui.position()) not in self.gui.FAILSAFE_POINTS:
                    self.gui.moveTo(*previous)
            return "Action completed. Call look_at_screen to verify the result before the next action."

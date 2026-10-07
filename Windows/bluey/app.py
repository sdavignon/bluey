"""Windows GUI. Run from Windows/: python -m bluey.app."""
import ctypes
from ctypes import wintypes
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from .host import Host, mint_token


def main():
    if sys.platform != "win32":
        raise SystemExit("The desktop UI requires Windows 10/11. Protocol tests run on Linux.")
    import pyautogui
    from .control import ComputerControl
    from PIL import ImageGrab
    import keyring
    from zeroconf import ServiceInfo, Zeroconf

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetProcessDPIAware()
    root = tk.Tk()
    root.title("Bluey")
    root.geometry("460x480")
    root.configure(bg="#1e1b29")
    events = queue.Queue()
    enabled = threading.Event()
    stopped = threading.Event()
    pending_confirmation = None
    point = None
    caption = ""
    running = False
    zeroconf = info = host = None
    address = tk.StringVar(value="")
    status = tk.StringVar(value="Start pairing on a trusted private Wi-Fi network.")

    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="#ff00ff")
    overlay.attributes("-transparentcolor", "#ff00ff")
    canvas = tk.Canvas(overlay, width=360, height=160, bg="#ff00ff", highlightthickness=0)
    canvas.pack()
    canvas.create_oval(12, 10, 68, 66, fill="#6c86f5", outline="#a9bcff", width=3)
    canvas.create_oval(24, 26, 34, 40, fill="white", outline="")
    canvas.create_oval(45, 26, 55, 40, fill="white", outline="")
    canvas.create_text(40, 50, text="⌣", fill="#1c1f66", font=("Segoe UI", 16))
    bubble = canvas.create_text(82, 14, anchor="nw", width=265, text="", fill="#17151f",
                                font=("Segoe UI", 11))
    background = canvas.create_rectangle(77, 8, 354, 152, fill="#eef0ff", outline="")
    canvas.tag_lower(background)
    overlay.withdraw()

    def cursor():
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pos = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pos))
        return pos.x, pos.y

    def screen():
        return ImageGrab.grab(all_screens=False), cursor()

    def key():
        return keyring.get_password("Bluey", "openai")

    def set_key():
        value = simpledialog.askstring("OpenAI key", "Stored in Windows Credential Manager.", show="*", parent=root)
        if value and value.strip():
            try:
                keyring.set_password("Bluey", "openai", value.strip())
                status.set("Key saved in Windows Credential Manager.")
            except Exception:
                messagebox.showerror("Key storage", "Windows Credential Manager could not save the key.")

    def password_check():
        try:
            import comtypes
            from pywinauto.uia_defines import IUIA
            comtypes.CoInitialize()
            try:
                focused = IUIA().iuia.GetFocusedElement()
                return bool(focused.CurrentIsPassword) if focused else None
            finally:
                comtypes.CoUninitialize()
        except Exception:
            return None

    def confirm(name, args):
        done = threading.Event()
        result = [False]
        foreground = ctypes.windll.user32.GetForegroundWindow()
        events.put(("confirm", (name, args, done, result, foreground)))
        # The prompt has a deadline and stop/unpair cancels a waiting action.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and enabled.is_set() and not stopped.is_set():
            if done.wait(.1):
                return result[0]
        done.set()
        return False

    control = ComputerControl(pyautogui, password_check, confirm, enabled.is_set, stopped.is_set)

    def run_action(name, args):
        try:
            return control.run(name, args)
        except pyautogui.FailSafeException:
            enabled.clear()
            stopped.set()
            events.put(("stopped", "Computer control stopped at a failsafe corner."))
            return "Computer control stopped at a failsafe corner."

    def toggle_control():
        if control_flag.get():
            stopped.clear()
            enabled.set()
            status.set("Control enabled. Every action requires confirmation. Restart voice to load tools.")
        else:
            enabled.clear()
            stopped.set()
            status.set("Computer control stopped.")

    def start():
        nonlocal host, zeroconf, info, running
        if running:
            return
        if not messagebox.askokcancel("Local network pairing",
                "Bluey uses unencrypted, unauthenticated local-network pairing, like the Mac app. "
                "Anyone on this network can request screen images and short-lived AI tokens. "
                "Start only on a trusted private network. Allow Python through Windows Firewall "
                "for Private networks only."):
            return
        try:
            # Enumerate usable IPv4 interfaces; do not rely on external Internet connectivity.
            addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None,
                                socket.AF_INET, socket.SOCK_STREAM) if not entry[4][0].startswith("127.")})
            if not addresses:
                raise RuntimeError("No LAN IPv4 address found")
            host = Host(screen, lambda kind, value: events.put((kind, value)), key,
                        token_factory=lambda value: mint_token(value, enabled.is_set()), action=run_action)
            port = host.start()
            zeroconf = Zeroconf()
            info = ServiceInfo("_googly._tcp.local.", socket.gethostname() + "._googly._tcp.local.",
                               addresses=[socket.inet_aton(a) for a in addresses], port=port,
                               properties={}, server=socket.gethostname() + ".local.")
            zeroconf.register_service(info, allow_name_change=True)
            running = True
            address.set(f"{', '.join(addresses)} : {port}")
            status.set("Pairing started. Choose this desktop on your phone.")
            overlay.deiconify()
            # Make the overlay click-through so it never intercepts the user's pointer.
            root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(overlay.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x20 | 0x80000 | 0x08000000)
        except Exception as error:
            stop()
            status.set(f"Pairing failed ({type(error).__name__}). Check your network.")

    def stop():
        nonlocal running, host, zeroconf, info, caption, point
        running = False
        enabled.clear()
        stopped.set()
        control_flag.set(False)
        if host:
            host.close()
            host = None
        if zeroconf:
            if info:
                zeroconf.unregister_service(info)
            zeroconf.close()
            zeroconf = info = None
        caption, point = "", None
        overlay.withdraw()
        status.set("Pairing stopped.")
        address.set("")

    def command(name):
        if host:
            host.broadcast({"command": name})

    def tick():
        nonlocal point, caption, pending_confirmation
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "confirm":
                    name, args, done, result, foreground = value
                    if done.is_set() or not enabled.is_set() or stopped.is_set() or pending_confirmation:
                        done.set()
                        continue
                    dialog = tk.Toplevel(root)
                    pending_confirmation = (dialog, done)
                    dialog.title("Bluey action confirmation")
                    dialog.attributes("-topmost", True)
                    tk.Label(dialog, text=f"Allow {name}?\n{str(args)[:2100]}", wraplength=450).pack(padx=20, pady=20)
                    def finish(allow=False, window=dialog, completion=done, answer=result, target=foreground):
                        nonlocal pending_confirmation
                        if not completion.is_set():
                            if allow and enabled.is_set() and not stopped.is_set():
                                ctypes.windll.user32.SetForegroundWindow(target)
                                answer[0] = ctypes.windll.user32.GetForegroundWindow() == target
                            completion.set()
                        window.destroy()
                        pending_confirmation = None
                    tk.Button(dialog, text="Allow", command=lambda fn=finish: fn(True)).pack(side="left", padx=20, pady=10)
                    tk.Button(dialog, text="Decline", command=finish).pack(side="right", padx=20, pady=10)
                    dialog.protocol("WM_DELETE_WINDOW", finish)
                elif kind == "stopped":
                    control_flag.set(False)
                    status.set(value)
                elif kind == "point":
                    point = value
                elif kind == "follow":
                    point = None
                elif kind in ("caption", "captionDone"):
                    caption = value
                elif kind == "phone":
                    status.set("Connected: " + value)
                elif kind == "error":
                    status.set(value)
                elif kind == "disconnect" and host and not host.clients:
                    status.set("Waiting for a phone.")
                    caption, point = "", None
        except queue.Empty:
            pass
        if all(ctypes.windll.user32.GetAsyncKeyState(code) & 0x8000 for code in (0x11, 0x12, 0x53)):
            enabled.clear()
            stopped.set()
            control_flag.set(False)
            status.set("Computer control stopped (Ctrl+Alt+S).")
        if pending_confirmation and (pending_confirmation[1].is_set() or stopped.is_set()):
            dialog, done = pending_confirmation
            done.set()
            dialog.destroy()
            pending_confirmation = None
        if running and host:
            width, height = root.winfo_screenwidth(), root.winfo_screenheight()
            mouse = cursor()
            x, y = (point[0] * width / 1000, point[1] * height / 1000) if point else mouse
            overlay.geometry(f"360x160+{max(0, min(width-360, int(x)+12))}+{max(0, min(height-160, int(y)+12))}")
            canvas.itemconfigure(bubble, text=caption[:500])
            canvas.itemconfigure(background, state="normal" if caption else "hidden")
            host.broadcast({"face": {"gazeX": max(-1, min(1, mouse[0]*2/width-1)),
                                     "gazeY": max(-1, min(1, mouse[1]*2/height-1)),
                                     "mood": "pointing" if point else "listening", "talk": 0}})
        root.after(50, tick)

    tk.Label(root, text="Bluey for Windows", bg="#1e1b29", fg="#a9bcff", font=("Segoe UI", 22)).pack(pady=15)
    tk.Label(root, textvariable=status, bg="#1e1b29", fg="white", wraplength=390).pack(pady=10)
    tk.Label(root, textvariable=address, bg="#1e1b29", fg="#a9bcff", wraplength=420).pack(pady=3)
    for label, callback in [("OpenAI key…", set_key), ("Start pairing", start), ("Stop pairing", stop),
                            ("Wake phone", lambda: command("wake")), ("Sleep phone", lambda: command("sleep"))]:
        tk.Button(root, text=label, command=callback).pack(fill="x", padx=60, pady=2)
    control_flag = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="Let Bluey use the computer", variable=control_flag,
                   command=toggle_control, bg="#1e1b29", fg="white", selectcolor="#2b2f8f").pack(pady=8)
    tk.Label(root, text="Emergency stop: Ctrl+Alt+S or move mouse to a screen corner.",
             bg="#1e1b29", fg="#b9b2cc", wraplength=420).pack()
    root.protocol("WM_DELETE_WINDOW", lambda: (stop(), root.destroy()))
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()

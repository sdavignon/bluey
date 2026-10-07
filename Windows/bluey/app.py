"""Windows GUI. Run from Windows/: python -m bluey.app."""
import ctypes
from pathlib import Path
from ctypes import wintypes
import queue
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from .host import Host, mint_token, session_config, phone_credentials_only
from .network import pairing_addresses


def main():
    customer = "--customer" in sys.argv[1:]
    if sys.platform != "win32":
        raise SystemExit("The desktop UI requires Windows 10/11. Protocol tests run on Linux.")
    import pyautogui
    from .control import ComputerControl
    from .text_input import UnicodeTextWriter
    from .tray import Tray, WindowLifecycle
    from .overlay import Overlay
    from PIL import Image, ImageGrab, ImageTk
    import keyring
    from zeroconf import ServiceInfo, Zeroconf

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetProcessDPIAware()
    root = tk.Tk()
    root.title("Bluey")
    root.geometry("540x730")
    root.minsize(540, 730)
    root.configure(bg="#0d0e18")
    root.option_add("*Font", ("Segoe UI", 10))
    assets = Path(__file__).parent / "assets"
    root.iconbitmap(str(assets / "bluey.ico"))
    art = Image.open(assets / "bluey.png")
    portrait = ImageTk.PhotoImage(art.resize((116, 104), Image.Resampling.LANCZOS))
    events = queue.Queue()
    enabled = threading.Event()
    stopped = threading.Event()
    pending_confirmation = None
    pending_tracker_confirmation = None
    point = None
    caption = ""
    phone_speaking = False
    speaking_updated = 0.0
    running = False
    pairing_generation = 0
    zeroconf = info = host = None
    address = tk.StringVar(value="")
    status = tk.StringVar(value="Start pairing on a trusted private Wi-Fi network.")

    overlay = Overlay(art)

    def cursor():
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pos = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pos))
        return pos.x, pos.y

    def screen():
        return ImageGrab.grab(all_screens=False), cursor()

    def key():
        if customer:
            return None
        return keyring.get_password("Bluey", "openai")

    key_status = tk.StringVar()
    def refresh_key_status():
        if customer:
            key_status.set("Customer PC\nCredentials stay on your phone")
            return
        try:
            key_status.set("OpenAI key saved · reused every run" if key() else "No OpenAI key saved yet")
        except Exception:
            key_status.set("Credential Manager unavailable")
    refresh_key_status()

    def set_key():
        if customer:
            return
        value = simpledialog.askstring("OpenAI key", "Stored in Windows Credential Manager.", show="*", parent=root)
        if value and value.strip():
            try:
                keyring.set_password("Bluey", "openai", value.strip())
                if key() != value.strip():
                    raise RuntimeError("Credential readback failed")
                refresh_key_status()
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
        request_generation = pairing_generation
        foreground = ctypes.windll.user32.GetForegroundWindow()
        events.put(("confirm", (name, args, done, result, foreground, request_generation)))
        # The prompt has a deadline and stop/unpair cancels a waiting action.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and enabled.is_set() and not stopped.is_set() and request_generation == pairing_generation:
            if done.wait(.1):
                return result[0] and request_generation == pairing_generation
        done.set()
        return False

    control = ComputerControl(pyautogui, password_check, confirm, enabled.is_set, stopped.is_set,
                              text_writer=UnicodeTextWriter())

    def run_action(name, args):
        try:
            outcome = control.run(name, args)
        except pyautogui.FailSafeException:
            enabled.clear()
            stopped.set()
            events.put(("stopped", "Computer control stopped at a failsafe corner."))
            return "Computer control stopped at a failsafe corner."
        except ValueError as error:
            # Control validation messages are fixed local text, never provider bodies.
            outcome = "Computer action rejected: " + str(error)
        except OSError:
            outcome = "Windows rejected the input. Check whether the target window runs as administrator or is a protected dialog."
        except Exception as error:
            outcome = "Computer action failed (" + type(error).__name__ + "). Check the target window and try again."
        events.put(("control_result", outcome))
        return outcome

    def run_tracker(name, args):
        if customer:
            return "Project Manager credentials and requests are handled on the phone."
        from . import project_tracker
        if not running or not project_tracker.is_connected():
            return "Project Manager is not connected."
        request_generation = pairing_generation
        done, result = threading.Event(), [False]
        events.put(("tracker_confirm", (name, args, done, result, request_generation)))
        deadline = time.monotonic() + 30
        while running and request_generation == pairing_generation and time.monotonic() < deadline:
            if done.wait(.1):
                if result[0] and running and request_generation == pairing_generation and project_tracker.is_connected():
                    return project_tracker.dispatch(name, args)
                return "Project Manager request declined or cancelled."
        done.set()
        return "Project Manager request cancelled or timed out."

    def tracker_connected():
        if customer:
            return False
        from . import project_tracker
        return project_tracker.is_connected()

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
            addresses = pairing_addresses()
            if not addresses:
                raise RuntimeError("No LAN IPv4 address found")
            host = Host(screen, lambda kind, value: events.put((kind, value)), key,
                        token_factory=phone_credentials_only if customer else lambda value: mint_token(value, enabled.is_set(), tracker_enabled=tracker_connected()),
                        action=run_action, tracker=None if customer else run_tracker,
                        config_factory=lambda: session_config(enabled.is_set(), False))
            port = host.start(port=8765)
            zeroconf = Zeroconf()
            info = ServiceInfo("_googly._tcp.local.", socket.gethostname() + "._googly._tcp.local.",
                               addresses=[socket.inet_aton(a) for a in addresses], port=port,
                               properties={}, server=socket.gethostname() + ".local.")
            zeroconf.register_service(info, allow_name_change=True)
            running = True
            address.set(f"{', '.join(addresses)} : {port}")
            status.set("Pairing started. Choose this desktop on your phone.")
            overlay.show()
        except Exception as error:
            stop()
            status.set("Port 8765 is busy. Quit the other Bluey instance and try again." if isinstance(error, OSError) and getattr(error, "winerror", None) == 10048 else f"Pairing failed ({type(error).__name__}). Check your network.")

    def stop():
        nonlocal running, host, zeroconf, info, caption, point, pairing_generation, phone_speaking
        running = False
        phone_speaking = False
        pairing_generation += 1
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
        overlay.hide()
        status.set("Pairing stopped.")
        address.set("")

    def command(name):
        if host:
            host.broadcast({"command": name})

    def tick():
        nonlocal point, caption, pending_confirmation, pending_tracker_confirmation, phone_speaking, speaking_updated, pairing_generation
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "ui":
                    value()
                    if lifecycle.quitting:
                        return
                    tray.refresh()
                elif kind == "tracker_confirm":
                    name, args, done, result, request_generation = value
                    if done.is_set() or not running or request_generation != pairing_generation or pending_tracker_confirmation:
                        done.set()
                        continue
                    dialog = tk.Toplevel(root)
                    pending_tracker_confirmation = (dialog, done)
                    dialog.title("Bluey Project Manager approval")
                    dialog.attributes("-topmost", True)
                    tk.Label(dialog, text=f"Allow Project Manager request?\n{name}\n{str(args)[:2100]}", wraplength=450).pack(padx=20, pady=16)
                    tk.Label(dialog, text="This can read or update your connected Google Sheet.", wraplength=450).pack(padx=20)
                    def finish_tracker(allow=False, window=dialog, completion=done, answer=result):
                        nonlocal pending_tracker_confirmation
                        if not completion.is_set():
                            answer[0] = bool(allow and running)
                            completion.set()
                        window.destroy()
                        pending_tracker_confirmation = None
                    tk.Button(dialog, text="Allow", command=lambda fn=finish_tracker: fn(True)).pack(side="left", padx=20, pady=12)
                    tk.Button(dialog, text="Decline", command=finish_tracker).pack(side="right", padx=20, pady=12)
                    dialog.protocol("WM_DELETE_WINDOW", finish_tracker)
                elif kind == "confirm":
                    name, args, done, result, foreground, request_generation = value
                    if done.is_set() or not enabled.is_set() or stopped.is_set() or pending_confirmation or request_generation != pairing_generation:
                        done.set()
                        continue
                    dialog = tk.Toplevel(root)
                    pending_confirmation = (dialog, done)
                    dialog.title("Bluey action confirmation")
                    dialog.attributes("-topmost", True)
                    tk.Label(dialog, text=f"Allow {name}?\n{str(args)[:2100]}", wraplength=450).pack(padx=20, pady=20)
                    def finish(allow=False, window=dialog, completion=done, answer=result, target=foreground, request_id=request_generation):
                        nonlocal pending_confirmation
                        window.destroy()
                        pending_confirmation = None
                        if completion.is_set():
                            return
                        if not allow or not enabled.is_set() or stopped.is_set():
                            completion.set()
                            return
                        # Destroying the prompt may steal focus back to its Tk parent.
                        # Restore only after Tk has processed that transition, then verify.
                        def restore():
                            if completion.is_set():
                                return
                            if not enabled.is_set() or stopped.is_set() or request_id != pairing_generation or not target or not user32.IsWindow(target):
                                status.set("Computer control stopped or target window closed. Focus the app and ask again.")
                                completion.set()
                                return
                            ctypes.windll.user32.SetForegroundWindow(target)
                            def settled():
                                if not completion.is_set():
                                    answer[0] = (enabled.is_set() and not stopped.is_set() and request_id == pairing_generation and user32.IsWindow(target)
                                                 and ctypes.windll.user32.GetForegroundWindow() == target)
                                    if not answer[0]:
                                        status.set("Could not restore the target window. Focus it and ask again.")
                                    completion.set()
                            root.after(80, settled)
                        root.after(80, restore)
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
                elif kind == "speaking":
                    phone_speaking = value is True
                    speaking_updated = time.monotonic()
                elif kind == "error":
                    status.set(value)
                elif kind == "control_result":
                    status.set(value)
                elif kind == "disconnect" and host and not host.clients:
                    phone_speaking = False
                    pairing_generation += 1
                    enabled.clear()
                    stopped.set()
                    control_flag.set(False)
                    status.set("Phone disconnected. Computer control disabled; reconnect and enable it again.")
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
        if pending_tracker_confirmation and (pending_tracker_confirmation[1].is_set() or not running):
            dialog, done = pending_tracker_confirmation
            done.set()
            dialog.destroy()
            pending_tracker_confirmation = None
        if running and host:
            width, height = root.winfo_screenwidth(), root.winfo_screenheight()
            mouse = cursor()
            # Tool coordinates still target the primary display, including grid 1000.
            x, y = (min(width-1, point[0] * width / 1000), min(height-1, point[1] * height / 1000)) if point else mouse
            gx, gy = max(-1, min(1, mouse[0]*2/width-1)), max(-1, min(1, mouse[1]*2/height-1))
            overlay.follow(x, y, caption[:500], gaze=(gx,gy),
                           speaking=phone_speaking and time.monotonic()-speaking_updated < 3,
                           animate=animate_character.get())
            host.broadcast({"face": {"gazeX": gx,
                                     "gazeY": gy,
                                     "mood": "pointing" if point else "listening", "talk": 0}})
        root.after(50, tick)

    page = tk.Frame(root, bg="#0d0e18")
    page.pack(fill="both", expand=True, padx=28, pady=22)
    header = tk.Frame(page, bg="#0d0e18")
    header.pack(fill="x", pady=(0, 18))
    tk.Label(header, image=portrait, bg="#0d0e18").pack(side="left", padx=(0, 18))
    title = tk.Frame(header, bg="#0d0e18")
    title.pack(side="left")
    tk.Label(title, text="Bluey", bg="#0d0e18", fg="#e9edff", font=("Segoe UI", 30, "bold")).pack(anchor="w")
    tk.Label(title, text="Your phone companion, on Windows", bg="#0d0e18", fg="#a2abc9", font=("Segoe UI", 10)).pack(anchor="w")
    card = tk.Frame(page, bg="#191d32", padx=18, pady=14)
    card.pack(fill="x", pady=(0, 16))
    tk.Label(card, text="CONNECTION", bg="#191d32", fg="#a9bcff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
    tk.Label(card, textvariable=status, bg="#191d32", fg="#f1f3ff", wraplength=402, justify="left", height=3).pack(anchor="w", fill="x")
    tk.Label(card, textvariable=address, bg="#191d32", fg="#a9bcff", wraplength=402, justify="left").pack(anchor="w")

    def button(parent, label, callback, primary=False):
        return tk.Button(parent, text=label, command=callback, bg="#a9bcff" if primary else "#252b46",
                         fg="#11172d" if primary else "#e9edff", activebackground="#c0ceff" if primary else "#343e61",
                         activeforeground="#11172d" if primary else "white", relief="flat", bd=0,
                         padx=14, pady=10, cursor="hand2", highlightthickness=1, highlightbackground="#343e61")

    pairing_row = tk.Frame(page, bg="#0d0e18")
    pairing_row.pack(fill="x", pady=(0, 10))
    button(pairing_row, "Start pairing", start, True).pack(side="left", fill="x", expand=True, padx=(0, 6))
    button(pairing_row, "Stop pairing", stop).pack(side="left", fill="x", expand=True, padx=(6, 0))
    phone_row = tk.Frame(page, bg="#0d0e18")
    phone_row.pack(fill="x", pady=(0, 16))
    button(phone_row, "Wake phone", lambda: command("wake")).pack(side="left", fill="x", expand=True, padx=(0, 6))
    button(phone_row, "Sleep phone", lambda: command("sleep")).pack(side="left", fill="x", expand=True, padx=(6, 0))
    key_row = tk.Frame(page, bg="#0d0e18")
    key_row.pack(fill="x", pady=(0, 16))
    key_button = button(key_row, "Credentials on phone" if customer else "OpenAI key…", set_key)
    if customer:
        key_button.configure(state="disabled")
    key_button.pack(side="left", padx=(0, 12))
    tk.Label(key_row, textvariable=key_status, bg="#0d0e18", fg="#a2abc9", justify="left", font=("Segoe UI", 9)).pack(side="left")
    safety = tk.Frame(page, bg="#191d32", padx=14, pady=10)
    safety.pack(fill="x")
    control_flag = tk.BooleanVar(value=False)
    tk.Checkbutton(safety, text="Let Bluey use the computer", variable=control_flag,
                   command=toggle_control, bg="#191d32", fg="#e9edff", activebackground="#191d32", activeforeground="white",
                   selectcolor="#2b2f8f").pack(anchor="w")
    tk.Label(safety, text="Every action needs your approval.", bg="#191d32", fg="#a2abc9", font=("Segoe UI", 9)).pack(anchor="w", padx=4)
    animate_character = tk.BooleanVar(value=True)
    tk.Checkbutton(safety, text="Animate character · eyes, blink and speech", variable=animate_character,
                   bg="#191d32", fg="#e9edff", activebackground="#191d32", activeforeground="white",
                   selectcolor="#2b2f8f").pack(anchor="w", pady=(6,0))
    tk.Label(page, text="Emergency stop  ·  Ctrl+Alt+S or move to a screen corner", bg="#0d0e18", fg="#a2abc9", font=("Segoe UI", 9)).pack(pady=(14, 0))

    def open_projects():
        try:
            if customer:
                import webbrowser
                from .project_tracker import DEFAULT_SHEET_URL
                webbrowser.open(DEFAULT_SHEET_URL)
                return
            from .project_tracker import open_project_manager
            open_project_manager()
        except Exception:
            lifecycle.show()
            messagebox.showerror("Project Manager", "Project Manager could not open. Check its configuration and try again.", parent=root)

    def tray_control():
        # Never touch Tk variables in pystray's worker thread.
        control_flag.set(not control_flag.get())
        toggle_control()

    def configure_sheets():
        if customer:
            # Opening the default sheet needs no local OAuth/settings access.
            open_projects()
            return
        lifecycle.show()
        try:
            from .project_tracker import configure
            configure(root)
        except Exception:
            messagebox.showerror("Google Sheets", "Google Sheets settings could not open. Please try again.", parent=root)

    def tray_start():
        lifecycle.show()
        start()

    def tray_failed():
        lifecycle.show()
        status.set("System tray unavailable. Keep this window open; closing it will quit Bluey.")

    tray = Tray(Image.open(assets / "bluey.ico"), lambda fn: events.put(("ui", fn)),
                {"show": lambda: lifecycle.show(), "projects": open_projects, "sheets": configure_sheets,
                 "start": tray_start, "stop": stop, "wake": lambda: command("wake"),
                 "sleep": lambda: command("sleep"), "control": tray_control,
                 "quit": lambda: lifecycle.quit()},
                pairing=lambda: running, control=enabled.is_set, failed=tray_failed)
    def cleanup():
        try:
            stop()
        finally:
            overlay.close()
    lifecycle = WindowLifecycle(root, tray, cleanup)
    footer = tk.Frame(page, bg="#0d0e18")
    footer.pack(fill="x", pady=(12, 0))
    button(footer, "Open Project Manager", open_projects).pack(side="left")
    button(footer, "Google Sheets…", configure_sheets).pack(side="left", padx=6)
    button(footer, "Quit Bluey", lifecycle.quit).pack(side="right")
    tk.Label(page, text="Close to keep Bluey in the system tray. Right-click its icon for controls.",
             bg="#0d0e18", fg="#a2abc9", wraplength=450, font=("Segoe UI", 9)).pack(pady=(8, 0))
    root.protocol("WM_DELETE_WINDOW", lifecycle.close)
    tray.start()
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()

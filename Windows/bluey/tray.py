"""Windows tray adapter. Callbacks only enqueue work for Tk's main thread."""
import threading


class Tray:
    def __init__(self, image, dispatch, actions, pairing, control, failed, backend=None):
        self.image, self.dispatch, self.actions = image, dispatch, actions
        self.pairing, self.control, self.failed = pairing, control, failed
        self.backend = backend
        self.icon = None
        self.thread = None
        self.available = threading.Event()
        self.closed = threading.Event()

    def _action(self, name):
        def invoke(icon, item):
            self.dispatch(self.actions[name])
        return invoke

    def start(self):
        try:
            if self.backend is None:
                import pystray
                self.backend = pystray
            item, menu = self.backend.MenuItem, self.backend.Menu
            self.icon = self.backend.Icon("Bluey", self.image, "Bluey · phone companion", menu(
                item("Open settings", self._action("show"), default=True),
                item("Open Project Manager", self._action("projects")),
                item("Google Sheets…", self._action("sheets")),
                menu.SEPARATOR,
                item("Start pairing", self._action("start"), enabled=lambda _: not self.pairing()),
                item("Stop pairing", self._action("stop"), enabled=lambda _: self.pairing()),
                item("Wake phone", self._action("wake"), enabled=lambda _: self.pairing()),
                item("Sleep phone", self._action("sleep"), enabled=lambda _: self.pairing()),
                item("Computer control", self._action("control"), checked=lambda _: self.control()),
                menu.SEPARATOR,
                item("Quit Bluey", self._action("quit"))))
            self.thread = threading.Thread(target=self._run, name="Bluey tray", daemon=True)
            self.thread.start()
        except Exception:
            self._failed()

    def _ready(self, icon):
        try:
            if self.closed.is_set():
                icon.stop()
                return
            icon.visible = True
            self.available.set()
        except Exception:
            self._failed()
            icon.stop()

    def _run(self):
        try:
            self.icon.run(setup=self._ready)
        except Exception:
            pass
        finally:
            self.available.clear()
            if not self.closed.is_set():
                self._failed()

    def _failed(self):
        self.available.clear()
        if not self.closed.is_set():
            self.dispatch(self.failed)

    def refresh(self):
        if self.available.is_set():
            try:
                self.icon.update_menu()
            except Exception:
                self._failed()

    def stop(self):
        self.closed.set()
        self.available.clear()
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass


class WindowLifecycle:
    """UI-thread-only close behavior; a failed tray must never strand the app."""
    def __init__(self, window, tray, cleanup):
        self.window, self.tray, self.cleanup = window, tray, cleanup
        self.quitting = False

    def show(self):
        if not self.quitting:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def close(self):
        if self.tray.available.is_set():
            self.window.withdraw()
        else:
            self.quit()

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        try:
            self.cleanup()
        finally:
            self.tray.stop()
            self.window.destroy()

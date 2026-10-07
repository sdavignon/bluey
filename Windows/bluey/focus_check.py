"""Bounded, fail-closed password checks on one windowless COM MTA thread."""
import ctypes
import importlib
import queue
import sys
import threading


class _NativeProvider:
    def __init__(self):
        self.automation = None
        self.ole = ctypes.WinDLL("ole32")
        self.ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.ole.CoInitializeEx.restype = ctypes.c_int32
        self.ole.CoUninitialize.argtypes = []
        self.ole.CoUninitialize.restype = None
        result = self.ole.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
        if result < 0:
            raise OSError("MTA initialization failed")
        try:
            # comtypes initializes the first importing thread. Ensure that its
            # implicit initialization agrees with this thread's explicit MTA.
            missing = object()
            previous = getattr(sys, "coinit_flags", missing)
            first_import = "comtypes" not in sys.modules
            sys.coinit_flags = 0
            try:
                comtypes = importlib.import_module("comtypes")
            finally:
                if previous is missing:
                    del sys.coinit_flags
                else:
                    sys.coinit_flags = previous
            if first_import:
                self.ole.CoUninitialize()  # balance comtypes' implicit init
            client = importlib.import_module("comtypes.client")
            definitions = client.GetModule("UIAutomationCore.dll")
            self.automation = comtypes.CoCreateInstance(
                definitions.CUIAutomation._reg_clsid_,
                interface=definitions.IUIAutomation,
                clsctx=comtypes.CLSCTX_INPROC_SERVER)
        except Exception:
            self.ole.CoUninitialize()
            raise

    def __call__(self):
        focused = self.automation.GetFocusedElement()
        return bool(focused.CurrentIsPassword) if focused else None

    def close(self):
        # Drop apartment-bound interfaces before balancing this thread's COM init.
        self.automation = None
        self.ole.CoUninitialize()


class _Request:
    def __init__(self):
        self.done = threading.Event()
        self.result = None
        self.expired = False


class FocusChecker:
    def __init__(self, timeout=2.5, provider_factory=None):
        self.timeout = timeout
        self.factory = provider_factory or _NativeProvider
        self.status = "ready"
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=1)
        self._closed = False
        self._active = None
        self._thread = threading.Thread(target=self._worker, name="Bluey password check MTA", daemon=True)
        self._thread.start()

    def check(self):
        with self._lock:
            if self._closed:
                self.status = "closed"
                return None
            if self._active is not None:
                self.status = "busy"
                return None
            request = _Request()
            self._active = request
            self.status = "checking"
            self._queue.put_nowait(request)
        completed = request.done.wait(self.timeout)
        with self._lock:
            if self._closed:
                self.status = "closed"
                return None
            if not completed:
                request.expired = True
                self.status = "timeout"
                return None
            return request.result

    def _worker(self):
        provider = None
        try:
            while True:
                request = self._queue.get()
                with self._lock:
                    if self._closed or request is None:
                        break
                result = None
                try:
                    if provider is None:
                        provider = self.factory()
                    candidate = provider()
                    result = candidate if type(candidate) is bool else None
                except Exception:
                    pass  # Unknown focus is never permission to type.
                with self._lock:
                    if not self._closed and not request.expired:
                        request.result = result
                        self.status = "password" if result is True else "non-password" if result is False else "unavailable"
                    self._active = None
                    request.done.set()
                    if self._closed:
                        break
        finally:
            if provider is not None and hasattr(provider, "close"):
                try:
                    provider.close()
                except Exception:
                    pass

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self.status = "closed"
            if self._active:
                self._active.expired = True
                self._active.done.set()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

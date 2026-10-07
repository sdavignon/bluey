import threading
import time
import unittest
from bluey.focus_check import FocusChecker


class FocusCheckerTests(unittest.TestCase):
    def test_all_provider_lifecycle_calls_stay_on_one_worker(self):
        threads = []
        class Provider:
            def __init__(self): threads.append(threading.get_ident())
            def __call__(self): threads.append(threading.get_ident()); return False
            def close(self): threads.append(threading.get_ident())
        checker = FocusChecker(provider_factory=Provider)
        self.assertIs(checker.check(), False)
        self.assertIs(checker.check(), False)
        checker.close(); checker._thread.join(1)
        self.assertEqual(len(threads), 4)
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.get_ident())

    def test_timeout_busy_and_recovery_ignore_late_result(self):
        release, entered = threading.Event(), threading.Event()
        def provider(): entered.set(); release.wait(2); return False
        checker = FocusChecker(timeout=.03, provider_factory=lambda: provider)
        try:
            self.assertIsNone(checker.check())
            self.assertTrue(entered.is_set())
            self.assertEqual(checker.status, 'timeout')
            self.assertIsNone(checker.check())
            self.assertEqual(checker.status, 'busy')
            release.set()
            deadline = time.monotonic()+1
            while checker._active is not None and time.monotonic()<deadline: time.sleep(.005)
            self.assertEqual(checker.status, 'busy')  # late False never becomes permission
            self.assertIs(checker.check(), False)
        finally:
            release.set(); checker.close(); checker._thread.join(1)

    def test_exception_and_non_boolean_results_fail_closed(self):
        for factory in (lambda: lambda: 0, lambda: lambda: True, lambda: (_ for _ in ()).throw(RuntimeError('private'))):
            checker = FocusChecker(provider_factory=factory)
            try:
                self.assertIsNot(checker.check(), False)
            finally:
                checker.close(); checker._thread.join(1)

    def test_close_unblocks_waiter_and_never_accepts_late_check(self):
        release, entered = threading.Event(), threading.Event()
        def provider(): entered.set(); release.wait(2); return False
        checker = FocusChecker(timeout=2, provider_factory=lambda: provider)
        results = []
        waiter = threading.Thread(target=lambda: results.append(checker.check()))
        waiter.start(); self.assertTrue(entered.wait(1))
        checker.close(); waiter.join(.2)
        self.assertFalse(waiter.is_alive())
        self.assertEqual(results, [None])
        self.assertIsNone(checker.check())
        release.set(); checker._thread.join(1)
        self.assertEqual(checker.status, 'closed')

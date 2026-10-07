import threading
import unittest
from bluey.control import ComputerControl


class FakeInput:
    FAILSAFE_POINTS = [(0, 0)]
    def __init__(self): self.calls = []
    def size(self): return (1920, 1080)
    def position(self): return (500, 400)
    def click(self, *point): self.calls.append(('click', point))
    def moveTo(self, *point): self.calls.append(('move', point))


class BusyControlTests(unittest.TestCase):
    def test_concurrent_request_is_rejected_without_second_prompt_or_input(self):
        entered, release = threading.Event(), threading.Event()
        prompts, result = [], []
        def confirm(name, args):
            prompts.append(name)
            entered.set()
            release.wait(3)
            return False
        gui = FakeInput()
        control = ComputerControl(gui, lambda: False, confirm, lambda: True)
        thread = threading.Thread(target=lambda: result.append(control.run('click', {'x': 100, 'y': 200})), daemon=True)
        thread.start()
        try:
            self.assertTrue(entered.wait(1), 'First request must reach approval')
            busy_result = control.run('click', {'x': 900, 'y': 800})
            self.assertIn('still running', busy_result)
            self.assertEqual(prompts, ['click'])
            self.assertEqual(gui.calls, [])
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertIn('declined', result[0])
        # The rejected concurrent request must not execute later as queued work.
        self.assertEqual(gui.calls, [])
        self.assertEqual(prompts, ['click'])
        self.assertTrue(control.lock.acquire(blocking=False))
        control.lock.release()

    def test_validation_exception_releases_busy_lock(self):
        gui = FakeInput()
        control = ComputerControl(gui, lambda: False, lambda *args: False, lambda: True)
        with self.assertRaises(ValueError):
            control.run('click', {'x': -1, 'y': 0})
        self.assertIn('declined', control.run('click', {'x': 100, 'y': 200}))
        self.assertEqual(gui.calls, [])

if __name__ == '__main__':
    unittest.main()

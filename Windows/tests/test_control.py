import unittest
from bluey.control import ComputerControl, shortcut


class FakeMouse:
    FAILSAFE_POINTS = [(0, 0)]
    def __init__(self): self.calls = []
    def size(self): return (1920, 1080)
    def position(self): return (800, 400)
    def __getattr__(self, name):
        return lambda *args, **kwargs: self.calls.append((name, args, kwargs))


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.allowed, self.password, self.enabled, self.cancelled = True, False, True, False
        self.control = ComputerControl(self.mouse, lambda: self.password, lambda *args: self.allowed,
                                       lambda: self.enabled, lambda: self.cancelled)

    def test_click_maps_grid_and_restores_pointer(self):
        self.control.run('click', {'x': 500, 'y': 500})
        self.assertEqual(self.mouse.calls[0][:2], ('click', (960, 540)))
        self.assertEqual(self.mouse.calls[-1][:2], ('moveTo', (800, 400)))

    def test_disabled_declined_and_cancelled_never_act(self):
        self.enabled = False
        self.control.run('click', {'x': 500, 'y': 500})
        self.enabled, self.allowed = True, False
        self.control.run('click', {'x': 500, 'y': 500})
        self.allowed, self.cancelled = True, True
        self.control.run('click', {'x': 500, 'y': 500})
        self.assertEqual(self.mouse.calls, [])

    def test_password_and_unknown_focus_never_type(self):
        for password in (True, None):
            self.password = password
            self.control.run('type_text', {'text': 'secret'})
            self.control.run('press_keys', {'keys': 'ctrl+v'})
        self.assertEqual(self.mouse.calls, [])

    def test_invalid_input_and_url_schemes_never_act(self):
        for name, args in [('click', {'x': -1,'y': 0}), ('type_text', {'text': 'a\nb'}),
                           ('open_url', {'url': 'file:///etc/passwd'}), ('open_url', {'url': 'https://user:pass@example.com'}),
                           ('open_app', {'name': 'powershell'}), ('press_keys', {'keys': 'win+l'})]:
            with self.assertRaises(ValueError): self.control.run(name, args)
        self.assertEqual(self.mouse.calls, [])

    def test_stop_during_typing(self):
        def write(char, **kwargs):
            self.mouse.calls.append(('write', char))
            self.cancelled = True
        self.mouse.write = write
        self.assertIn('stopped during', self.control.run('type_text', {'text': 'abc'}))
        self.assertEqual(self.mouse.calls, [('write', 'a')])

    def test_system_shortcuts_refused(self):
        for value in ['ctrl+alt+delete', 'ctrl+shift+esc', 'alt+tab', 'ctrl+alt+s', 'win+l', 'alt+f4']:
            with self.assertRaises(ValueError): shortcut(value)
        self.assertEqual(shortcut('command+c'), ['ctrl', 'c'])

class SupportedActionTests(unittest.TestCase):
    def test_shortcut_scroll_drag_and_printable_text(self):
        mouse = FakeMouse()
        control = ComputerControl(mouse, lambda: False, lambda *args: True, lambda: True)
        control.run('press_keys', {'keys': 'ctrl+c'})
        control.run('scroll', {'direction': 'down', 'amount': 500})
        control.run('drag', {'from_x': 250, 'from_y': 250, 'to_x': 750, 'to_y': 750})
        control.run('type_text', {'text': 'Hi'})
        self.assertIn(('hotkey', ('ctrl', 'c'), {}), mouse.calls)
        self.assertIn(('scroll', (-5,), {}), mouse.calls)
        self.assertIn(('dragTo', (1440, 810), {'duration': .5}), mouse.calls)
        self.assertIn(('write', ('H',), {'_pause': False}), mouse.calls)
        self.assertIn(('write', ('i',), {'_pause': False}), mouse.calls)


if __name__ == '__main__': unittest.main()

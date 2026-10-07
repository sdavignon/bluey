import ctypes
import unittest
from bluey.text_input import INPUT, KEYBDINPUT, TextInputError, UnicodeTextWriter, character_events, normalize_text


class TextInputTests(unittest.TestCase):
    def test_struct_size_and_alignment_match_windows_abi(self):
        bits = ctypes.sizeof(ctypes.c_void_p)
        self.assertEqual(ctypes.sizeof(INPUT), 40 if bits == 8 else 28)
        self.assertEqual(INPUT.data.offset, 8 if bits == 8 else 4)
        self.assertEqual(ctypes.sizeof(KEYBDINPUT), 24 if bits == 8 else 16)

    def test_unicode_and_emoji_are_utf16_packets_not_shortcuts(self):
        events = character_events('🫐')
        self.assertEqual([(e.type,e.ki.wVk,e.ki.wScan,e.ki.dwFlags) for e in events],
                         [(1,0,0xD83E,4),(1,0,0xD83E,6),(1,0,0xDED0,4),(1,0,0xDED0,6)])
        self.assertEqual(character_events('é')[0].ki.wScan, 233)

    def test_crlf_and_cr_normalize_and_newline_is_enter_pair(self):
        self.assertEqual(normalize_text('a\r\nb\rc\n'), 'a\nb\nc\n')
        self.assertEqual([(e.ki.wVk,e.ki.wScan,e.ki.dwFlags) for e in character_events('\n')],
                         [(13,0,0),(13,0,2)])

    def test_controls_tabs_surrogates_and_oversized_input_rejected(self):
        for text in ('a\tb', '\x00', '\x1b', '\x7f', '\x85', '\ud800', 'x'*2001, None):
            with self.assertRaises(ValueError): normalize_text(text)

    def test_injected_api_receives_one_bounded_character_batch(self):
        batches = []
        def send(count, events, size):
            batches.append((count, size, [e.ki.dwFlags for e in events]))
            return count
        writer = UnicodeTextWriter(send_input=send)
        writer('🫐'); writer('\n')
        self.assertEqual([b[0] for b in batches], [4,2])
        self.assertEqual([b[1] for b in batches], [ctypes.sizeof(INPUT)]*2)

    def test_held_modifiers_never_send_and_partial_enter_is_released(self):
        batches = []
        def send(count, events, size):
            batches.append([e.ki.dwFlags for e in events])
            return 1
        with self.assertRaises(TextInputError):
            UnicodeTextWriter(send_input=send, key_state=lambda _: 0x8000)('x')
        self.assertEqual(batches, [])
        with self.assertRaises(TextInputError): UnicodeTextWriter(send_input=send)('\n')
        self.assertEqual(batches, [[0,2],[2]])

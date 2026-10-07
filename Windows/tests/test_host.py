import base64
import io
import json
import socket
import unittest
from PIL import Image
from bluey.host import Host, session_config
from bluey.protocol import Decoder, encode


class ProtocolTests(unittest.TestCase):
    def test_fragmentation_unicode_and_coalescing(self):
        decoder = Decoder()
        data = encode({'hello': 'Android 🫐'}) + encode({'command': 'awake'})
        result = []
        for byte in data:
            result.extend(decoder.feed(bytes([byte])))
        self.assertEqual(result, [{'hello': 'Android 🫐'}, {'command': 'awake'}])

    def test_bad_packet_does_not_break_next_packet(self):
        self.assertEqual(Decoder().feed(b'broken\n[]\n{"command":"sleep"}\n'), [{'command': 'sleep'}])

    def test_bound_unterminated_packet(self):
        import bluey.protocol as protocol
        from unittest.mock import patch
        with patch.object(protocol, 'MAX_PACKET', 10):
            with self.assertRaises(ValueError): Decoder().feed(b'x' * 11)


class HostTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.host = Host(lambda: (Image.new('RGB', (200, 100), 'blue'), (100, 50)),
                         lambda *event: self.events.append(event), lambda: 'desktop-only-key',
                         token_factory=lambda key: 'ephemeral-token' if key == 'desktop-only-key' else None,
                         name='Windows test host', action=lambda name, args: 'Confirmed '+name)
        port = self.host.start('127.0.0.1')
        self.client = socket.create_connection(('127.0.0.1', port), timeout=3)
        self.reader = self.client.makefile('rb')
        self.assertEqual(self.receive()['hello'], 'Windows test host')

    def tearDown(self):
        self.reader.close()
        self.client.close()
        self.host.close()

    def receive(self):
        return json.loads(self.reader.readline())

    def request(self, **fields):
        fields['callID'] = 'test-call'
        self.client.sendall(encode(fields))
        result = self.receive()
        self.assertEqual(result['callID'], 'test-call')
        return result

    def test_token_only_ephemeral_secret_leaves_host(self):
        result = self.request(command='realtimeToken')
        self.assertEqual(result['text'], 'ephemeral-token')
        self.assertNotIn('desktop-only-key', json.dumps(result))

    def test_screen_capture_and_point(self):
        result = self.request(command='tool', tool='look_at_screen', text='{}')
        self.assertEqual(result['command'], 'toolResult')
        image = Image.open(io.BytesIO(base64.b64decode(result['image'])))
        self.assertEqual(image.size, (200, 100))
        self.assertIn('(500, 500)', result['text'])
        self.request(command='tool', tool='point_at_spot', text='{"x":400,"y":600}')
        self.assertIn(('point', (400, 600)), self.events)

    def test_invalid_coordinates_are_not_executed(self):
        for args in ['{"x":-1,"y":5}', '{"x":true,"y":0}', '{"x":NaN,"y":0}', '[]']:
            result = self.request(command='tool', tool='point_at_spot', text=args)
            self.assertIn('could not complete', result['text'])
        self.assertFalse(any(event[0] == 'point' for event in self.events))

    def test_tool_failure_is_reported_and_connection_survives(self):
        def fail(): raise RuntimeError('private details')
        self.host.screen = fail
        result = self.request(command='tool', tool='look_at_screen', text='{}')
        self.assertNotIn('private details', result['text'])
        self.assertEqual(self.request(command='tool', tool='stop_pointing', text='{}')['text'], 'Following the mouse.')

    def test_action_dispatch_and_unsupported_tool(self):
        self.assertEqual(self.request(command='tool', tool='click', text='{"x":1,"y":2}')['text'], 'Confirmed click')
        self.assertIn('unavailable', self.request(command='tool', tool='unknown', text='{}')['text'])

    def test_unsupported_correlated_request_gets_failure_reply(self):
        result = self.request(command='notes', text='{}')
        self.assertEqual(result['command'], 'notes')
        self.assertIsNone(result['text'])

    def test_face_broadcast(self):
        self.host.broadcast({'face': {'gazeX': .25, 'gazeY': -.5, 'mood': 'pointing', 'talk': 0}})
        self.assertEqual(self.receive()['face']['mood'], 'pointing')

    def test_tools_only_advertised_when_enabled(self):
        self.assertNotIn('click', [tool['name'] for tool in session_config()['tools']])
        self.assertIn('click', [tool['name'] for tool in session_config(True)['tools']])


if __name__ == '__main__': unittest.main()

import base64
import io
import json
import socket
import unittest
from PIL import Image
from bluey.host import Host, session_config, phone_credentials_only
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

    def test_realtime_config_never_reads_or_mints_credentials(self):
        from unittest.mock import Mock
        self.host.key = Mock(side_effect=AssertionError('must not access credentials'))
        self.host.token_factory = Mock(side_effect=AssertionError('must not mint token'))
        enabled = [False]
        self.host.config_factory = lambda: session_config(enabled[0], False)
        first = self.request(command='realtimeConfig')
        self.assertEqual(first['command'], 'realtimeConfig')
        self.assertNotIn('click', {t['name'] for t in json.loads(first['text'])['tools']})
        enabled[0] = True
        second = self.request(command='realtimeConfig')
        names = {t['name'] for t in json.loads(second['text'])['tools']}
        self.assertIn('click', names)
        self.assertNotIn('list_projects', names)
        self.host.key.assert_not_called()
        self.host.token_factory.assert_not_called()

    def test_customer_token_request_directs_user_to_phone(self):
        self.host.key = lambda: None
        self.host.token_factory = phone_credentials_only
        result = self.request(command='realtimeToken')
        self.assertIsNone(result['text'])
        self.assertIn('phone settings', result['error'])
        self.assertNotIn('Save it once in Bluey settings', result['error'])

    def test_config_failure_is_sanitized_and_connection_survives(self):
        def broken(): raise RuntimeError('private data')
        self.host.config_factory = broken
        reply = self.request(command='realtimeConfig')
        self.assertIsNone(reply['text'])
        self.assertNotIn('private data', json.dumps(reply))
        self.assertEqual(self.request(command='tool', tool='stop_pointing')['text'], 'Following the mouse.')

    def test_token_errors_distinguish_auth_from_network(self):
        import urllib.error
        cases = [(ValueError('private'), 'No OpenAI key'),
                 (urllib.error.HTTPError('private', 401, 'private', {}, None), 'saved OpenAI key was rejected'),
                 (urllib.error.HTTPError('private', 429, 'private', {}, None), 'usage limit'),
                 (OSError('private'), 'internet connection')]
        for failure, expected in cases:
            def fail(key, error=failure):
                raise error
            self.host.token_factory = fail
            result = self.request(command='realtimeToken')
            self.assertIsNone(result['text'])
            self.assertIn(expected, result['error'])
            self.assertNotIn('private', json.dumps(result))

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

    def test_tracker_is_opt_in_and_dispatch_is_allowlisted(self):
        self.assertIn('unavailable', self.request(command='tool', tool='list_projects', text='{}')['text'])
        calls = []
        self.host.tracker = lambda name, args: calls.append((name, args)) or 'Approved tracker result'
        self.assertEqual(self.request(command='tool', tool='list_projects', text='{}')['text'], 'Approved tracker result')
        self.assertIn('unavailable', self.request(command='tool', tool='delete_project', text='{}')['text'])
        self.assertEqual(calls, [('list_projects', {})])

    def test_tracker_advertised_only_when_connected(self):
        self.assertNotIn('list_projects', {t['name'] for t in session_config()['tools']})
        config = session_config(tracker_enabled=True)
        self.assertIn('list_projects', {t['name'] for t in config['tools']})
        self.assertNotIn('click', {t['name'] for t in config['tools']})
        self.assertIn('local approval', config['instructions'])

    def test_unsupported_correlated_request_gets_failure_reply(self):
        result = self.request(command='notes', text='{}')
        self.assertEqual(result['command'], 'notes')
        self.assertIsNone(result['text'])

    def test_phone_speaking_true_heartbeat_and_stop(self):
        for active in (True, True, False):
            self.client.sendall(encode({'command': 'speaking', 'active': active}))
        # A subsequent correlated packet proves preceding state packets were consumed.
        self.request(command='tool', tool='stop_pointing', text='{}')
        self.assertEqual([event for event in self.events if event[0] == 'speaking'],
                         [('speaking', True), ('speaking', True), ('speaking', False)])

    def test_phone_speaking_rejects_non_boolean_state_and_face_payload(self):
        for invalid in ('true', 'false', 1, 0, None, {}, []):
            self.client.sendall(encode({'command': 'speaking', 'active': invalid,
                                       'text': 'true', 'face': {'talk': 1}}))
        self.client.sendall(encode({'command': 'speaking', 'text': 'true'}))
        self.request(command='tool', tool='stop_pointing', text='{}')
        self.assertFalse(any(event[0] == 'speaking' for event in self.events))
        self.assertFalse(any(event[0] == 'face' for event in self.events))

    def test_face_broadcast(self):
        self.host.broadcast({'face': {'gazeX': .25, 'gazeY': -.5, 'mood': 'pointing', 'talk': 0}})
        self.assertEqual(self.receive()['face']['mood'], 'pointing')

    def test_tools_only_advertised_when_enabled(self):
        self.assertNotIn('click', [tool['name'] for tool in session_config()['tools']])
        self.assertIn('click', [tool['name'] for tool in session_config(True)['tools']])


if __name__ == '__main__': unittest.main()

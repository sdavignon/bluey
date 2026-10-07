import unittest
from unittest.mock import patch, MagicMock
from bluey.network import pairing_addresses


class NetworkTests(unittest.TestCase):
    def test_routed_interface_excludes_virtual_adapters(self):
        probe = MagicMock()
        probe.__enter__.return_value = probe
        probe.getsockname.return_value = ('192.168.1.101', 50000)
        with patch('bluey.network.socket.socket', return_value=probe), patch('bluey.network.socket.getaddrinfo') as lookup:
            self.assertEqual(pairing_addresses(), ['192.168.1.101'])
            lookup.assert_not_called()
            probe.send.assert_not_called()

    def test_no_route_falls_back_without_loopback_or_linklocal(self):
        addresses = [(None,None,None,None,(ip,0)) for ip in ['127.0.0.1','169.254.1.2','192.168.1.101']]
        with patch('bluey.network.socket.socket', side_effect=OSError), patch('bluey.network.socket.getaddrinfo', return_value=addresses):
            self.assertEqual(pairing_addresses(), ['192.168.1.101'])

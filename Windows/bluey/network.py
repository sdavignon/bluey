"""Select the routed interface rather than advertising Hyper-V/WSL adapters."""
import socket


def pairing_addresses():
    # UDP connect consults the routing table; no packet is sent.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
            if address and not address.startswith(("127.", "169.254.")):
                return [address]
    except OSError:
        pass
    return sorted({entry[4][0] for entry in socket.getaddrinfo(
        socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
        if not entry[4][0].startswith(("127.", "169.254."))})

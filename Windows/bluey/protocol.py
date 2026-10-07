"""Wire compatible with Shared/GooglyLink.swift."""
import json

MAX_PACKET = 16 * 1024 * 1024


def encode(packet):
    return (json.dumps(packet, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


class Decoder:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        packets = []
        while b"\n" in self.buffer:
            end = self.buffer.index(10)
            if end > MAX_PACKET:
                raise ValueError("Packet too large")
            line = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            try:
                packet = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(packet, dict):
                packets.append(packet)
        if len(self.buffer) > MAX_PACKET:
            raise ValueError("Packet too large")
        return packets

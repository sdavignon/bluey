package co.visionairy.bluey;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Incremental bounded newline framing. UTF-8 is decoded only after a full line arrives. */
final class PacketFramer {
    private final int maximum;
    private final ByteArrayOutputStream line = new ByteArrayOutputStream();
    PacketFramer() { this(16 * 1024 * 1024); }
    PacketFramer(int maximum) { this.maximum = maximum; }
    List<String> feed(byte[] bytes, int count) {
        List<String> lines = new ArrayList<>();
        for (int i=0; i<count; i++) {
            if (bytes[i]=='\n') {
                lines.add(new String(line.toByteArray(), StandardCharsets.UTF_8));
                line.reset();
            } else {
                if (line.size() >= maximum) throw new IllegalArgumentException("Packet too large");
                line.write(bytes[i]);
            }
        }
        return lines;
    }
}

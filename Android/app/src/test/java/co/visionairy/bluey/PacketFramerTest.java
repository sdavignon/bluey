package co.visionairy.bluey;

import org.junit.Test;
import static org.junit.Assert.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class PacketFramerTest {
    @Test public void handlesFragmentedUnicodeAndMultiplePackets() {
        PacketFramer framer = new PacketFramer();
        byte[] wire = "{\"hello\":\"Phone 🫐\"}\n{\"command\":\"awake\"}\n".getBytes(StandardCharsets.UTF_8);
        List<String> lines = new ArrayList<>();
        for (byte b : wire) lines.addAll(framer.feed(new byte[]{b},1));
        assertEquals(2,lines.size());
        assertEquals("{\"hello\":\"Phone 🫐\"}",lines.get(0));
        assertEquals("{\"command\":\"awake\"}",lines.get(1));
    }
    @Test public void retainsIncompleteTail() {
        PacketFramer framer = new PacketFramer();
        byte[] first = "one\ntw".getBytes(StandardCharsets.UTF_8);
        assertEquals("one",framer.feed(first,first.length).get(0));
        assertEquals("two",framer.feed(new byte[]{'o','\n'},2).get(0));
    }
    @Test(expected=IllegalArgumentException.class) public void boundsUnterminatedPackets() {
        new PacketFramer(2).feed(new byte[]{'a','b','c'},3);
    }
}

package co.visionairy.bluey;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.List;

public class SpeechChunksTest {
    @Test public void longReplyIsNotTruncated() {
        String reply = "This is a long answer with natural word boundaries. ".repeat(100);
        List<String> chunks = SpeechChunks.split(reply,4000);
        assertTrue(chunks.size()>1);
        assertEquals(reply,String.join("",chunks));
        for (String chunk:chunks) assertTrue(chunk.length()<=4000);
    }
    @Test public void emojiIsNotCutInHalf() {
        String reply = "abc🫐abcd🫐";
        List<String> chunks = SpeechChunks.split(reply,4);
        assertEquals(reply,String.join("",chunks));
        for (String chunk:chunks) {
            assertTrue(chunk.length()<=4);
            assertFalse(Character.isHighSurrogate(chunk.charAt(chunk.length()-1)));
            assertFalse(Character.isLowSurrogate(chunk.charAt(0)));
        }
    }
    @Test public void emptyReplyQueuesNothing() { assertTrue(SpeechChunks.split("",4000).isEmpty()); }
}

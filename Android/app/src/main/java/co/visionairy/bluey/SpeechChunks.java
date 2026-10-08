package co.visionairy.bluey;

import java.util.ArrayList;
import java.util.List;

/** Preserve all reply text, including surrogate pairs, while respecting the system engine's limit. */
final class SpeechChunks {
    static List<String> split(String text, int maximum) {
        if (maximum < 2) throw new IllegalArgumentException("Speech chunk limit must be at least two");
        List<String> parts = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(text.length(),start+maximum);
            if (end < text.length() && Character.isHighSurrogate(text.charAt(end-1)) && Character.isLowSurrogate(text.charAt(end))) end--;
            if (end < text.length()) {
                for (int i=end-1;i>start+maximum/2;i--) {
                    if (Character.isWhitespace(text.charAt(i))) { end=i+1; break; }
                }
            }
            parts.add(text.substring(start,end));
            start=end;
        }
        return parts;
    }
}

package co.visionairy.bluey;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class MeetingProfileTest {
    @Test public void meetingKeepsQuietTextAndUsesFarField() throws Exception {
        JSONObject config = new JSONObject().put("instructions", "Trusted base.")
                .put("audio", new JSONObject().put("input", new JSONObject()
                        .put("format", new JSONObject().put("type", "audio/pcm").put("rate", 24000))
                        .put("turn_detection", new JSONObject().put("threshold", 0.5))))
                .put("tools", new JSONArray().put(new JSONObject().put("name", "example")));
        MeetingProfile.apply(config, true);
        JSONObject input = config.getJSONObject("audio").getJSONObject("input");
        assertEquals("far_field", input.getJSONObject("noise_reduction").getString("type"));
        assertFalse(input.getJSONObject("turn_detection").getBoolean("create_response"));
        assertFalse(input.getJSONObject("turn_detection").getBoolean("interrupt_response"));
        assertEquals(0.5, input.getJSONObject("turn_detection").getDouble("threshold"), 0.0);
        assertEquals(24000, input.getJSONObject("format").getInt("rate"));
        assertEquals("text", config.getJSONArray("output_modalities").getString(0));
        assertEquals("example", config.getJSONArray("tools").getJSONObject(0).getString("name"));
        assertTrue(config.getString("instructions").startsWith("Trusted base."));
    }
    @Test public void normalModePreservesConfiguration() throws Exception {
        JSONObject config = new JSONObject().put("instructions", "Original")
                .put("audio", new JSONObject().put("input", new JSONObject().put("noise_reduction", new JSONObject().put("type", "near_field"))));
        String before = config.toString();
        assertSame(config, MeetingProfile.apply(config, false));
        assertEquals(before, config.toString());
        assertEquals("{\"type\":\"response.create\"}", MeetingProfile.ask(false).toString());
    }
    @Test public void recapExplicitAndReadOnly() throws Exception {
        JSONObject ask = MeetingProfile.ask(true);
        assertEquals("response.create", ask.getString("type"));
        JSONObject response = ask.getJSONObject("response");
        assertEquals("none", response.getString("tool_choice"));
        assertEquals("text", response.getJSONArray("output_modalities").getString(0));
        String instructions = response.getString("instructions");
        assertTrue(instructions.contains("pressed Ask"));
        assertTrue(instructions.contains("confirmed decisions"));
        assertTrue(instructions.contains("owners"));
        assertTrue(instructions.contains("deadlines"));
        assertTrue(instructions.contains("Do not infer identities"));
        assertTrue(instructions.contains("Do not call tools, save, send"));
    }
    @Test public void legacyUpdateExcludesReadOnlyFields() throws Exception {
        JSONObject event = MeetingProfile.legacyUpdate(new JSONObject().put("id", "session_example").put("instructions", "Original").put("client_secret", "must-not-copy"));
        assertEquals("session.update", event.getString("type"));
        JSONObject session = event.getJSONObject("session");
        assertFalse(session.has("id")); assertFalse(session.has("client_secret"));
        assertEquals("realtime", session.getString("type"));
        assertFalse(session.getJSONObject("audio").getJSONObject("input").getJSONObject("turn_detection").getBoolean("create_response"));
    }
    @Test public void repeatApplyDoesNotDuplicatePolicy() throws Exception {
        JSONObject config = new JSONObject(); MeetingProfile.apply(config, true);
        String first = config.getString("instructions"); MeetingProfile.apply(config, true);
        assertEquals(first, config.getString("instructions"));
    }
}

package co.visionairy.bluey;

import org.junit.Test;
import org.json.JSONObject;
import org.json.JSONArray;
import static org.junit.Assert.*;

public class AgentSessionTest {
    @Test public void phoneAgentDoesNotRequireDesktop() {
        assertFalse(AgentSession.needsDesktop(true));
        assertTrue(AgentSession.needsDesktop(false));
    }
    @Test public void standaloneAgentCannotAdvertiseComputerTools() throws Exception {
        JSONObject session = AgentSession.phoneConfiguration().getJSONObject("session");
        JSONArray tools = session.getJSONArray("tools");
        assertEquals(1,tools.length());
        assertEquals("go_to_sleep",tools.getJSONObject(0).getString("name"));
        assertFalse(AgentSession.localTool("click"));
        assertFalse(AgentSession.localTool("look_at_screen"));
        assertTrue(AgentSession.localTool("go_to_sleep"));
    }
    @Test public void microphoneContextDoesNotRequestAutomaticReplies() throws Exception {
        JSONObject input = AgentSession.phoneConfiguration().getJSONObject("session").getJSONObject("audio").getJSONObject("input");
        assertFalse(input.getJSONObject("turn_detection").getBoolean("create_response"));
        assertFalse(input.getJSONObject("turn_detection").getBoolean("interrupt_response"));
        assertEquals(24000,input.getJSONObject("format").getInt("rate"));
    }
    @Test public void configUsesTextForLocalTtsWithoutEmbeddingCredentials() throws Exception {
        JSONObject event = AgentSession.phoneConfiguration();
        assertEquals("session.update",event.getString("type"));
        JSONArray output = event.getJSONObject("session").getJSONArray("output_modalities");
        assertEquals(1,output.length());
        assertEquals("text",output.getString(0));
        assertFalse(event.toString().contains("Authorization"));
        assertFalse(event.toString().contains("api_key"));
    }
}

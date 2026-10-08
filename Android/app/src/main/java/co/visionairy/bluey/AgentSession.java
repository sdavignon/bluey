package co.visionairy.bluey;

import org.json.JSONArray;
import org.json.JSONObject;

/** Standalone sessions deliberately advertise no computer tools. */
final class AgentSession {
    static final String MODEL = "gpt-realtime-2.1";
    static JSONObject phoneConfiguration() throws Exception {
        JSONObject turn = new JSONObject().put("type", "server_vad").put("threshold", .5)
            .put("prefix_padding_ms",300).put("silence_duration_ms",500)
            .put("create_response",false).put("interrupt_response",false);
        JSONObject input = new JSONObject().put("format",new JSONObject().put("type","audio/pcm").put("rate",24000))
            .put("turn_detection",turn).put("noise_reduction",new JSONObject().put("type","near_field"))
            .put("transcription",new JSONObject().put("model","gpt-4o-mini-transcribe"));
        JSONObject sleep = new JSONObject().put("type","function").put("name","go_to_sleep")
            .put("description","End this conversation when the user asks you to sleep; give a brief goodbye.")
            .put("parameters",new JSONObject().put("type","object").put("properties",new JSONObject())
                 .put("required",new JSONArray()).put("additionalProperties",false));
        JSONObject session = new JSONObject().put("type","realtime").put("model",MODEL)
            .put("instructions","You are Bluey, a friendly blueberry assistant running independently on this Android phone. "
                + "Answer questions and help with reasoning, planning and writing. Keep spoken replies concise and natural. "
                + "Listen quietly until the user asks for a response. You have no access to a computer, screen, files, "
                + "phone controls or live web search. Never claim to have seen or changed them. "
                + "Be honest about uncertainty. Use go_to_sleep when asked to stop listening.")
            .put("output_modalities",new JSONArray().put("text"))
            .put("audio",new JSONObject().put("input",input)).put("tools",new JSONArray().put(sleep)).put("tool_choice","auto");
        return new JSONObject().put("type","session.update").put("session",session);
    }
    static boolean needsDesktop(boolean phoneMode) { return !phoneMode; }
    static boolean localTool(String name) { return "go_to_sleep".equals(name); }
}

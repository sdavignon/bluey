package co.visionairy.bluey;

import android.annotation.SuppressLint;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import java.util.concurrent.TimeUnit;

/** Foreground voice with standalone phone credentials or optional desktop tokens. */
final class LiveVoice {
    interface Listener { void state(String state); void caption(String text); }
    private final DesktopLink link;
    private final Listener listener;
    private final PhoneCredentials credentials;
    private final SpeechOutput speech;
    private boolean phoneSession;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient.Builder().pingInterval(20, TimeUnit.SECONDS).build();
    private volatile AudioRecord recorder;
    private WebSocket socket;
    private volatile boolean recording;
    private boolean awake, holding, ready, askWhenReady, responding, sleepAfter;
    private int generation;
    private String transcript = "";


    LiveVoice(DesktopLink link, Listener listener, PhoneCredentials credentials, SpeechOutput speech) {
        this.link = link; this.listener = listener; this.credentials = credentials; this.speech = speech;
    }
    boolean requiresDesktop() { return awake && AgentSession.needsDesktop(phoneSession); }
    boolean isAwake() { return awake; }
    void toggle() { if (awake) sleep(); else wake(); }
    void wake() {
        if (awake) return;
        awake = true;
        askWhenReady = false;
        transcript = "";
        int run = ++generation;
        listener.state("Waking up…");
        phoneSession = credentials.phoneMode();
        if (phoneSession) {
            try {
                String key = credentials.read();
                if (key.isEmpty()) { fail("Add your OpenAI key in Voice settings to use Bluey without a PC."); return; }
                connect(key, run);
            } catch (Exception e) { fail("Could not unlock the saved key. Save it again in Voice settings."); }
        } else link.request(DesktopLink.json("command", "realtimeToken"), reply -> {
            if (run != generation || !awake) return;
            String token = reply == null ? "" : reply.optString("text", "");
            if (token.isEmpty() || token.equals("null")) { fail("Pair a desktop or select standalone mode in Voice settings."); return; }
            connect(token, run);
        });
    }
    private void connect(String token, int run) {
            Request request = new Request.Builder()
                .url("wss://api.openai.com/v1/realtime?model=" + AgentSession.MODEL)
                .header("Authorization", "Bearer " + token).build();
            socket = http.newWebSocket(request, new WebSocketListener() {
                @Override public void onMessage(WebSocket ws, String text) {
                    ui.post(() -> { if (run == generation && awake) { try { handle(new JSONObject(text)); } catch (Exception e) { fail("Invalid voice response."); } } });
                }
                @Override public void onFailure(WebSocket ws, Throwable error, Response response) {
                    ui.post(() -> {
                        if (run != generation || !awake) return;
                        int code = response == null ? 0 : response.code();
                        if (code == 401 || code == 403) fail("OpenAI rejected the key or account. Check Voice settings or the paired desktop key.");
                        else if (code == 429) fail("OpenAI usage limit reached. Check your account quota and billing.");
                        else fail("Voice connection lost. Double tap to reconnect.");
                    });
                }
                @Override public void onClosing(WebSocket ws, int code, String reason) { ws.close(code, reason); }
                @Override public void onClosed(WebSocket ws, int code, String reason) {
                    ui.post(() -> { if (run == generation && awake) fail("Voice session ended. Double tap to reconnect."); });
                }
            });
    }
    void sleep() {
        awake = ready = holding = askWhenReady = responding = sleepAfter = false;
        generation++;
        speech.stop();
        recording = false;
        AudioRecord old = recorder;
        if (old != null) try { old.stop(); } catch (Exception ignored) {}
        if (socket != null) { socket.close(1000, "Sleep"); socket = null; }
        link.send(DesktopLink.json("command", "asleep"));
        listener.state("Ready · double tap to wake");
    }
    private void fail(String message) { sleep(); listener.caption(message); }
    void beginAsk() {
        if (!awake) wake();
        holding = true;
        sleepAfter = false;
        speech.stop();
        if (responding) { send(DesktopLink.json("type", "response.cancel")); responding = false; }
        transcript = "";
        caption(false);
        listener.caption("");
        if (ready) listener.state("I'm all ears");
    }
    void endAsk() {
        if (!holding) return;
        holding = false;
        if (!ready) { askWhenReady = true; return; }
        ask();
    }
    private void ask() {
        askWhenReady = false;
        listener.state("Thinking…");
        send(DesktopLink.json("type", "input_audio_buffer.commit"));
        send(DesktopLink.json("type", "response.create"));
    }
    private void send(JSONObject packet) {
        if (socket != null && !socket.send(packet.toString())) fail("Voice connection could not send audio.");
    }
    private void caption(boolean done) {
        JSONObject packet = DesktopLink.json("command", done ? "captionDone" : "caption");
        DesktopLink.put(packet, "text", transcript);
        link.send(packet);
        listener.caption(transcript);
    }
    private void handle(JSONObject event) throws Exception {
        switch (event.optString("type")) {
            case "session.created":
                if (phoneSession) send(AgentSession.phoneConfiguration());
                else sessionReady();
                break;
            case "session.updated":
                if (phoneSession && !ready) sessionReady();
                break;
            case "response.created": responding = true; transcript = ""; break;
            case "response.output_text.delta":
            case "response.output_audio_transcript.delta":
                transcript += event.optString("delta");
                listener.state("Replying"); caption(false); break;
            case "response.done":
                responding = false;
                if (!transcript.isEmpty()) caption(true);
                JSONObject response = event.optJSONObject("response");
                if (response != null && response.optString("status").equals("failed")) { fail("Voice response failed. Check your OpenAI account and try again."); return; }
                if (response != null && response.optString("status").equals("cancelled")) { finishReply(); return; }
                JSONArray output = response == null ? null : response.optJSONArray("output");
                JSONArray calls = new JSONArray();
                if (output != null) for (int i = 0; i < output.length(); i++) {
                    JSONObject item = output.optJSONObject(i);
                    if (item != null && item.optString("type").equals("function_call")) calls.put(item);
                }
                if (calls.length() > 0) runTools(calls, 0);
                else speakReply();
                break;
            case "error":
                JSONObject error = event.optJSONObject("error");
                if (error != null && error.optString("code").equals("input_audio_buffer_commit_empty")) break;
                fail("Voice service error. Check your Internet connection and OpenAI account.");
                break;
        }
    }
    private void sessionReady() {
        if (ready) return;
        ready = true;
        startAudio();
        if (!awake) return;
        link.send(DesktopLink.json("command", "awake"));
        if (askWhenReady) ask(); else listener.state(holding ? "I'm all ears" : "Listening · hold to ask");
    }
    private void finishReply() {
        if (sleepAfter) sleep();
        else if (awake) listener.state(holding ? "I'm all ears" : "Listening · hold to ask");
    }
    private void speakReply() {
        if (!awake) return;
        if (transcript.isEmpty() || !credentials.spokenReplies()) { finishReply(); return; }
        listener.state("Speaking");
        int run = generation;
        String reply = transcript;
        if (!speech.speak(reply, success -> {
            if (run != generation || !awake) return;
            if (!success) listener.caption(reply + "\n(Speech playback failed; text is still available.)");
            finishReply();
        })) {
            listener.caption(reply + "\n(Phone speech voice unavailable. Check Android text-to-speech settings.)");
            finishReply();
        }
    }
    private void runTools(JSONArray calls, int index) throws Exception {
        JSONObject call = calls.getJSONObject(index);
        String name = call.optString("name");
        if (name.equals("go_to_sleep")) sleepAfter = true;
        JSONObject packet = DesktopLink.json("command", "tool");
        DesktopLink.put(packet, "tool", name);
        DesktopLink.put(packet, "text", call.optString("arguments", "{}"));
        int run = generation;
        java.util.function.Consumer<JSONObject> completed = reply -> {
            if (run != generation || !awake) return;
            try {
                JSONObject result = DesktopLink.json("type", "function_call_output");
                DesktopLink.put(result, "call_id", call.optString("call_id"));
                DesktopLink.put(result, "output", reply == null ? "Desktop did not answer." : reply.optString("text", "Tool failed."));
                JSONObject event = DesktopLink.json("type", "conversation.item.create");
                DesktopLink.put(event, "item", result); send(event);
                if (reply != null && !reply.optString("image").isEmpty()) {
                    JSONObject content = DesktopLink.json("type", "input_image");
                    DesktopLink.put(content, "image_url", "data:image/jpeg;base64," + reply.getString("image"));
                    JSONObject image = DesktopLink.json("type", "message");
                    DesktopLink.put(image, "role", "user"); DesktopLink.put(image, "content", new JSONArray().put(content));
                    JSONObject imageEvent = DesktopLink.json("type", "conversation.item.create");
                    DesktopLink.put(imageEvent, "item", image); send(imageEvent);
                }
                if (index + 1 < calls.length()) runTools(calls, index + 1);
                else send(DesktopLink.json("type", "response.create"));
            } catch (Exception e) { fail("Agent tool response failed."); }
        };
        if (AgentSession.localTool(name)) completed.accept(DesktopLink.json("text", "Going to sleep after saying goodbye."));
        else if (phoneSession) completed.accept(DesktopLink.json("text", "This standalone phone session has no computer or phone-control tools."));
        else link.request(packet, completed);
    }
    @SuppressLint("MissingPermission")
    private void startAudio() {
        if (recording) return;
        int minimum = AudioRecord.getMinBufferSize(24000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) { fail("This phone does not support 24 kHz microphone capture."); return; }
        AudioRecord candidate = null;
        try {
            candidate = new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, 24000,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(minimum, 9600));
            if (candidate.getState() != AudioRecord.STATE_INITIALIZED) { candidate.release(); fail("Microphone unavailable."); return; }
            candidate.startRecording();
        } catch (Exception e) {
            if (candidate != null) candidate.release();
            fail("Microphone unavailable. Check permission in Settings."); return;
        }
        final AudioRecord audio = candidate;
        recorder = audio; recording = true;
        WebSocket target = socket;
        int audioGeneration = generation;
        new Thread(() -> {
            byte[] data = new byte[2400];
            try {
                while (recording && recorder == audio) {
                    int count = audio.read(data, 0, data.length);
                    if (count < 0) throw new IllegalStateException("Audio read failed");
                    if (count > 0 && !speech.speaking()) {
                        JSONObject packet = DesktopLink.json("type", "input_audio_buffer.append");
                        DesktopLink.put(packet, "audio", Base64.encodeToString(data, 0, count, Base64.NO_WRAP));
                        if (target.queueSize() > 1024 * 1024 || !target.send(packet.toString())) throw new IllegalStateException("Audio connection stalled");
                    }
                }
            } catch (Exception e) {
                ui.post(() -> { if (audioGeneration == generation && awake) fail("Microphone or voice connection interrupted."); });
            } finally {
                audio.release();
                if (recorder == audio) recorder = null;
            }
        }, "Bluey microphone").start();
    }
    void destroy() { sleep(); speech.destroy(); http.dispatcher().executorService().shutdown(); http.connectionPool().evictAll(); }
}

package co.visionairy.bluey;

import android.annotation.SuppressLint;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.ToneGenerator;
import android.media.AudioManager;
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

/** Foreground-only 24 kHz PCM voice. The durable API key stays on the desktop. */
final class LiveVoice {
    interface Listener { void state(String state); void caption(String text); }
    private final DesktopLink link;
    private final Listener listener;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient.Builder().pingInterval(20, TimeUnit.SECONDS).build();
    private volatile AudioRecord recorder;
    private WebSocket socket;
    private volatile boolean recording;
    private boolean awake, holding, ready, askWhenReady, responding, sleepAfter;
    private int generation;
    private String transcript = "";
    private final ToneGenerator chirp = new ToneGenerator(AudioManager.STREAM_MUSIC, 25);

    LiveVoice(DesktopLink link, Listener listener) { this.link = link; this.listener = listener; }
    boolean isAwake() { return awake; }
    void toggle() { if (awake) sleep(); else wake(); }
    void wake() {
        if (awake) return;
        awake = true;
        int run = ++generation;
        listener.state("Waking up…");
        link.request(DesktopLink.json("command", "realtimeToken"), reply -> {
            if (run != generation || !awake) return;
            String token = reply == null ? "" : reply.optString("text", "");
            if (token.isEmpty() || token.equals("null")) { fail("Set an OpenAI key on the desktop and reconnect."); return; }
            Request request = new Request.Builder()
                .url("wss://api.openai.com/v1/realtime?model=gpt-realtime-2.1")
                .header("Authorization", "Bearer " + token).build();
            socket = http.newWebSocket(request, new WebSocketListener() {
                @Override public void onMessage(WebSocket ws, String text) {
                    ui.post(() -> { if (run == generation && awake) { try { handle(new JSONObject(text)); } catch (Exception e) { fail("Invalid voice response."); } } });
                }
                @Override public void onFailure(WebSocket ws, Throwable error, Response response) {
                    ui.post(() -> { if (run == generation && awake) fail("Voice connection lost. Double tap to reconnect."); });
                }
                @Override public void onClosing(WebSocket ws, int code, String reason) { ws.close(code, reason); }
                @Override public void onClosed(WebSocket ws, int code, String reason) {
                    ui.post(() -> { if (run == generation && awake) fail("Voice session ended. Double tap to reconnect."); });
                }
            });
        });
    }
    void sleep() {
        awake = ready = holding = askWhenReady = responding = sleepAfter = false;
        generation++;
        recording = false;
        AudioRecord old = recorder;
        if (old != null) try { old.stop(); } catch (Exception ignored) {}
        if (socket != null) { socket.close(1000, "Sleep"); socket = null; }
        link.send(DesktopLink.json("command", "asleep"));
        listener.state("Following · double tap to wake");
    }
    private void fail(String message) { sleep(); listener.caption(message); }
    void beginAsk() {
        if (!awake) wake();
        holding = true;
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
                ready = true;
                startAudio();
                if (!awake) return;
                link.send(DesktopLink.json("command", "awake"));
                if (askWhenReady) ask(); else listener.state(holding ? "I'm all ears" : "Listening · hold to ask");
                break;
            case "response.created": responding = true; transcript = ""; break;
            case "response.output_text.delta":
            case "response.output_audio_transcript.delta":
                if (transcript.isEmpty()) chirp.startTone(ToneGenerator.TONE_PROP_BEEP, 130);
                transcript += event.optString("delta");
                listener.state("Replying"); caption(false); break;
            case "response.done":
                responding = false;
                if (!transcript.isEmpty()) caption(true);
                JSONObject response = event.optJSONObject("response");
                if (response != null && response.optString("status").equals("failed")) { fail("Voice response failed. Check the desktop account and try again."); return; }
                JSONArray output = response == null ? null : response.optJSONArray("output");
                JSONArray calls = new JSONArray();
                if (output != null) for (int i = 0; i < output.length(); i++) {
                    JSONObject item = output.optJSONObject(i);
                    if (item != null && item.optString("type").equals("function_call")) calls.put(item);
                }
                if (calls.length() > 0) runTools(calls, 0);
                else if (sleepAfter) sleep();
                else listener.state(holding ? "I'm all ears" : "Listening · hold to ask");
                break;
            case "error":
                JSONObject error = event.optJSONObject("error");
                if (error != null && error.optString("code").equals("input_audio_buffer_commit_empty")) break;
                fail("Voice service error. Check your connection and desktop account.");
                break;
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
        link.request(packet, reply -> {
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
            } catch (Exception e) { fail("Desktop tool response failed."); }
        });
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
                    if (count > 0) {
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
    void destroy() { sleep(); chirp.release(); http.dispatcher().executorService().shutdown(); http.connectionPool().evictAll(); }
}

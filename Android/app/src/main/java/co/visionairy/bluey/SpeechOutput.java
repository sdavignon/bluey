package co.visionairy.bluey;

import android.content.Context;
import android.media.AudioAttributes;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Log;
import java.util.Locale;

/** Native phone TTS. All control and callbacks run on the main thread. */
final class SpeechOutput {
    interface Listener { void speaking(boolean active); void error(String message); }
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Listener listener;
    private final TextToSpeech engine;
    private boolean ready, unavailable, destroyed;
    private volatile boolean active;
    private volatile long quietUntil;
    private int generation;
    private String pending;
    private Runnable completion;

    SpeechOutput(Context context, Listener listener) {
        this.listener = listener;
        engine = new TextToSpeech(context.getApplicationContext(), status -> ui.post(() -> initialize(status)));
    }
    private void initialize(int status) {
        if (destroyed || unavailable) return;
        if (status != TextToSpeech.SUCCESS || engine.setLanguage(Locale.US) < 0) {
            unavailable("Install an English voice in Android text-to-speech settings."); return;
        }
        // Prefer installed offline English voices; never download voice data automatically.
        if (engine.getVoices() != null) {
            Voice best = null;
            for (Voice voice : engine.getVoices()) {
                if (!voice.isNetworkConnectionRequired() && voice.getLocale().equals(Locale.US)
                        && !voice.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)
                        && (best == null || voice.getQuality() > best.getQuality())) best = voice;
            }
            if (best != null) engine.setVoice(best);
        }
        engine.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
        engine.setPitch(1.12f); engine.setSpeechRate(1.0f);
        engine.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { Log.i("BlueySpeech", "Playback started"); }
            @Override public void onDone(String id) { ui.post(() -> finish(id, false)); }
            @Override public void onError(String id) { ui.post(() -> finish(id, true)); }
            @Override public void onError(String id, int code) { ui.post(() -> finish(id, true)); }
        });
        ready = true;
        if (pending != null) enqueue(pending);
    }
    boolean blocksMicrophone() { return active || SystemClock.uptimeMillis() < quietUntil; }
    void speak(String text, Runnable done) {
        stop();
        if (destroyed || unavailable || text.trim().isEmpty()) {
            if (unavailable) listener.error("Phone speech unavailable; the reply is still shown on screen.");
            done.run(); return;
        }
        active = true; completion = done; pending = text;
        listener.speaking(true);
        if (ready) enqueue(text);
        else {
            int run = generation;
            ui.postDelayed(() -> {
                if (!destroyed && !ready && active && run == generation) {
                    listener.error("Phone speech is still loading. Try Test voice again shortly.");
                    finish(run+":last", true);
                }
            }, 15000);
        }
    }
    private void enqueue(String text) {
        pending = null;
        int offset = 0, chunk = 0;
        int limit = Math.min(3000, TextToSpeech.getMaxSpeechInputLength());
        while (offset < text.length()) {
            int end = Math.min(text.length(), offset + limit);
            if (end < text.length()) {
                int space = text.lastIndexOf(' ', end);
                if (space > offset) end = space;
                else if (Character.isHighSurrogate(text.charAt(end-1))) end--;
            }
            boolean last = end == text.length();
            String id = generation + ":" + chunk + (last ? ":last" : "");
            if (engine.speak(text.substring(offset,end), chunk==0 ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD, null, id) == TextToSpeech.ERROR) {
                finish(id, true); return;
            }
            offset = end; chunk++;
        }
    }
    private void finish(String id, boolean failed) {
        if (!active || !id.startsWith(generation+":")) return;
        if (!failed && !id.endsWith(":last")) return;
        if (failed) engine.stop();
        Log.i("BlueySpeech", failed ? "Playback failed" : "Playback completed");
        active = false; pending = null; quietUntil = SystemClock.uptimeMillis()+250;
        listener.speaking(false);
        if (failed) listener.error("Couldn't play speech. Check phone media volume and text-to-speech settings.");
        Runnable done = completion; completion = null;
        if (done != null) done.run();
    }
    private void unavailable(String message) {
        unavailable = true;
        if (active) { String id=generation+":last"; listener.error(message); finish(id,true); }
    }
    void stop() {
        generation++; pending = null; completion = null;
        boolean wasActive = active; active = false;
        if (wasActive) quietUntil = SystemClock.uptimeMillis()+250;
        engine.stop();
        if (wasActive) { listener.speaking(false); Log.i("BlueySpeech", "Playback cancelled"); }
    }
    void shutdown() { stop(); destroyed = true; engine.shutdown(); }
}

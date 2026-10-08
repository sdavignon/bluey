package co.visionairy.bluey;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import java.util.Locale;
import java.util.function.Consumer;

/** System TTS needs no PC or second API key. Stale utterance callbacks cannot affect a new session. */
final class SpeechOutput {
    private final TextToSpeech tts;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private volatile boolean ready;
    private volatile boolean speaking;
    private volatile long muteUntil;
    private String current = "", last = "";
    private long next;
    private Consumer<Boolean> completion;
    SpeechOutput(Context context) {
        tts = new TextToSpeech(context.getApplicationContext(), status -> {
            if (status == TextToSpeech.SUCCESS) {
                int language = ttsLanguage();
                ready = language != TextToSpeech.LANG_MISSING_DATA && language != TextToSpeech.LANG_NOT_SUPPORTED;
            }
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            public void onStart(String id) {}
            public void onDone(String id) { ui.post(() -> finished(id, true)); }
            @Deprecated public void onError(String id) { ui.post(() -> finished(id, false)); }
            public void onError(String id, int code) { ui.post(() -> finished(id, false)); }
            public void onStop(String id, boolean interrupted) { ui.post(() -> finished(id, false)); }
        });
    }
    private int ttsLanguage() { return tts.setLanguage(Locale.getDefault()); }
    boolean speaking() { return speaking || SystemClock.elapsedRealtime() < muteUntil; }
    boolean speak(String text, Consumer<Boolean> done) {
        stop();
        if (!ready || text.isEmpty()) return false;
        current = "bluey-" + (++next); completion = done; speaking = true;
        java.util.List<String> parts = SpeechChunks.split(text,TextToSpeech.getMaxSpeechInputLength());
        int count = parts.size();
        last = current + "-" + (count-1);
        for (int i=0;i<count;i++) {
            String part = parts.get(i);
            if (tts.speak(part,i==0 ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD,null,current+"-"+i) != TextToSpeech.SUCCESS) {
                stop(); return false;
            }
        }
        String utterance = last;
        ui.postDelayed(() -> finished(utterance,false),Math.min(600000L,10000L+text.length()*100L));
        return true;
    }
    private void finished(String id, boolean success) {
        if (current.isEmpty() || (success ? !id.equals(last) : !id.startsWith(current+"-"))) return;
        current = last = ""; speaking = false;
        if (!success) tts.stop(); muteUntil = SystemClock.elapsedRealtime()+250;
        Consumer<Boolean> done = completion; completion = null;
        if (done != null) done.accept(success);
    }
    void stop() { current = last = ""; completion = null; speaking = false; muteUntil = 0; tts.stop(); }
    void destroy() { stop(); tts.shutdown(); }
}

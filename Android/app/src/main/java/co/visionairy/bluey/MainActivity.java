package co.visionairy.bluey;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    private DesktopLink link;
    private LiveVoice voice;
    private TextView connection, state, caption;
    private FaceView face;
    private String[] desktops = new String[0];
    private WifiManager.MulticastLock multicast;
    private final Handler handler = new Handler();
    private boolean holding, resumed;
    private final Runnable hold = () -> {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            holding = true; voice.beginAsk();
        } else requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
    };
    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setVolumeControlStream(android.media.AudioManager.STREAM_MUSIC);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        FrameLayout root = new FrameLayout(this);
        face = new FaceView(this); root.addView(face);
        LinearLayout labels = new LinearLayout(this); labels.setOrientation(LinearLayout.VERTICAL); labels.setPadding(24,12,24,12);
        connection = label("Looking for a desktop…"); state = label("Following · double tap to wake"); caption = label("");
        labels.addView(connection); labels.addView(state); labels.addView(caption);
        root.addView(labels, new FrameLayout.LayoutParams(-2,-2,android.view.Gravity.TOP | android.view.Gravity.START));
        Button pairing = new Button(this); pairing.setText(R.string.pair_desktop);
        FrameLayout.LayoutParams buttonParams = new FrameLayout.LayoutParams(-2,-2,android.view.Gravity.BOTTOM | android.view.Gravity.END);
        root.addView(pairing,buttonParams); pairing.setOnClickListener(v -> pairing());
        setContentView(root);
        link = new DesktopLink(this, new DesktopLink.Listener() {
            public void packet(JSONObject packet) {
                JSONObject update = packet.optJSONObject("face"); if (update != null) face.receive(update);
                switch (packet.optString("command")) {
                    case "wake": wake(); break;
                    case "sleep": voice.sleep(); break;
                }
            }
            public void status(String text, boolean connected) { connection.setText(text); if (!connected && voice != null && voice.isAwake()) voice.sleep(); }
            public void services(String[] names) { desktops = names; }
        });
        voice = new LiveVoice(this,link,new LiveVoice.Listener() {
            public void state(String text) { state.setText(text); }
            public void caption(String text) { caption.setText(text); }
            public void speaking(boolean active) { face.setSpeaking(active); }
        });
        GestureDetector gestures = new GestureDetector(this,new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) { return true; }
            @Override public boolean onDoubleTap(MotionEvent e) { handler.removeCallbacks(hold); if (voice.isAwake()) voice.sleep(); else wake(); return true; }
        });
        gestures.setIsLongpressEnabled(false);
        face.setOnTouchListener((v,event) -> {
            gestures.onTouchEvent(event);
            if (event.getActionMasked()==MotionEvent.ACTION_DOWN) handler.postDelayed(hold,300);
            if (event.getActionMasked()==MotionEvent.ACTION_UP || event.getActionMasked()==MotionEvent.ACTION_CANCEL) {
                handler.removeCallbacks(hold);
                if (holding) { holding=false; if (event.getActionMasked()==MotionEvent.ACTION_UP) voice.endAsk(); else voice.sleep(); }
                else if (event.getActionMasked()==MotionEvent.ACTION_UP) v.performClick();
            }
            return true;
        });
        LinearLayout actions = new LinearLayout(this);
        Button wakeButton = new Button(this); wakeButton.setText(R.string.wake_sleep);
        wakeButton.setOnClickListener(v -> { if (voice.isAwake()) voice.sleep(); else wake(); });
        Button askButton = new Button(this); askButton.setText(R.string.ask_now);
        askButton.setOnClickListener(v -> { if (voice.isAwake()) { voice.beginAsk(); voice.endAsk(); } else wake(); });
        actions.addView(wakeButton); actions.addView(askButton);
        Button testVoice = new Button(this); testVoice.setText("Test voice");
        testVoice.setOnClickListener(v -> voice.testSpeech()); actions.addView(testVoice);
        root.addView(actions, new FrameLayout.LayoutParams(-2,-2,android.view.Gravity.BOTTOM | android.view.Gravity.START));
        // Keep the face unobstructed like iPhone; explicit controls remain one tap away.
        actions.setVisibility(View.GONE); pairing.setVisibility(View.GONE);
        Button menu = new Button(this); menu.setText("\u2022\u2022\u2022");
        menu.setContentDescription("Show or hide Bluey controls");
        menu.setTextColor(Color.WHITE); menu.setBackgroundColor(Color.TRANSPARENT);
        root.addView(menu, new FrameLayout.LayoutParams(-2,-2,android.view.Gravity.TOP | android.view.Gravity.END));
        menu.setOnClickListener(v -> {
            int visibility = actions.getVisibility()==View.VISIBLE ? View.GONE : View.VISIBLE;
            actions.setVisibility(visibility); pairing.setVisibility(visibility);
        });
        WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
        if (wifi != null) { multicast=wifi.createMulticastLock("Bluey discovery"); multicast.setReferenceCounted(false); }
    }
    private TextView label(String text) {
        TextView view = new TextView(this); view.setText(text); view.setTextColor(Color.WHITE); view.setTextSize(11); view.setMaxLines(4); view.setMaxWidth(getResources().getDisplayMetrics().widthPixels-180); view.setShadowLayer(3,0,1,Color.BLACK); return view;
    }
    private void wake() {
        if (!resumed) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},1);
        else voice.wake();
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants) {
        super.onRequestPermissionsResult(code,permissions,grants);
        if (code==1 && grants.length>0 && grants[0]==PackageManager.PERMISSION_GRANTED && resumed) voice.wake();
        else if (code==1) caption.setText(R.string.microphone_denied);
    }
    private void pairing() {
        String[] options = new String[desktops.length+1];
        System.arraycopy(desktops,0,options,0,desktops.length); options[desktops.length]="Enter IP and port…";
        new AlertDialog.Builder(this).setTitle("Choose a trusted desktop on your Wi-Fi")
            .setItems(options,(dialog,index)-> {
                voice.sleep();
                if (index<desktops.length) link.choose(this,desktops[index]);
                else {
                    EditText input = new EditText(this); input.setHint("192.168.1.20:54321");
                    new AlertDialog.Builder(this).setTitle("Desktop IPv4 address and port").setView(input)
                        .setMessage("Pairing is unencrypted. Use trusted private networks only.")
                        .setPositiveButton("Connect",(d,w)-> {
                            try {
                                String value=input.getText().toString().trim(); int colon=value.lastIndexOf(':');
                                int port=Integer.parseInt(value.substring(colon+1));
                                if (colon<=0 || port<1 || port>65535) throw new IllegalArgumentException();
                                link.manual(value.substring(0,colon),port);
                            } catch (Exception e) { connection.setText(R.string.invalid_address); }
                        }).setNegativeButton("Cancel",null).show();
                }
            }).setNegativeButton("Cancel",null).show();
    }
    @Override protected void onResume() { super.onResume(); resumed=true; if(multicast!=null) multicast.acquire(); link.start(); }
    @Override protected void onPause() { resumed=false; handler.removeCallbacks(hold); holding=false; voice.sleep(); link.stop(); if(multicast!=null && multicast.isHeld()) multicast.release(); super.onPause(); }
    @Override protected void onDestroy() { voice.destroy(); link.destroy(); super.onDestroy(); }
}

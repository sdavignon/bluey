package co.visionairy.bluey;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/** Same _googly._tcp / newline JSON protocol as the Apple apps. Call public methods on UI thread. */
final class DesktopLink {
    interface Listener {
        void packet(JSONObject packet);
        void status(String text, boolean connected);
        void services(String[] names);
    }
    private final NsdManager nsd;
    private final Listener listener;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final ExecutorService writes = Executors.newSingleThreadExecutor();
    private final Map<String, NsdServiceInfo> services = new LinkedHashMap<>();
    private final Map<String, Consumer<JSONObject>> pending = new HashMap<>();
    private final ArrayDeque<NsdServiceInfo> resolveQueue = new ArrayDeque<>();
    private NsdManager.DiscoveryListener discovery;
    private volatile Socket socket;
    private boolean active, resolving, connecting, connected;
    private int generation, discoveryGeneration;
    private String preferred;
    private String current;

    DesktopLink(Context context, Listener listener) {
        nsd = (NsdManager) context.getSystemService(Context.NSD_SERVICE);
        this.listener = listener;
        preferred = context.getSharedPreferences("bluey", 0).getString("desktop", null);
    }
    void start() {
        if (active) return;
        active = true;
        int run = ++discoveryGeneration;
        discovery = new NsdManager.DiscoveryListener() {
            public void onDiscoveryStarted(String type) { ui.post(() -> { if (run == discoveryGeneration) listener.status("Looking for a desktop on this Wi-Fi…", false); }); }
            public void onServiceFound(NsdServiceInfo service) { ui.post(() -> { if (run == discoveryGeneration && active) { resolveQueue.add(service); resolveNext(run); } }); }
            public void onServiceLost(NsdServiceInfo service) { ui.post(() -> { if (run != discoveryGeneration) return; services.remove(service.getServiceName()); publishServices(); }); }
            public void onDiscoveryStopped(String type) {}
            public void onStartDiscoveryFailed(String type, int code) { ui.post(() -> { if (run == discoveryGeneration) { listener.status("Discovery failed. Use a desktop IP and port.", false); } }); }
            public void onStopDiscoveryFailed(String type, int code) {}
        };
        nsd.discoverServices("_googly._tcp.", NsdManager.PROTOCOL_DNS_SD, discovery);
    }
    @SuppressWarnings("deprecation")
    private void resolveNext(int run) {
        if (resolving || resolveQueue.isEmpty() || !active || run != discoveryGeneration) return;
        resolving = true;
        nsd.resolveService(resolveQueue.remove(), new NsdManager.ResolveListener() {
            public void onResolveFailed(NsdServiceInfo service, int code) { ui.post(() -> { if (run == discoveryGeneration) { resolving = false; resolveNext(run); } }); }
            public void onServiceResolved(NsdServiceInfo service) { ui.post(() -> {
                if (run != discoveryGeneration) return;
                resolving = false;
                services.put(service.getServiceName(), service);
                publishServices();
                connectBest();
                resolveNext(run);
            }); }
        });
    }
    private void publishServices() { listener.services(services.keySet().toArray(new String[0])); }
    void choose(Context context, String name) {
        preferred = name;
        context.getSharedPreferences("bluey", 0).edit().putString("desktop", name).apply();
        disconnect();
        connectBest();
    }
    private void connectBest() {
        if (!active || connected || connecting || services.isEmpty()) return;
        NsdServiceInfo target = preferred == null ? services.values().iterator().next() : services.get(preferred);
        if (target != null && target.getHost() != null) connect(target.getHost().getHostAddress(), target.getPort(), target.getServiceName());
    }
    void manual(String address, int port) {
        disconnect();
        active = true;
        connect(address, port, address);
    }
    private void connect(String address, int port, String name) {
        connecting = true;
        int run = generation;
        current = name;
        listener.status("Connecting to " + name + "…", false);
        io.execute(() -> {
            Socket candidate = new Socket();
            try {
                candidate.connect(new InetSocketAddress(address, port), 5000);
                candidate.setTcpNoDelay(true);
                synchronized (this) {
                    if (!active || run != generation) { candidate.close(); return; }
                    socket = candidate;
                }
                ui.post(() -> {
                    if (run != generation) return;
                    connected = true; connecting = false;
                    listener.status("Connected to " + name, true);
                    send(json("hello", Build.MODEL));
                });
                InputStream input = candidate.getInputStream();
                PacketFramer framer = new PacketFramer();
                byte[] chunk = new byte[65536];
                int count;
                while ((count = input.read(chunk)) != -1) {
                    for (String line : framer.feed(chunk, count)) {
                        try {
                            JSONObject packet = new JSONObject(line);
                            ui.post(() -> { if (run == generation) receive(packet); });
                        } catch (Exception ignored) {}
                    }
                }
            } catch (Exception ignored) {
            } finally {
                try { candidate.close(); } catch (Exception ignored) {}
                ui.post(() -> {
                    if (run != generation) return;
                    disconnect();
                    listener.status("Desktop disconnected. Retrying…", false);
                    int retryRun = generation;
                    ui.postDelayed(() -> {
                        if (!active || retryRun != generation || connected || connecting) return;
                        if (services.containsKey(current)) connectBest();
                        else if (name.equals(address)) connect(address, port, name);
                    }, 1500);
                });
            }
        });
    }
    private void receive(JSONObject packet) {
        String id = packet.optString("callID");
        Consumer<JSONObject> callback = pending.remove(id);
        if (callback != null) callback.accept(packet);
        else listener.packet(packet);
    }
    void send(JSONObject packet) {
        Socket target = socket;
        if (target == null) return;
        writes.execute(() -> {
            try {
                byte[] data = (packet.toString() + "\n").getBytes(StandardCharsets.UTF_8);
                OutputStream out = target.getOutputStream();
                out.write(data); out.flush();
            } catch (Exception ignored) { try { target.close(); } catch (Exception ignoredAgain) {} }
        });
    }
    void request(JSONObject packet, Consumer<JSONObject> callback) {
        if (!connected) { callback.accept(null); return; }
        String id = UUID.randomUUID().toString();
        put(packet, "callID", id);
        pending.put(id, callback);
        send(packet);
        ui.postDelayed(() -> { Consumer<JSONObject> cb = pending.remove(id); if (cb != null) cb.accept(null); }, packet.optString("command").equals("tool") ? 75000 : 35000);
    }
    private synchronized void disconnect() {
        generation++;
        connected = connecting = false;
        Socket old = socket; socket = null;
        if (old != null) try { old.close(); } catch (Exception ignored) {}
        java.util.List<Consumer<JSONObject>> callbacks = new java.util.ArrayList<>(pending.values());
        pending.clear();
        for (Consumer<JSONObject> cb : callbacks) cb.accept(null);
    }
    void stop() {
        active = false;
        discoveryGeneration++;
        disconnect();
        if (discovery != null) try { nsd.stopServiceDiscovery(discovery); } catch (Exception ignored) {}
        discovery = null;
        resolving = false; resolveQueue.clear(); services.clear();
        publishServices();
    }
    void destroy() { stop(); io.shutdownNow(); writes.shutdownNow(); }
    static JSONObject json(String key, Object value) { JSONObject obj = new JSONObject(); put(obj, key, value); return obj; }
    static void put(JSONObject obj, String key, Object value) { try { obj.put(key, value); } catch (Exception e) { throw new IllegalArgumentException(e); } }
}

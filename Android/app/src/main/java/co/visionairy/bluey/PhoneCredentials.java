package co.visionairy.bluey;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** The app-private preference contains ciphertext only; the wrapping key never leaves Android Keystore. */
final class PhoneCredentials {
    private static final String ALIAS = "Bluey.OpenAI.v1";
    private final SharedPreferences preferences;
    PhoneCredentials(Context context) { preferences = context.getSharedPreferences("bluey_voice", Context.MODE_PRIVATE); }
    boolean phoneMode() { return preferences.getBoolean("phone_mode", true); }
    boolean spokenReplies() { return preferences.getBoolean("spoken_replies", true); }
    void configure(boolean phone, boolean spoken) { preferences.edit().putBoolean("phone_mode", phone).putBoolean("spoken_replies", spoken).apply(); }
    private SecretKey wrappingKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (store.containsAlias(ALIAS)) return ((KeyStore.SecretKeyEntry) store.getEntry(ALIAS, null)).getSecretKey();
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }
    void save(String key) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, wrappingKey());
        byte[] encrypted = cipher.doFinal(key.trim().getBytes(StandardCharsets.UTF_8));
        if (!preferences.edit().putString("key_ciphertext", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString("key_iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)).commit())
            throw new java.io.IOException("Key storage failed");
    }
    String read() throws Exception {
        String encrypted = preferences.getString("key_ciphertext", "");
        if (encrypted.isEmpty()) return "";
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, wrappingKey(), new GCMParameterSpec(128, Base64.decode(preferences.getString("key_iv", ""), Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }
    void remove() { preferences.edit().remove("key_ciphertext").remove("key_iv").apply(); }
}

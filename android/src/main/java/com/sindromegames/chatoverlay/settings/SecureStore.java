package com.sindromegames.chatoverlay.settings;

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

public final class SecureStore {
    private static final String KEY_ALIAS = "sindrome.youtube.api.key";
    private static final String PREFS = "secure";
    private static final String VALUE = "youtube_api_key";
    private static final String IV = "youtube_api_key_iv";
    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";

    private final SharedPreferences preferences;

    public SecureStore(Context context) {
        preferences = context.getApplicationContext()
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized String readApiKey() {
        String encrypted = preferences.getString(VALUE, "");
        String iv = preferences.getString(IV, "");
        if (encrypted == null || encrypted.isEmpty() || iv == null || iv.isEmpty()) return "";
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(),
                    new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
            byte[] clear = cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP));
            return new String(clear, StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    public synchronized void writeApiKey(String rawValue) throws Exception {
        String value = rawValue == null ? "" : rawValue.trim();
        if (value.isEmpty()) {
            preferences.edit().remove(VALUE).remove(IV).apply();
            return;
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        preferences.edit()
                .putString(VALUE, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .apply();
    }

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore store = KeyStore.getInstance(ANDROID_KEYSTORE);
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) store.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,
                ANDROID_KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return generator.generateKey();
    }
}


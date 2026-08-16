package org.yugioh.kartenliste;

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

/** Hardware-backed secret storage for optional cloud API credentials. */
public final class SecureSecretStore {
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "JustInCard.v12.CloudSecret";
    private static final String PREFS = "just_incard_secure_v12";

    private SecureSecretStore() {}

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance(KEYSTORE);
        store.load(null);
        if (store.containsAlias(ALIAS)) {
            return (SecretKey) store.getKey(ALIAS, null);
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    public static synchronized boolean put(Context context, String name, String value) {
        if (context == null || name == null) return false;
        if (value == null || value.isEmpty()) {
            delete(context, name);
            return true;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key());
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            return prefs(context).edit()
                    .putString(name + ".iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                    .putString(name + ".data", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                    .commit();
        } catch (Throwable error) {
            return false;
        }
    }

    public static synchronized String get(Context context, String name) {
        if (context == null || name == null) return "";
        try {
            String ivValue = prefs(context).getString(name + ".iv", "");
            String dataValue = prefs(context).getString(name + ".data", "");
            if (ivValue == null || ivValue.isEmpty() || dataValue == null || dataValue.isEmpty()) return "";
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(
                    Cipher.DECRYPT_MODE,
                    key(),
                    new GCMParameterSpec(128, Base64.decode(ivValue, Base64.NO_WRAP))
            );
            byte[] plain = cipher.doFinal(Base64.decode(dataValue, Base64.NO_WRAP));
            return new String(plain, StandardCharsets.UTF_8);
        } catch (Throwable error) {
            // A lock-screen change or restored app data can invalidate a hardware
            // key. Never crash startup; discard only the unreadable secret.
            delete(context, name);
            return "";
        }
    }

    public static synchronized boolean delete(Context context, String name) {
        if (context == null || name == null) return false;
        return prefs(context).edit().remove(name + ".iv").remove(name + ".data").commit();
    }
}

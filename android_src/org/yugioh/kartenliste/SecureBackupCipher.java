package org.yugioh.kartenliste;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.File;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.CipherInputStream;
import javax.crypto.CipherOutputStream;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Device-bound AES-GCM backup encryption using Android Keystore. */
public final class SecureBackupCipher {
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "JustInCard.v12.DeviceBackup";
    private static final int MAGIC = 0x4A494331; // JIC1

    private SecureBackupCipher() {}

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance(KEYSTORE);
        store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    public static boolean encrypt(Context context, String inputPath, String outputPath) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key());
            try (BufferedInputStream input = new BufferedInputStream(new FileInputStream(inputPath));
                 DataOutputStream header = new DataOutputStream(new BufferedOutputStream(new FileOutputStream(outputPath)))) {
                byte[] iv = cipher.getIV();
                header.writeInt(MAGIC);
                header.writeInt(iv.length);
                header.write(iv);
                header.flush();
                try (CipherOutputStream encrypted = new CipherOutputStream(header, cipher)) {
                    copy(input, encrypted);
                }
            }
            return true;
        } catch (Throwable error) {
            try { new File(outputPath).delete(); } catch (Throwable ignored) {}
            return false;
        }
    }

    public static boolean decrypt(Context context, String inputPath, String outputPath) {
        try (DataInputStream input = new DataInputStream(new BufferedInputStream(new FileInputStream(inputPath)))) {
            if (input.readInt() != MAGIC) return false;
            int ivLength = input.readInt();
            if (ivLength < 12 || ivLength > 32) return false;
            byte[] iv = new byte[ivLength];
            input.readFully(iv);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            try (CipherInputStream decrypted = new CipherInputStream(input, cipher);
                 BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(outputPath))) {
                copy(decrypted, output);
            }
            return true;
        } catch (Throwable error) {
            try { new File(outputPath).delete(); } catch (Throwable ignored) {}
            return false;
        }
    }

    private static void copy(java.io.InputStream input, java.io.OutputStream output) throws Exception {
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) >= 0) {
            if (count > 0) output.write(buffer, 0, count);
        }
        output.flush();
    }
}

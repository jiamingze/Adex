package io.adex.app.security;

import io.adex.kernel.Kernel;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import javax.crypto.Cipher;
import javax.crypto.spec.*;

/** External 256-bit key; per-object AAD prevents moving tokens between owners/devices. */
public final class SecretEnvelope {
  private final byte[] key;

  public SecretEnvelope(byte[] key) {
    if (key.length != 32) throw new IllegalArgumentException("INVALID_ENCRYPTION_KEY");
    this.key = key.clone();
  }

  public static SecretEnvelope push() {
    try {
      return new SecretEnvelope(
          Base64.getDecoder().decode(Kernel.env("ADEX_APNS_DEVICE_ENCRYPTION_KEY", "")));
    } catch (Exception e) {
      throw Kernel.error(503, "BLOCKED_EXTERNAL");
    }
  }

  public String seal(String value, String aad) {
    try {
      byte[] nonce = new byte[12];
      new SecureRandom().nextBytes(nonce);
      byte[] cipher =
          crypt(Cipher.ENCRYPT_MODE, value.getBytes(StandardCharsets.UTF_8), nonce, aad);
      byte[] result = new byte[nonce.length + cipher.length];
      System.arraycopy(nonce, 0, result, 0, 12);
      System.arraycopy(cipher, 0, result, 12, cipher.length);
      return "v1." + Base64.getUrlEncoder().encodeToString(result);
    } catch (Exception e) {
      throw Kernel.error(503, "CREDENTIAL_UNAVAILABLE");
    }
  }

  public String open(String value, String aad) {
    try {
      if (!value.startsWith("v1.")) throw new IllegalArgumentException();
      byte[] raw = Base64.getUrlDecoder().decode(value.substring(3));
      return new String(
          crypt(
              Cipher.DECRYPT_MODE,
              Arrays.copyOfRange(raw, 12, raw.length),
              Arrays.copyOf(raw, 12),
              aad),
          StandardCharsets.UTF_8);
    } catch (Exception e) {
      throw Kernel.error(503, "CREDENTIAL_UNAVAILABLE");
    }
  }

  private byte[] crypt(int mode, byte[] value, byte[] nonce, String aad) throws Exception {
    var cipher = Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(mode, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, nonce));
    cipher.updateAAD(aad.getBytes(StandardCharsets.UTF_8));
    return cipher.doFinal(value);
  }
}

import React, { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { Colors, Space, Type } from '../../utils/theme';
import { User } from '../../types';
import { authApi, describeApiError } from '../../services/auth';
import { isGoogleAuthAvailable, requestGoogleIdToken } from '../../services/googleAuth';
import { describeGoogleError } from '../../utils/googleError';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Sheet } from '../ui/Sheet';

interface LinkGoogleSheetProps {
  visible: boolean;
  onClose: () => void;
  onLinked: (user: User) => void;
}

/**
 * Explicit Google linking for an existing password account.
 *
 * The password is collected first because the backend requires it: a stolen
 * access token alone must not be able to bind an attacker's Google account.
 */
export function LinkGoogleSheet({ visible, onClose, onLinked }: LinkGoogleSheetProps) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setPassword('');
    setLoading(false);
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const handleLink = async () => {
    if (loading) return;
    if (!password) {
      setError('Masukkan kata sandi akun kamu.');
      return;
    }
    setLoading(true);
    setError(null);

    let idToken: string | null = null;
    try {
      const available = await isGoogleAuthAvailable();
      if (!available) {
        throw new Error('GOOGLE_UNAVAILABLE');
      }
      idToken = await requestGoogleIdToken();
      if (!idToken) {
        // Cancelled in the Google sheet; keep the password field as-is.
        return;
      }
      const user = await authApi.linkGoogle({ idToken, password });
      reset();
      onLinked(user);
    } catch (err) {
      setError(
        describeGoogleError(err) ?? describeApiError(err, 'Gagal menautkan Google. Coba lagi.')
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Sheet
      visible={visible}
      onClose={close}
      title="Tautkan Google"
      footer={
        <>
          <Button title="Tautkan Google" loading={loading} onPress={handleLink} size="lg" />
          <Button title="Batal" variant="ghost" onPress={close} disabled={loading} />
        </>
      }
    >
      <Text style={styles.body}>
        Masukkan kata sandi akun ini, lalu pilih akun Google dengan email yang sama.
        Setelah tertaut, kamu bisa masuk lewat Google.
      </Text>

      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : null}

      <View style={styles.field}>
        <Input
          label="Kata sandi"
          placeholder="Kata sandi akun kamu"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="password"
          textContentType="password"
        />
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  body: {
    ...Type.body,
    color: Colors.inkSoft,
    marginBottom: Space.lg,
  },
  error: {
    ...Type.caption,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  field: {
    marginBottom: Space.sm,
  },
});

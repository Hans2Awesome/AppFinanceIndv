import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Colors, Space, Type } from '../../utils/theme';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { authApi, describeApiError } from '../../services/auth';
import { GoogleAuthAction } from '../../components/auth/GoogleAuthAction';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    if (loading || googleBusy) return;
    if (!email || !password) {
      setError('Harap isi email dan password.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await authApi.login({ email, password });
      router.replace('/(tabs)');
    } catch (err) {
      setError(describeApiError(err, 'Gagal masuk. Periksa email dan password.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen contentStyle={styles.scroll} keyboardBehavior="padding">
      <View style={styles.brand}>
        <Text style={styles.wordmark}>Bot04</Text>
        <View style={styles.brandRule} />
        <Text style={styles.tagline}>Buku kas pribadi</Text>
      </View>

      <View style={styles.form}>
        <Text style={styles.title}>Masuk</Text>

        {error ? (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {error}
          </Text>
        ) : null}

        <Input
          label="Email"
          placeholder="nama@email.com"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          textContentType="emailAddress"
          keyboardType="email-address"
          returnKeyType="next"
        />

        <Input
          label="Password"
          placeholder="Password kamu"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="password"
          textContentType="password"
          returnKeyType="done"
          onSubmitEditing={handleLogin}
        />

        <Button
          title="Masuk"
          loading={loading}
          onPress={handleLogin}
          size="lg"
          disabled={googleBusy}
        />

        <GoogleAuthAction
          disabled={loading}
          onBusyChange={setGoogleBusy}
          onError={(message) => setError(message)}
        />

        <View style={styles.footer}>
          <Text style={styles.footerText}>Belum punya akun?</Text>
          <Pressable
            onPress={() => router.push('/(auth)/register')}
            hitSlop={10}
            style={styles.linkTap}
            accessibilityRole="link"
            accessibilityLabel="Daftar akun baru"
          >
            <Text style={styles.link}>Daftar</Text>
          </Pressable>
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingTop: Space.xxl,
    paddingBottom: Space.xxl,
  },
  brand: {
    alignItems: 'center',
    marginBottom: Space.xxl,
    gap: Space.sm,
  },
  wordmark: {
    ...Type.h1,
    fontSize: 44,
    lineHeight: 48,
  },
  brandRule: {
    width: 28,
    height: 1,
    backgroundColor: Colors.lineStrong,
  },
  tagline: {
    ...Type.micro,
    textTransform: 'uppercase',
  },
  form: {
    gap: 0,
  },
  title: {
    ...Type.h2,
    marginBottom: Space.lg,
  },
  error: {
    ...Type.caption,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: Space.sm,
    marginTop: Space.xl,
  },
  footerText: {
    ...Type.caption,
  },
  linkTap: {
    minHeight: 44,
    justifyContent: 'center',
  },
  link: {
    ...Type.caption,
    color: Colors.ink,
    textDecorationLine: 'underline',
  },
});

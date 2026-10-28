import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Colors, Space, Type } from '../../utils/theme';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { authApi, describeApiError } from '../../services/auth';

export default function RegisterScreen() {
  const [firstName, setFirstName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async () => {
    if (!email || !password) {
      setError('Harap isi email dan password.');
      return;
    }
    if (password.length < 6) {
      setError('Password minimal 6 karakter.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await authApi.register({
        email,
        password,
        first_name: firstName || undefined,
      });
      router.replace('/(tabs)');
    } catch (err) {
      setError(describeApiError(err, 'Gagal mendaftar. Silakan coba lagi.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.flex}
    >
      <Screen contentStyle={styles.scroll}>
        <View style={styles.brand}>
          <Text style={styles.wordmark}>Bot04</Text>
          <View style={styles.brandRule} />
          <Text style={styles.tagline}>Buku kas pribadi</Text>
        </View>

        <View>
          <Text style={styles.title}>Buat akun</Text>

          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}

          <Input
            label="Nama"
            placeholder="Nama panggilan"
            value={firstName}
            onChangeText={setFirstName}
            autoCapitalize="words"
            textContentType="givenName"
            returnKeyType="next"
          />

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
            placeholder="Minimal 6 karakter"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            hint="Minimal 6 karakter"
            returnKeyType="done"
            onSubmitEditing={handleRegister}
          />

          <Button title="Daftar" loading={loading} onPress={handleRegister} size="lg" />

          <View style={styles.footer}>
            <Text style={styles.footerText}>Sudah punya akun?</Text>
            <Pressable
              onPress={() => router.push('/(auth)/login')}
              hitSlop={10}
              style={styles.linkTap}
              accessibilityRole="link"
              accessibilityLabel="Masuk ke akun"
            >
              <Text style={styles.link}>Masuk</Text>
            </Pressable>
          </View>
        </View>
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
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
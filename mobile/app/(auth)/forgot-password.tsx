import React, { useCallback, useState } from 'react';
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { AxiosError } from 'axios';
import { Colors, Space, Type } from '../../utils/theme';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { authApi, describeApiError } from '../../services/auth';
import { validateNewPassword } from '../../utils/password';

type Step = 'request' | 'reset';

export default function ForgotPasswordScreen() {
  const [step, setStep] = useState<Step>('request');
  const [email, setEmail] = useState('');
  const [requestId, setRequestId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearSecrets = useCallback(() => {
    setCode('');
    setNewPassword('');
    setConfirmPassword('');
  }, []);

  useFocusEffect(
    useCallback(() => {
      return () => {
        clearSecrets();
      };
    }, [clearSecrets])
  );

  const handleBackToLogin = () => {
    clearSecrets();
    router.replace('/(auth)/login');
  };

  const handleRequestCode = async () => {
    if (loading || resending) return;
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError('Please enter your account email address.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.forgotPassword({ email: trimmedEmail });
      setRequestId(res.request_id);
      setStatusMessage(
        res.message ||
          'If an account with a password exists for that email, a 6-digit recovery code has been sent.'
      );
      clearSecrets();
      setStep('reset');
    } catch (err) {
      const status = (err as AxiosError).response?.status;
      if (status === 503) {
        setError(
          describeApiError(
            err,
            'Password recovery email service is currently unavailable. Please try again later.'
          )
        );
      } else {
        setError(describeApiError(err, 'Unable to request a recovery code. Please try again.'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (loading || resending) return;
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setStep('request');
      return;
    }
    setResending(true);
    setError(null);
    try {
      const res = await authApi.forgotPassword({ email: trimmedEmail });
      setRequestId(res.request_id);
      setCode('');
      setStatusMessage(
        res.message ||
          'A new recovery request has been issued. Previous codes are no longer valid.'
      );
    } catch (err) {
      const status = (err as AxiosError).response?.status;
      if (status === 503) {
        setError(
          describeApiError(
            err,
            'Password recovery email service is currently unavailable. Please try again later.'
          )
        );
      } else {
        setError(describeApiError(err, 'Unable to resend code. Please try again.'));
      }
    } finally {
      setResending(false);
    }
  };

  const handleResetPassword = async () => {
    if (loading || resending) return;
    if (!requestId) {
      setError('Missing recovery request. Please request a new code.');
      setStep('request');
      return;
    }
    const normalizedCode = code.trim();
    if (!/^\d{6}$/.test(normalizedCode)) {
      setError('Enter the 6-digit code sent to your email.');
      return;
    }
    const passwordError = validateNewPassword(newPassword);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await authApi.resetPassword({
        request_id: requestId,
        code: normalizedCode,
        new_password: newPassword,
      });
      clearSecrets();
      setRequestId(null);
      Alert.alert(
        'Password reset',
        res.message || 'Your password has been updated. Sign in with your new password.'
      );
      router.replace('/(auth)/login');
    } catch (err) {
      setError(
        describeApiError(
          err,
          'Invalid or expired recovery code. Check the code or request a new one.'
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen contentStyle={styles.scroll} bottomInset keyboardBehavior="padding">
      <View style={styles.brand}>
        <Text style={styles.wordmark}>Bot04</Text>
        <View style={styles.brandRule} />
        <Text style={styles.tagline}>Account recovery</Text>
      </View>

      {step === 'request' ? (
        <View style={styles.form}>
          <Text style={styles.title}>Forgot password</Text>
          <Text style={styles.subtitle}>
            Enter the email address for your account. If it uses a password, we will send a
            6-digit recovery code valid for 10 minutes.
          </Text>

          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}

          <Input
            label="Email"
            placeholder="name@example.com"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            keyboardType="email-address"
            returnKeyType="send"
            onSubmitEditing={handleRequestCode}
            accessibilityLabel="Account email"
          />

          <Button
            title="Send recovery code"
            loading={loading}
            onPress={handleRequestCode}
            size="lg"
          />

          <View style={styles.footer}>
            <Pressable
              onPress={handleBackToLogin}
              hitSlop={10}
              style={styles.linkTap}
              accessibilityRole="link"
              accessibilityLabel="Back to sign in"
            >
              <Text style={styles.link}>Back to sign in</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <View style={styles.form}>
          <Text style={styles.title}>Reset password</Text>
          <Text style={styles.subtitle}>
            {statusMessage ||
              'Enter the 6-digit code from your email and choose a new password. Code expires in 10 minutes.'}
          </Text>

          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}

          <Input
            label="6-digit code"
            placeholder="000000"
            value={code}
            onChangeText={(val) => setCode(val.replace(/\D/g, '').slice(0, 6))}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            maxLength={6}
            returnKeyType="next"
            accessibilityLabel="6-digit recovery code"
          />

          <Input
            label="New password"
            placeholder="At least 8 characters"
            value={newPassword}
            onChangeText={setNewPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            hint="8 characters minimum, up to 72 UTF-8 bytes"
            returnKeyType="next"
            accessibilityLabel="New password"
          />

          <Input
            label="Confirm new password"
            placeholder="Repeat new password"
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            returnKeyType="done"
            onSubmitEditing={handleResetPassword}
            accessibilityLabel="Confirm new password"
          />

          <Button
            title="Reset password"
            loading={loading}
            disabled={resending}
            onPress={handleResetPassword}
            size="lg"
          />

          <Button
            title="Resend code"
            variant="secondary"
            loading={resending}
            disabled={loading}
            onPress={handleResendCode}
            style={styles.secondaryAction}
          />

          <View style={styles.footer}>
            <Pressable
            disabled={loading || resending}
            onPress={() => {
                clearSecrets();
                setError(null);
                setStep('request');
              }}
              hitSlop={10}
              style={styles.linkTap}
            accessibilityRole="button"
            accessibilityState={{ disabled: loading || resending }}
              accessibilityLabel="Use a different email"
            >
              <Text style={styles.link}>Use a different email</Text>
            </Pressable>
            <Text style={styles.footerDot}>·</Text>
            <Pressable
              onPress={handleBackToLogin}
              hitSlop={10}
              style={styles.linkTap}
              accessibilityRole="link"
              accessibilityLabel="Back to sign in"
            >
              <Text style={styles.link}>Back to sign in</Text>
            </Pressable>
          </View>
        </View>
      )}
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
    marginBottom: Space.xs,
  },
  subtitle: {
    ...Type.body,
    color: Colors.inkSoft,
    marginBottom: Space.lg,
  },
  error: {
    ...Type.caption,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  secondaryAction: {
    marginTop: Space.sm,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: Space.sm,
    marginTop: Space.xl,
  },
  footerDot: {
    ...Type.caption,
    color: Colors.inkMuted,
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

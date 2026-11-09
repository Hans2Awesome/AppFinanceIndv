import { AppAlert as Alert } from '../services/appAlert';
import React, { useCallback, useEffect, useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Space, Type } from '../utils/theme';
import { User } from '../types';
import { authApi, describeApiError } from '../services/auth';
import { validateNewPassword } from '../utils/password';
import { Screen } from '../components/ui/Screen';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { SkeletonRows } from '../components/ui/Skeleton';

export default function ChangePasswordScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearSecrets = useCallback(() => {
    setCurrentPassword('');
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

  const loadProfile = useCallback(async () => {
    try {
      setUser(await authApi.getProfile());
      setProfileError(null);
    } catch (err) {
      setProfileError(describeApiError(err, 'Unable to load account details.'));
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleBack = () => {
    clearSecrets();
    router.back();
  };

  const handleChangePassword = async () => {
    if (loading || !user?.has_password) return;
    if (!currentPassword) {
      setError('Enter your current password.');
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
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      clearSecrets();
      Alert.alert(
        'Password updated',
        'Your password has been changed and other active sessions have been signed out.'
      );
      router.back();
    } catch (err) {
      setError(
        describeApiError(err, 'Unable to update password. Check your current password and try again.')
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen bottomInset keyboardBehavior="padding">
      <View style={styles.header}>
        <Pressable
          onPress={handleBack}
          hitSlop={8}
          style={styles.back}
          accessibilityRole="button"
          accessibilityLabel="Back"
        >
          <Ionicons name="arrow-back" size={20} color={Colors.ink} />
        </Pressable>
        <Text style={styles.title}>Change password</Text>
      </View>

      {profileError ? <ErrorState message={profileError} onRetry={loadProfile} /> : null}

      {user === null && !profileError ? (
        <View style={styles.loadingBlock}>
          <SkeletonRows count={3} />
        </View>
      ) : user && !user.has_password ? (
        <View style={styles.noticeBlock}>
          <View style={styles.noticeHeader}>
            <Ionicons name="logo-google" size={18} color={Colors.inkSoft} />
            <Text style={styles.noticeTitle}>Managed by Google</Text>
          </View>
          <Text style={styles.noticeBody}>
            This account signs in with Google only and does not have a separate Bot04 password.
            Google manages your password and sign-in security in your Google Account settings.
          </Text>
          <Button
            title="Back to settings"
            variant="secondary"
            onPress={handleBack}
            style={styles.noticeButton}
          />
        </View>
      ) : user ? (
        <View style={styles.form}>
          <Text style={styles.intro}>
            Updating your password keeps this device signed in and revokes any other active
            sessions or pending recovery codes.
          </Text>

          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}

          <Input
            label="Current password"
            placeholder="Your current password"
            value={currentPassword}
            onChangeText={setCurrentPassword}
            secureTextEntry
            autoComplete="password"
            textContentType="password"
            returnKeyType="next"
            accessibilityLabel="Current password"
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
            onSubmitEditing={handleChangePassword}
            accessibilityLabel="Confirm new password"
          />

          <Button
            title="Update password"
            loading={loading}
            onPress={handleChangePassword}
            size="lg"
          />
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginBottom: Space.md,
  },
  back: {
    width: 44,
    height: 44,
    alignItems: 'flex-start',
    justifyContent: 'center',
    marginLeft: -Space.sm,
  },
  title: {
    ...Type.h2,
  },
  loadingBlock: {
    paddingTop: Space.lg,
  },
  intro: {
    ...Type.body,
    color: Colors.inkSoft,
    marginBottom: Space.lg,
  },
  form: {
    gap: 0,
  },
  error: {
    ...Type.caption,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  noticeBlock: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.block,
    padding: Space.lg,
    gap: Space.md,
  },
  noticeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
  },
  noticeTitle: {
    ...Type.title,
  },
  noticeBody: {
    ...Type.body,
    color: Colors.inkSoft,
  },
  noticeButton: {
    marginTop: Space.xs,
  },
});

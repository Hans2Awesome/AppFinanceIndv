import React, { useCallback, useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { authApi, describeApiError } from '../../services/auth';
import { isGoogleAuthAvailable, requestGoogleIdToken } from '../../services/googleAuth';
import { describeGoogleError } from '../../utils/googleError';
import { GoogleSeparator, GoogleSignInButton } from '../auth/GoogleSignInButton';

interface GoogleAuthActionProps {
  /** Called after a successful Google exchange once tokens are stored. */
  onSuccess?: () => void;
  /** Called with a message when Google reports a non-cancellation failure. */
  onError?: (message: string) => void;
  /** Disables the button while the email form is submitting. */
  disabled?: boolean;
  /** Reports the native flow so the email form can disable its own submit. */
  onBusyChange?: (busy: boolean) => void;
  separatorLabel?: string;
}

/**
 * Shared Google sign-in block for the auth screens.
 *
 * Owns availability detection, the native request, the backend exchange, and the
 * single-flight guard so a double tap cannot run two native flows. Screens only
 * decide where the block renders and how success navigates.
 */
export function GoogleAuthAction({
  onSuccess,
  onError,
  disabled = false,
  onBusyChange,
  separatorLabel = 'atau',
}: GoogleAuthActionProps) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    let active = true;
    isGoogleAuthAvailable().then((ok) => {
      if (active) setAvailable(ok);
    });
    return () => {
      active = false;
    };
  }, []);

  const handlePress = useCallback(async () => {
    if (loading || disabled) return;
    setLoading(true);
    onBusyChange?.(true);
    try {
      const idToken = await requestGoogleIdToken();
      if (!idToken) {
        // User cancelled the Google sheet; leave the screen as it was.
        return;
      }
      await authApi.googleLogin({ idToken });
      if (onSuccess) {
        onSuccess();
      } else {
        router.replace('/(tabs)');
      }
    } catch (err) {
      const message = describeApiError(err, 'Gagal masuk dengan Google. Coba lagi.');
      if (onError) {
        onError(describeGoogleError(err) ?? message);
      } else {
        Alert.alert('Gagal masuk dengan Google', describeGoogleError(err) ?? message);
      }
    } finally {
      setLoading(false);
      onBusyChange?.(false);
    }
  }, [disabled, loading, onBusyChange, onError, onSuccess]);

  if (available !== true) {
    return null;
  }

  return (
    <>
      <GoogleSeparator label={separatorLabel} />
      <GoogleSignInButton
        title="Lanjut dengan Google"
        onPress={handlePress}
        loading={loading}
        disabled={disabled}
      />
    </>
  );
}

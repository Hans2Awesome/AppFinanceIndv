import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  ActivityIndicator,
  Alert,
  AppState,
  AppStateStatus,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space, Type } from '../../utils/theme';
import { Screen } from '../ui/Screen';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { PatternInput } from './PatternInput';
import { isValidLockPattern } from '../../utils/lockPattern';
import {
  getAppLockState,
  getBiometricAvailability,
  hydrateAppLock,
  subscribeAppLock,
  unlockWithBiometrics,
  unlockWithPattern,
  unlockWithPin,
} from '../../services/appLock';

export interface AppLockViewProps {
  onSignOut: () => Promise<void>;
}

type UnlockMethod = 'pin' | 'pattern';

const PIN_PATTERN = /^[0-9]{6}$/;

function sanitizePinInput(value: string): string {
  return value.replace(/[^0-9]/g, '').slice(0, 6);
}

export function AppLockView({ onSignOut }: AppLockViewProps) {
  const lockState = useSyncExternalStore(
    subscribeAppLock,
    getAppLockState,
    getAppLockState
  );

  const [pin, setPin] = useState('');
  const [pattern, setPattern] = useState<number[]>([]);
  const [unlockMethod, setUnlockMethod] = useState<UnlockMethod>('pin');
  const [localError, setLocalError] = useState<string | null>(null);
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [retryingBoot, setRetryingBoot] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const pinRef = useRef('');
  const patternRef = useRef<number[]>([]);
  const mountedRef = useRef(true);
  const actionLockRef = useRef(false);

  const updatePin = useCallback((next: string) => {
    const clean = sanitizePinInput(next);
    pinRef.current = clean;
    setPin(clean);
  }, []);

  const updatePattern = useCallback((next: number[]) => {
    patternRef.current = next;
    setPattern(next);
  }, []);

  const clearPinFields = useCallback(() => {
    pinRef.current = '';
    patternRef.current = [];
    setPin('');
    setPattern([]);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      pinRef.current = '';
      patternRef.current = [];
    };
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      if (nextState === 'background' || nextState === 'inactive') {
        pinRef.current = '';
        patternRef.current = [];
        setPin('');
        setPattern([]);
        setUnlockMethod('pin');
        setLocalError(null);
      }
    });
    return () => {
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (lockState.covered || !lockState.locked || !lockState.ready) {
      clearPinFields();
      setUnlockMethod('pin');
      setLocalError(null);
    }
  }, [lockState.covered, lockState.locked, lockState.ready, clearPinFields]);

  useEffect(() => {
    if (!lockState.patternEnabled && unlockMethod === 'pattern') {
      patternRef.current = [];
      setPattern([]);
      setUnlockMethod('pin');
    }
  }, [lockState.patternEnabled, unlockMethod]);

  useEffect(() => {
    let active = true;
    if (!lockState.ready || !lockState.enabled || !lockState.biometricsEnabled) {
      setBiometricAvailable(false);
      return () => {
        active = false;
      };
    }

    getBiometricAvailability()
      .then((available) => {
        if (active && mountedRef.current) {
          setBiometricAvailable(Boolean(available));
        }
      })
      .catch(() => {
        if (active && mountedRef.current) {
          setBiometricAvailable(false);
        }
      });

    return () => {
      active = false;
    };
  }, [lockState.ready, lockState.enabled, lockState.biometricsEnabled]);

  useEffect(() => {
    if (!lockState.retryAt || lockState.retryAt <= Date.now()) {
      return;
    }
    setNowMs(Date.now());
    const interval = setInterval(() => {
      const current = Date.now();
      setNowMs(current);
      if (current >= lockState.retryAt) {
        clearInterval(interval);
      }
    }, 1000);
    return () => {
      clearInterval(interval);
    };
  }, [lockState.retryAt]);

  const cooldownSeconds =
    lockState.retryAt > nowMs ? Math.ceil((lockState.retryAt - nowMs) / 1000) : 0;
  const inCooldown = cooldownSeconds > 0;

  useEffect(() => {
    if (inCooldown) {
      clearPinFields();
    }
  }, [inCooldown, clearPinFields]);

  const isBusy = lockState.busy || signingOut || retryingBoot;

  const handlePinUnlock = async () => {
    if (actionLockRef.current || isBusy || inCooldown) {
      return;
    }
    const candidate = pinRef.current;
    if (!PIN_PATTERN.test(candidate)) {
      setLocalError('Masukkan PIN 6 digit.');
      return;
    }

    actionLockRef.current = true;
    setLocalError(null);
    try {
      const unlocked = await unlockWithPin(candidate);
      if (mountedRef.current) {
        clearPinFields();
        if (!unlocked) {
          setNowMs(Date.now());
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        clearPinFields();
        setNowMs(Date.now());
        setLocalError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal membuka kunci aplikasi. Coba lagi.'
        );
      }
    } finally {
      actionLockRef.current = false;
    }
  };

  const handlePatternUnlock = async () => {
    if (actionLockRef.current || isBusy || inCooldown || !lockState.patternEnabled) {
      return;
    }
    const candidate = patternRef.current;
    if (!isValidLockPattern(candidate)) {
      setLocalError('Hubungkan minimal 4 titik untuk membuka kunci.');
      return;
    }

    actionLockRef.current = true;
    setLocalError(null);
    try {
      const unlocked = await unlockWithPattern(candidate);
      if (mountedRef.current) {
        clearPinFields();
        if (!unlocked) {
          setNowMs(Date.now());
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        clearPinFields();
        setNowMs(Date.now());
        setLocalError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal membuka kunci aplikasi. Coba lagi.'
        );
      }
    } finally {
      actionLockRef.current = false;
    }
  };

  const handleSwitchUnlockMethod = (nextMethod: UnlockMethod) => {
    if (isBusy || inCooldown) {
      return;
    }
    clearPinFields();
    setLocalError(null);
    setUnlockMethod(nextMethod);
  };

  const handleBiometricUnlock = async () => {
    if (actionLockRef.current || isBusy || inCooldown || !biometricAvailable) {
      return;
    }

    actionLockRef.current = true;
    setLocalError(null);
    try {
      const unlocked = await unlockWithBiometrics();
      if (mountedRef.current) {
        if (unlocked) {
          clearPinFields();
        } else {
          setNowMs(Date.now());
        }
      }
    } catch (err) {
      if (mountedRef.current) {
        setNowMs(Date.now());
        setLocalError(
          err instanceof Error && err.message
            ? err.message
            : 'Verifikasi biometrik gagal. Gunakan PIN 6 digit.'
        );
      }
    } finally {
      actionLockRef.current = false;
    }
  };

  const handleRetryBoot = async () => {
    if (actionLockRef.current || isBusy) {
      return;
    }
    actionLockRef.current = true;
    setRetryingBoot(true);
    setLocalError(null);
    try {
      await hydrateAppLock();
    } catch (err) {
      if (mountedRef.current) {
        setLocalError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal memuat status kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setRetryingBoot(false);
      }
      actionLockRef.current = false;
    }
  };

  const performSignOut = async () => {
    if (actionLockRef.current || isBusy) {
      return;
    }
    actionLockRef.current = true;
    setSigningOut(true);
    setLocalError(null);
    clearPinFields();
    try {
      await onSignOut();
    } catch (err) {
      if (mountedRef.current) {
        setLocalError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal keluar dari akun. Coba lagi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSigningOut(false);
      }
      actionLockRef.current = false;
    }
  };

  const handleForgotPin = () => {
    if (isBusy) {
      return;
    }
    Alert.alert(
      'Lupa PIN kunci aplikasi?',
      'Untuk mengatur ulang kunci aplikasi, kamu perlu keluar dari sesi ini lalu masuk kembali ke akunmu. Data keuanganmu tetap aman dan tidak dihapus.',
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Keluar dari akun',
          style: 'destructive',
          onPress: () => {
            void performSignOut();
          },
        },
      ]
    );
  };

  if (!lockState.ready) {
    return (
      <View
        style={styles.overlay}
        accessibilityViewIsModal
        importantForAccessibility="yes"
      >
        <Screen
          scroll={false}
          bottomInset
          contentStyle={styles.centerContent}
        >
          <View style={styles.brand}>
            <Text style={styles.wordmark}>Bot04</Text>
            <View style={styles.brandRule} />
            <Text style={styles.tagline}>Kunci aplikasi</Text>
          </View>
          <ActivityIndicator
            size="small"
            color={Colors.inkMuted}
            accessibilityLabel="Memuat kunci aplikasi"
          />
          <Text style={styles.loadingCaption}>Memeriksa keamanan perangkat...</Text>
        </Screen>
      </View>
    );
  }

  if (lockState.covered && !lockState.locked && !lockState.error) {
    return (
      <View
        style={styles.overlay}
        accessibilityViewIsModal
        importantForAccessibility="yes"
      >
        <Screen
          scroll={false}
          bottomInset
          contentStyle={styles.centerContent}
        >
          <View style={styles.brand}>
            <View style={styles.iconCircle}>
              <Ionicons name="lock-closed-outline" size={20} color={Colors.inkSoft} />
            </View>
            <Text style={styles.wordmark}>Bot04</Text>
            <View style={styles.brandRule} />
            <Text style={styles.tagline}>Buku kas terlindungi</Text>
          </View>
        </Screen>
      </View>
    );
  }

  const isBootOrDisabledError = lockState.storageError || (!lockState.enabled && Boolean(lockState.error));
  const activeError = localError || lockState.error;

  return (
    <View
      style={styles.overlay}
      accessibilityViewIsModal
      importantForAccessibility="yes"
    >
      <Screen
        bottomInset
        keyboardBehavior="padding"
        contentStyle={styles.scrollContent}
      >
        <View style={styles.brand}>
          <View style={styles.iconCircle}>
            <Ionicons name="lock-closed-outline" size={20} color={Colors.inkSoft} />
          </View>
          <Text style={styles.wordmark}>Bot04</Text>
          <View style={styles.brandRule} />
          <Text style={styles.tagline}>Buku kas terkunci</Text>
        </View>

        {isBootOrDisabledError ? (
          <View style={styles.panel}>
            <Text style={styles.title}>Tidak dapat memverifikasi kunci</Text>
            <Text style={styles.subtitle}>
              {activeError ||
                'Penyimpanan keamanan perangkat tidak dapat dibaca saat ini.'}
            </Text>

            <View style={styles.actions}>
              <Button
                title="Coba lagi"
                onPress={handleRetryBoot}
                loading={retryingBoot}
                disabled={isBusy && !retryingBoot}
                size="lg"
              />
              <Button
                title="Keluar dari akun"
                variant="danger"
                icon="log-out-outline"
                onPress={handleForgotPin}
                loading={signingOut}
                disabled={isBusy && !signingOut}
              />
            </View>
          </View>
        ) : (
          <View style={styles.panel}>
            <Text style={styles.title}>
              {unlockMethod === 'pattern' && lockState.patternEnabled
                ? 'Gambar pola kunci'
                : 'Masukkan PIN'}
            </Text>
            <Text style={styles.subtitle}>
              {unlockMethod === 'pattern' && lockState.patternEnabled
                ? 'Hubungkan minimal 4 titik pola untuk membuka catatan keuanganmu.'
                : 'Masukkan PIN 6 digit untuk membuka catatan keuanganmu.'}
            </Text>

            {inCooldown ? (
              <View style={styles.cooldownBanner} accessibilityLiveRegion="polite">
                <Ionicons name="time-outline" size={18} color={Colors.danger} />
                <Text style={styles.cooldownText}>
                  Terlalu banyak percobaan salah. Coba lagi dalam {cooldownSeconds} detik.
                </Text>
              </View>
            ) : null}

            {activeError ? (
              <View style={styles.errorBanner} accessibilityLiveRegion="polite">
                <Ionicons name="alert-circle-outline" size={18} color={Colors.danger} />
                <Text style={styles.errorText}>{activeError}</Text>
              </View>
            ) : null}

            {unlockMethod === 'pattern' && lockState.patternEnabled ? (
              <PatternInput
                label="Pola 3x3"
                value={pattern}
                onChange={(next) => {
                  if (localError) {
                    setLocalError(null);
                  }
                  updatePattern(next);
                }}
                disabled={isBusy || inCooldown}
                accessibilityLabel="Pola buka kunci aplikasi"
              />
            ) : (
              <Input
                label="PIN 6 digit"
                placeholder="••••••"
                value={pin}
                onChangeText={(text) => {
                  if (localError) {
                    setLocalError(null);
                  }
                  updatePin(text);
                }}
                keyboardType="number-pad"
                inputMode="numeric"
                maxLength={6}
                secureTextEntry
                autoCorrect={false}
                autoCapitalize="none"
                autoComplete="off"
                textContentType="none"
                contextMenuHidden
                editable={!isBusy && !inCooldown}
                returnKeyType="done"
                onSubmitEditing={handlePinUnlock}
                accessibilityLabel="PIN 6 digit"
                fieldStyle={styles.pinField}
              />
            )}

            <View style={styles.actions}>
              {unlockMethod === 'pattern' && lockState.patternEnabled ? (
                <Button
                  title="Buka kunci dengan pola"
                  onPress={handlePatternUnlock}
                  loading={lockState.busy && !signingOut && !retryingBoot}
                  disabled={isBusy || inCooldown || !isValidLockPattern(pattern)}
                  size="lg"
                />
              ) : (
                <Button
                  title="Buka kunci"
                  onPress={handlePinUnlock}
                  loading={lockState.busy && !signingOut && !retryingBoot}
                  disabled={isBusy || inCooldown || pin.length !== 6}
                  size="lg"
                />
              )}

              {lockState.patternEnabled ? (
                <Button
                  title={
                    unlockMethod === 'pattern'
                      ? 'Gunakan PIN 6 digit'
                      : 'Gunakan pola kunci'
                  }
                  variant="secondary"
                  icon={unlockMethod === 'pattern' ? 'keypad-outline' : 'grid-outline'}
                  onPress={() =>
                    handleSwitchUnlockMethod(unlockMethod === 'pattern' ? 'pin' : 'pattern')
                  }
                  disabled={isBusy || inCooldown}
                />
              ) : null}

              {lockState.biometricsEnabled && biometricAvailable ? (
                <Button
                  title="Gunakan sidik jari / biometrik"
                  variant="secondary"
                  icon="finger-print-outline"
                  onPress={handleBiometricUnlock}
                  disabled={isBusy || inCooldown}
                />
              ) : null}

              {!lockState.locked && lockState.error ? (
                <Button
                  title="Muat ulang penyimpanan kunci"
                  variant="secondary"
                  onPress={handleRetryBoot}
                  loading={retryingBoot}
                  disabled={isBusy}
                />
              ) : null}

              <Button
                title="Lupa PIN? Keluar dari akun"
                variant="ghost"
                onPress={handleForgotPin}
                loading={signingOut}
                disabled={isBusy && !signingOut}
              />
            </View>
          </View>
        )}
      </Screen>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute', top: 0, bottom: 0, left: 0, right: 0,
    backgroundColor: Colors.paper,
    zIndex: 9999,
    elevation: 24,
  },
  centerContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: Space.md,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingTop: Space.xxl,
    paddingBottom: Space.xxl,
  },
  brand: {
    alignItems: 'center',
    marginBottom: Space.xl,
    gap: Space.sm,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.inkTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.xs,
  },
  wordmark: {
    ...Type.h1,
    fontSize: 38,
    lineHeight: 42,
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
  loadingCaption: {
    ...Type.caption,
    color: Colors.inkMuted,
  },
  panel: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.block,
    padding: Space.lg,
    gap: Space.sm,
  },
  title: {
    ...Type.h2,
  },
  subtitle: {
    ...Type.body,
    color: Colors.inkSoft,
    marginBottom: Space.sm,
  },
  cooldownBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Colors.dangerTint,
    borderWidth: 1,
    borderColor: 'rgba(163, 43, 43, 0.25)',
    borderRadius: Radius.control,
    paddingVertical: Space.sm,
    paddingHorizontal: Space.md,
    marginBottom: Space.xs,
  },
  cooldownText: {
    ...Type.caption,
    color: Colors.danger,
    flex: 1,
    fontVariant: ['tabular-nums'],
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Colors.dangerTint,
    borderWidth: 1,
    borderColor: 'rgba(163, 43, 43, 0.25)',
    borderRadius: Radius.control,
    paddingVertical: Space.sm,
    paddingHorizontal: Space.md,
    marginBottom: Space.xs,
  },
  errorText: {
    ...Type.caption,
    color: Colors.danger,
    flex: 1,
  },
  pinField: {
    fontFamily: Fonts.semibold,
    fontSize: 20,
    letterSpacing: 6,
    fontVariant: ['tabular-nums'],
  },
  actions: {
    gap: Space.sm,
    marginTop: Space.xs,
  },
});

export default AppLockView;

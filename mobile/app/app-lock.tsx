import { AppAlert as Alert } from '../services/appAlert';
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  ActivityIndicator,
  AppState,
  AppStateStatus,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space, Type } from '../utils/theme';
import { Screen } from '../components/ui/Screen';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { PatternInput } from '../components/security/PatternInput';
import { isValidLockPattern } from '../utils/lockPattern';
import {
  changeAppLockPin,
  disableAppLock,
  enableAppLock,
  getAppLockState,
  getBiometricAvailability,
  hydrateAppLock,
  setAppLockBiometrics,
  setAppLockPattern,
  subscribeAppLock,
} from '../services/appLock';

const PIN_PATTERN = /^[0-9]{6}$/;

function sanitizePinInput(value: string): string {
  return value.replace(/[^0-9]/g, '').slice(0, 6);
}

function patternsMatch(left: readonly number[], right: readonly number[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) {
      return false;
    }
  }
  return true;
}

export default function AppLockSettingsScreen() {
  const lockState = useSyncExternalStore(
    subscribeAppLock,
    getAppLockState,
    getAppLockState
  );

  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [currentPin, setCurrentPin] = useState('');
  const [changeNextPin, setChangeNextPin] = useState('');
  const [changeConfirmPin, setChangeConfirmPin] = useState('');
  const [newPattern, setNewPattern] = useState<number[]>([]);
  const [confirmPattern, setConfirmPattern] = useState<number[]>([]);

  const [error, setError] = useState<string | null>(null);
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [checkingBiometrics, setCheckingBiometrics] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const newPinRef = useRef('');
  const confirmPinRef = useRef('');
  const currentPinRef = useRef('');
  const changeNextPinRef = useRef('');
  const changeConfirmPinRef = useRef('');
  const newPatternRef = useRef<number[]>([]);
  const confirmPatternRef = useRef<number[]>([]);
  const mountedRef = useRef(true);
  const submitLockRef = useRef(false);

  const clearAllPinFields = useCallback(() => {
    newPinRef.current = '';
    confirmPinRef.current = '';
    currentPinRef.current = '';
    changeNextPinRef.current = '';
    changeConfirmPinRef.current = '';
    newPatternRef.current = [];
    confirmPatternRef.current = [];
    setNewPin('');
    setConfirmPin('');
    setCurrentPin('');
    setChangeNextPin('');
    setChangeConfirmPin('');
    setNewPattern([]);
    setConfirmPattern([]);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      newPinRef.current = '';
      confirmPinRef.current = '';
      currentPinRef.current = '';
      changeNextPinRef.current = '';
      changeConfirmPinRef.current = '';
      newPatternRef.current = [];
      confirmPatternRef.current = [];
    };
  }, []);

  useFocusEffect(
    useCallback(() => {
      return () => {
        clearAllPinFields();
      };
    }, [clearAllPinFields])
  );

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      if (nextState === 'background' || nextState === 'inactive') {
        clearAllPinFields();
        setError(null);
      }
    });
    return () => {
      subscription.remove();
    };
  }, [clearAllPinFields]);

  useEffect(() => {
    if (!lockState.ready || lockState.locked || lockState.covered) {
      clearAllPinFields();
      setError(null);
    }
  }, [lockState.ready, lockState.locked, lockState.covered, clearAllPinFields]);

  useEffect(() => {
    let active = true;
    if (!lockState.ready || !lockState.supported) {
      setBiometricAvailable(false);
      setCheckingBiometrics(false);
      return () => {
        active = false;
      };
    }

    setCheckingBiometrics(true);
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
      })
      .finally(() => {
        if (active && mountedRef.current) {
          setCheckingBiometrics(false);
        }
      });

    return () => {
      active = false;
    };
  }, [lockState.ready, lockState.supported, lockState.enabled, lockState.biometricsEnabled]);

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
      clearAllPinFields();
    }
  }, [inCooldown, clearAllPinFields]);

  const isBusy = lockState.busy || submitting;

  const handleBack = () => {
    clearAllPinFields();
    router.back();
  };

  const handleRetryHydrate = async () => {
    if (submitLockRef.current || isBusy) {
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await hydrateAppLock();
    } catch (err) {
      if (mountedRef.current) {
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal memuat pengaturan kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleEnableLock = async () => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    const pinCandidate = newPinRef.current;
    const confirmCandidate = confirmPinRef.current;

    if (!PIN_PATTERN.test(pinCandidate)) {
      setError('PIN harus terdiri dari tepat 6 digit angka.');
      return;
    }
    if (!PIN_PATTERN.test(confirmCandidate)) {
      setError('Konfirmasi PIN harus terdiri dari tepat 6 digit angka.');
      return;
    }
    if (pinCandidate !== confirmCandidate) {
      setError('PIN baru dan konfirmasi PIN tidak cocok.');
      return;
    }

    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await enableAppLock(pinCandidate);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert(
          'Kunci aplikasi aktif',
          'PIN 6 digit berhasil disimpan untuk melindungi aplikasi di perangkat ini.'
        );
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal mengaktifkan kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleChangePin = async () => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    const currCandidate = currentPinRef.current;
    const nextCandidate = changeNextPinRef.current;
    const confirmCandidate = changeConfirmPinRef.current;

    if (!PIN_PATTERN.test(currCandidate)) {
      setError('Masukkan PIN saat ini (6 digit).');
      return;
    }
    if (!PIN_PATTERN.test(nextCandidate)) {
      setError('PIN baru harus terdiri dari tepat 6 digit angka.');
      return;
    }
    if (!PIN_PATTERN.test(confirmCandidate)) {
      setError('Konfirmasi PIN baru harus terdiri dari tepat 6 digit angka.');
      return;
    }
    if (nextCandidate !== confirmCandidate) {
      setError('PIN baru dan konfirmasi PIN baru tidak cocok.');
      return;
    }

    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await changeAppLockPin(currCandidate, nextCandidate);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert('PIN diperbarui', 'PIN kunci aplikasi berhasil diganti.');
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal mengganti PIN kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleToggleBiometrics = async () => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    const currCandidate = currentPinRef.current;
    if (!PIN_PATTERN.test(currCandidate)) {
      setError('Masukkan PIN saat ini (6 digit) untuk mengubah pengaturan biometrik.');
      return;
    }

    const nextEnabled = !lockState.biometricsEnabled;
    if (nextEnabled && !biometricAvailable) {
      setError('Sidik jari / biometrik tidak tersedia atau belum terdaftar di perangkat ini.');
      return;
    }

    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await setAppLockBiometrics(currCandidate, nextEnabled);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert(
          nextEnabled ? 'Biometrik diaktifkan' : 'Biometrik dinonaktifkan',
          nextEnabled
            ? 'Sidik jari / biometrik kini dapat digunakan untuk membuka kunci aplikasi.'
            : 'Pembukaan kunci dengan sidik jari / biometrik telah dimatikan.'
        );
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal memperbarui pengaturan sidik jari / biometrik.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleSavePattern = async () => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    const currCandidate = currentPinRef.current;
    const nextCandidate = newPatternRef.current;
    const confirmCandidate = confirmPatternRef.current;

    if (!PIN_PATTERN.test(currCandidate)) {
      setError('Masukkan PIN saat ini (6 digit) untuk menyimpan pola kunci.');
      return;
    }
    if (!isValidLockPattern(nextCandidate)) {
      setError('Pola baru harus menghubungkan minimal 4 titik.');
      return;
    }
    if (!isValidLockPattern(confirmCandidate)) {
      setError('Konfirmasi pola baru harus menghubungkan minimal 4 titik.');
      return;
    }
    if (!patternsMatch(nextCandidate, confirmCandidate)) {
      setError('Pola baru dan konfirmasi pola tidak cocok.');
      return;
    }

    const wasEnabled = lockState.patternEnabled;
    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await setAppLockPattern(currCandidate, nextCandidate);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert(
          wasEnabled ? 'Pola kunci diperbarui' : 'Pola kunci diaktifkan',
          'Pola 3x3 berhasil disimpan sebagai metode buka kunci pendamping PIN.'
        );
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal menyimpan pola kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const executeRemovePattern = async (verifiedCurrentPin: string) => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await setAppLockPattern(verifiedCurrentPin, null);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert(
          'Pola kunci dihapus',
          'Pembukaan kunci dengan pola telah dinonaktifkan. PIN 6 digit tetap aktif.'
        );
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal menghapus pola kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleRemovePatternPrompt = () => {
    if (submitLockRef.current || isBusy || inCooldown || !lockState.patternEnabled) {
      return;
    }
    const currCandidate = currentPinRef.current;
    if (!PIN_PATTERN.test(currCandidate)) {
      setError('Masukkan PIN saat ini (6 digit) untuk menghapus pola kunci.');
      return;
    }

    Alert.alert(
      'Hapus pola kunci?',
      'Pola kunci pada perangkat ini akan dihapus. PIN 6 digit tetap digunakan untuk membuka aplikasi.',
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Hapus pola',
          style: 'destructive',
          onPress: () => {
            void executeRemovePattern(currCandidate);
          },
        },
      ]
    );
  };

  const executeDisableLock = async (verifiedCurrentPin: string) => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await disableAppLock(verifiedCurrentPin);
      if (mountedRef.current) {
        clearAllPinFields();
        Alert.alert(
          'Kunci aplikasi dinonaktifkan',
          'Kunci aplikasi pada perangkat ini telah dimatikan.'
        );
      }
    } catch (err) {
      if (mountedRef.current) {
        clearAllPinFields();
        setNowMs(Date.now());
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Gagal menonaktifkan kunci aplikasi.'
        );
      }
    } finally {
      if (mountedRef.current) {
        setSubmitting(false);
      }
      submitLockRef.current = false;
    }
  };

  const handleDisableLockPrompt = () => {
    if (submitLockRef.current || isBusy || inCooldown) {
      return;
    }
    const currCandidate = currentPinRef.current;
    if (!PIN_PATTERN.test(currCandidate)) {
      setError('Masukkan PIN saat ini (6 digit) untuk menonaktifkan kunci aplikasi.');
      return;
    }

    Alert.alert(
      'Nonaktifkan kunci aplikasi?',
      'PIN, pola kunci, dan pengaturan sidik jari / biometrik di perangkat ini akan dihapus.',
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Nonaktifkan',
          style: 'destructive',
          onPress: () => {
            void executeDisableLock(currCandidate);
          },
        },
      ]
    );
  };

  const activeError = error || lockState.error;

  return (
    <Screen bottomInset keyboardBehavior="padding">
      <View style={styles.header}>
        <Pressable
          onPress={handleBack}
          hitSlop={8}
          style={styles.back}
          accessibilityRole="button"
          accessibilityLabel="Kembali"
        >
          <Ionicons name="arrow-back" size={20} color={Colors.ink} />
        </Pressable>
        <Text style={styles.title}>Kunci aplikasi</Text>
      </View>

      {!lockState.ready ? (
        <View style={styles.loadingBlock}>
          <ActivityIndicator
            size="small"
            color={Colors.inkMuted}
            accessibilityLabel="Memuat pengaturan kunci aplikasi"
          />
          <Text style={styles.loadingText}>Memuat status keamanan perangkat...</Text>
        </View>
      ) : !lockState.supported ? (
        <View style={styles.noticeBlock}>
          <View style={styles.noticeHeader}>
            <Ionicons name="shield-outline" size={18} color={Colors.inkSoft} />
            <Text style={styles.noticeTitle}>Tidak didukung di perangkat ini</Text>
          </View>
          <Text style={styles.noticeBody}>
            Kunci aplikasi memerlukan penyimpanan aman perangkat (SecureStore) dan kriptografi
            bawaan sistem yang hanya tersedia pada aplikasi mobile Android atau iOS, bukan versi
            web atau biner lama tanpa modul keamanan.
          </Text>
          <Button
            title="Kembali ke pengaturan"
            variant="secondary"
            onPress={handleBack}
            style={styles.noticeButton}
          />
        </View>
      ) : (
        <View style={styles.content}>
          <Text style={styles.intro}>
            Lindungi akses catatan keuangan di perangkat ini dengan PIN 6 digit setiap kali
            aplikasi dibuka atau kembali dari latar belakang.
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
              {!lockState.enabled && lockState.error ? (
                <Button
                  title="Coba lagi"
                  variant="secondary"
                  fullWidth={false}
                  onPress={handleRetryHydrate}
                  loading={submitting}
                  disabled={isBusy}
                />
              ) : null}
            </View>
          ) : null}

          {!lockState.enabled ? (
            <View style={styles.sectionBlock}>
              <Text style={styles.sectionHeading}>Aktifkan PIN 6 digit</Text>
              <Text style={styles.sectionSub}>
                Buat PIN 6 digit angka. Jika kamu lupa PIN di kemudian hari, kamu perlu keluar dan
                masuk kembali ke akunmu.
              </Text>

              <Input
                label="PIN baru (6 digit)"
                placeholder="••••••"
                value={newPin}
                onChangeText={(text) => {
                  if (error) setError(null);
                  const clean = sanitizePinInput(text);
                  newPinRef.current = clean;
                  setNewPin(clean);
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
                returnKeyType="next"
                accessibilityLabel="PIN baru 6 digit"
                fieldStyle={styles.pinField}
              />

              <Input
                label="Konfirmasi PIN baru"
                placeholder="••••••"
                value={confirmPin}
                onChangeText={(text) => {
                  if (error) setError(null);
                  const clean = sanitizePinInput(text);
                  confirmPinRef.current = clean;
                  setConfirmPin(clean);
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
                onSubmitEditing={handleEnableLock}
                accessibilityLabel="Konfirmasi PIN baru"
                fieldStyle={styles.pinField}
              />

              <Button
                title="Aktifkan kunci aplikasi"
                onPress={handleEnableLock}
                loading={isBusy}
                disabled={isBusy || inCooldown}
                size="lg"
              />
            </View>
          ) : (
            <>
              <View style={styles.sectionBlock}>
                <View style={styles.statusRow}>
                  <View style={styles.statusBody}>
                    <Text style={styles.sectionHeading}>Status kunci aplikasi</Text>
                    <Text style={styles.sectionSub}>
                      Aktif di perangkat ini. Masukkan PIN saat ini untuk mengubah pengaturan
                      pola, biometrik, mengganti PIN, atau menonaktifkan kunci.
                    </Text>
                  </View>
                  <View style={styles.activeBadge}>
                    <Text style={styles.activeBadgeText}>Aktif</Text>
                  </View>
                </View>

                <Input
                  label="PIN saat ini"
                  placeholder="••••••"
                  value={currentPin}
                  onChangeText={(text) => {
                    if (error) setError(null);
                    const clean = sanitizePinInput(text);
                    currentPinRef.current = clean;
                    setCurrentPin(clean);
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
                  accessibilityLabel="PIN saat ini"
                  hint="Diperlukan untuk memverifikasi perubahan di bawah ini."
                  fieldStyle={styles.pinField}
                />
              </View>

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeading}>Pola kunci (3x3)</Text>
                <Text style={styles.sectionSub}>
                  Tambahkan pola minimal 4 titik sebagai pendamping PIN 6 digit. Isi PIN saat ini
                  di bagian atas, lalu gambar atau ketuk pola baru dan konfirmasinya.
                </Text>

                <View style={styles.biometricStatusRow}>
                  <Text style={styles.rowLabel}>Status pola kunci</Text>
                  <Text style={styles.rowValue}>
                    {lockState.patternEnabled ? 'Aktif' : 'Nonaktif'}
                  </Text>
                </View>

                <PatternInput
                  label={lockState.patternEnabled ? 'Pola baru (4-9 titik)' : 'Buat pola baru (4-9 titik)'}
                  value={newPattern}
                  onChange={(next) => {
                    if (error) setError(null);
                    newPatternRef.current = next;
                    setNewPattern(next);
                  }}
                  disabled={isBusy || inCooldown}
                  accessibilityLabel="Pola baru 3x3"
                />

                <PatternInput
                  label="Konfirmasi pola baru"
                  value={confirmPattern}
                  onChange={(next) => {
                    if (error) setError(null);
                    confirmPatternRef.current = next;
                    setConfirmPattern(next);
                  }}
                  disabled={isBusy || inCooldown}
                  accessibilityLabel="Konfirmasi pola baru 3x3"
                />

                <Button
                  title={lockState.patternEnabled ? 'Simpan pola baru' : 'Aktifkan pola kunci'}
                  icon="grid-outline"
                  onPress={handleSavePattern}
                  loading={isBusy}
                  disabled={isBusy || inCooldown}
                />

                {lockState.patternEnabled ? (
                  <Button
                    title="Hapus pola kunci"
                    variant="secondary"
                    onPress={handleRemovePatternPrompt}
                    loading={isBusy}
                    disabled={isBusy || inCooldown}
                  />
                ) : null}
              </View>

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeading}>Sidik jari / biometrik</Text>
                <Text style={styles.sectionSub}>
                  {checkingBiometrics
                    ? 'Memeriksa dukungan sidik jari / biometrik perangkat...'
                    : biometricAvailable || lockState.biometricsEnabled
                    ? 'Gunakan sidik jari / biometrik kuat bawaan sistem operasi (termasuk pengenalan wajah yang didukung perangkat) sebagai pendamping PIN.'
                    : 'Sidik jari / biometrik belum tersedia atau belum didaftarkan di pengaturan keamanan perangkat ini. PIN 6 digit tetap digunakan.'}
                </Text>

                <View style={styles.biometricStatusRow}>
                  <Text style={styles.rowLabel}>Status biometrik</Text>
                  <Text style={styles.rowValue}>
                    {lockState.biometricsEnabled ? 'Aktif' : 'Nonaktif'}
                  </Text>
                </View>

                {biometricAvailable || lockState.biometricsEnabled ? (
                  <Button
                    title={
                      lockState.biometricsEnabled
                        ? 'Nonaktifkan sidik jari / biometrik'
                        : 'Aktifkan sidik jari / biometrik'
                    }
                    variant="secondary"
                    icon="finger-print-outline"
                    onPress={handleToggleBiometrics}
                    loading={isBusy}
                    disabled={isBusy || inCooldown}
                  />
                ) : null}
              </View>

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeading}>Ganti PIN</Text>
                <Text style={styles.sectionSub}>
                  Isi PIN saat ini di bagian atas, lalu masukkan PIN 6 digit baru dan
                  konfirmasinya.
                </Text>

                <Input
                  label="PIN baru (6 digit)"
                  placeholder="••••••"
                  value={changeNextPin}
                  onChangeText={(text) => {
                    if (error) setError(null);
                    const clean = sanitizePinInput(text);
                    changeNextPinRef.current = clean;
                    setChangeNextPin(clean);
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
                  returnKeyType="next"
                  accessibilityLabel="PIN baru 6 digit"
                  fieldStyle={styles.pinField}
                />

                <Input
                  label="Konfirmasi PIN baru"
                  placeholder="••••••"
                  value={changeConfirmPin}
                  onChangeText={(text) => {
                    if (error) setError(null);
                    const clean = sanitizePinInput(text);
                    changeConfirmPinRef.current = clean;
                    setChangeConfirmPin(clean);
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
                  onSubmitEditing={handleChangePin}
                  accessibilityLabel="Konfirmasi PIN baru"
                  fieldStyle={styles.pinField}
                />

                <Button
                  title="Simpan PIN baru"
                  onPress={handleChangePin}
                  loading={isBusy}
                  disabled={isBusy || inCooldown}
                />
              </View>

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionHeading}>Matikan kunci aplikasi</Text>
                <Text style={styles.sectionSub}>
                  Menonaktifkan kunci aplikasi memerlukan verifikasi PIN saat ini.
                </Text>
                <Button
                  title="Nonaktifkan kunci aplikasi"
                  variant="danger"
                  icon="lock-open-outline"
                  onPress={handleDisableLockPrompt}
                  loading={isBusy}
                  disabled={isBusy || inCooldown}
                />
              </View>
            </>
          )}
        </View>
      )}
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
    paddingVertical: Space.xxl,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
  },
  loadingText: {
    ...Type.caption,
    color: Colors.inkMuted,
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
  content: {
    gap: Space.lg,
  },
  intro: {
    ...Type.body,
    color: Colors.inkSoft,
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
  },
  errorText: {
    ...Type.caption,
    color: Colors.danger,
    flex: 1,
  },
  sectionBlock: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.block,
    padding: Space.lg,
    gap: Space.sm,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: Space.md,
    marginBottom: Space.xs,
  },
  statusBody: {
    flex: 1,
    gap: Space.xs,
  },
  activeBadge: {
    backgroundColor: Colors.incomeTint,
    borderRadius: Radius.pill,
    paddingHorizontal: Space.md,
    paddingVertical: Space.xs,
  },
  activeBadgeText: {
    ...Type.micro,
    color: Colors.income,
  },
  sectionHeading: {
    ...Type.title,
  },
  sectionSub: {
    ...Type.caption,
    color: Colors.inkSoft,
    marginBottom: Space.xs,
  },
  biometricStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 44,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: Colors.line,
    marginBottom: Space.xs,
  },
  rowLabel: {
    ...Type.body,
    color: Colors.inkSoft,
  },
  rowValue: {
    ...Type.bodyStrong,
    color: Colors.ink,
  },
  pinField: {
    fontFamily: Fonts.semibold,
    fontSize: 20,
    letterSpacing: 6,
    fontVariant: ['tabular-nums'],
  },
});

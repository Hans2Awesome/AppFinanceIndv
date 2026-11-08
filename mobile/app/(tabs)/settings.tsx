import React, { useState, useEffect } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Space, Type } from '../../utils/theme';
import { User } from '../../types';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { FadeIn } from '../../components/ui/FadeIn';
import { authApi, describeApiError } from '../../services/auth';
import { LinkGoogleSheet } from '../../components/auth/LinkGoogleSheet';
import { isGoogleAuthAvailable } from '../../services/googleAuth';

export default function SettingsScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [googleAvailable, setGoogleAvailable] = useState(false);
  const [linkSheetVisible, setLinkSheetVisible] = useState(false);

  useEffect(() => {
    let active = true;
    isGoogleAuthAvailable().then((ok) => {
      if (active) setGoogleAvailable(ok);
    });
    return () => {
      active = false;
    };
  }, []);

  const loadProfile = async () => {
    try {
      setUser(await authApi.getProfile());
      setError(null);
    } catch (err) {
      setError(describeApiError(err, 'Gagal memuat profil.'));
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const [linking, setLinking] = useState(false);

  const handleLinkTelegram = async () => {
    setLinking(true);
    try {
      const { code, expires_in_minutes } = await authApi.createTelegramLinkToken();
      Alert.alert(
        'Kode tautan Telegram',
        `Kirim perintah berikut ke Bot04:\n\n/link ${code}\n\nKode berlaku ${expires_in_minutes} menit dan hanya bisa dipakai sekali.`
      );
    } catch (err) {
      Alert.alert('Gagal membuat kode', describeApiError(err, 'Coba lagi sebentar lagi.'));
    } finally {
      setLinking(false);
    }
  };

  const handleUnlinkTelegram = () => {
    Alert.alert(
      'Putuskan tautan Telegram',
      'Data keuanganmu tetap aman. Setelah diputus, kamu bisa menautkan akun Telegram lain lewat kode baru.',
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Putuskan',
          style: 'destructive',
          onPress: async () => {
            try {
              await authApi.unlinkTelegram();
              await loadProfile();
            } catch (err) {
              Alert.alert('Gagal memutus tautan', describeApiError(err, 'Coba lagi sebentar lagi.'));
            }
          },
        },
      ]
    );
  };

  const handleLogout = () => {
    Alert.alert('Keluar dari akun', 'Kamu perlu masuk lagi untuk membuka data keuangan.', [
      { text: 'Batal', style: 'cancel' },
      {
        text: 'Keluar',
        style: 'destructive',
        onPress: async () => {
          await authApi.logout();
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  const initial = user?.first_name ? user.first_name[0].toUpperCase() : 'B';

  return (
    <Screen>
      <FadeIn>
        <Text style={styles.title}>Pengaturan</Text>
      </FadeIn>

      {error ? <ErrorState message={error} onRetry={loadProfile} /> : null}

      <FadeIn delay={60}>
        <View style={styles.profile}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <View style={styles.profileInfo}>
            {user ? (
              <>
                <Text style={styles.userName} numberOfLines={1}>
                  {user.first_name || 'Pengguna'}
                </Text>
                <Text style={styles.userEmail} numberOfLines={1}>
                  {user.email}
                </Text>
              </>
            ) : (
              <>
                <Skeleton width="45%" height={17} />
                <Skeleton width="70%" height={12} style={styles.skeletonLine} />
              </>
            )}
          </View>
        </View>
      </FadeIn>

      <FadeIn delay={120}>
        <Text style={styles.sectionLabel}>Preferensi</Text>
        <View style={styles.block}>
          <Row label="Mata uang" value={user?.currency || 'IDR'} />
          <Row label="Zona waktu" value={user?.timezone || 'Asia/Jakarta'} last />
        </View>
      </FadeIn>

      <FadeIn delay={150}>
        <Text style={styles.sectionLabel}>Otomatisasi</Text>
        <View style={styles.block}>
          <Pressable
            onPress={() => router.push('/recurring')}
            accessibilityRole="button"
            accessibilityLabel="Transaksi berulang"
            style={({ pressed }) => [styles.navRow, pressed && styles.pressed]}
          >
            <View style={styles.navBody}>
              <Text style={styles.navTitle}>Transaksi berulang</Text>
              <Text style={styles.navHint}>
                Jadwal pemasukan, pengeluaran, dan investasi otomatis
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={Colors.inkMuted} />
          </Pressable>
        </View>
      </FadeIn>

      <FadeIn delay={180}>
        <Text style={styles.sectionLabel}>Telegram</Text>
        <View style={styles.block}>
          <View style={styles.navRow}>
            <View style={styles.navBody}>
              <Text style={styles.navTitle}>Hubungkan akun Telegram</Text>
              <Text style={styles.navHint}>
                {user?.telegram_linked
                  ? 'Sudah terhubung. Kirim kode baru bila ingin pindah akun Telegram.'
                  : 'Minta kode 6 digit, lalu kirim /link <kode> ke Bot04.'}
              </Text>
            </View>
            <Button
              title={user?.telegram_linked ? 'Kode baru' : 'Kode'}
              variant="secondary"
              onPress={handleLinkTelegram}
              loading={linking}
              style={styles.linkButton}
            />
          </View>
          {user?.telegram_linked ? (
            <Pressable
              onPress={handleUnlinkTelegram}
              accessibilityRole="button"
              accessibilityLabel="Putuskan tautan Telegram"
              style={({ pressed }) => [styles.navRow, styles.lastNavRow, pressed && styles.pressed]}
            >
              <View style={styles.navBody}>
                <Text style={styles.navTitle}>Putuskan tautan Telegram</Text>
                <Text style={styles.navHint}>
                  Lepas akun Telegram ini tanpa menghapus data keuangan.
                </Text>
              </View>
              <Ionicons name="unlink-outline" size={18} color={Colors.inkMuted} />
            </Pressable>
          ) : null}
        </View>
      </FadeIn>

      <FadeIn delay={180}>
        <Text style={styles.sectionLabel}>Google</Text>
        <View style={styles.block}>
          {user?.google_linked ? (
            <View style={[styles.navRow, styles.lastNavRow]}>
              <View style={styles.navBody}>
                <Text style={styles.navTitle}>Google tertaut</Text>
                <Text style={styles.navHint}>
                  Kamu bisa masuk memakai akun Google yang sudah ditautkan.
                </Text>
              </View>
              <Ionicons name="checkmark-circle-outline" size={18} color={Colors.inkMuted} />
            </View>
          ) : googleAvailable && user?.has_password ? (
            <Pressable
              onPress={() => setLinkSheetVisible(true)}
              accessibilityRole="button"
              accessibilityLabel="Tautkan akun Google"
              style={({ pressed }) => [styles.navRow, styles.lastNavRow, pressed && styles.pressed]}
            >
              <View style={styles.navBody}>
                <Text style={styles.navTitle}>Tautkan akun Google</Text>
                <Text style={styles.navHint}>
                  Masuk lebih cepat dengan akun Google yang emailnya sama.
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={Colors.inkMuted} />
            </Pressable>
          ) : (
            <View style={[styles.navRow, styles.lastNavRow]}>
              <View style={styles.navBody}>
                <Text style={styles.navTitle}>Google belum tersedia</Text>
                <Text style={styles.navHint}>
                  Login Google hanya aktif di aplikasi Android versi terbaru.
                </Text>
              </View>
            </View>
          )}
        </View>
      </FadeIn>

      <FadeIn delay={200}>
        <Text style={styles.sectionLabel}>Account security</Text>
        <View style={styles.block}>
          <Pressable
            onPress={() => router.push('/change-password')}
            accessibilityRole="button"
            accessibilityLabel="Change password"
            style={({ pressed }) => [styles.navRow, pressed && styles.pressed]}
          >
            <View style={styles.navBody}>
              <Text style={styles.navTitle}>Change password</Text>
              <Text style={styles.navHint}>
                {user?.has_password === false
                  ? 'Signed in with Google. View password management info.'
                  : 'Update your account password and sign out other devices.'}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={Colors.inkMuted} />
          </Pressable>

          <Pressable
            onPress={() => router.push('/delete-account')}
            accessibilityRole="button"
            accessibilityLabel="Delete account"
            style={({ pressed }) => [styles.navRow, styles.lastNavRow, pressed && styles.pressed]}
          >
            <View style={styles.navBody}>
              <Text style={styles.dangerTitle}>Delete account</Text>
              <Text style={styles.navHint}>
                Permanently delete your account and all financial records.
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={Colors.danger} />
          </Pressable>
        </View>
      </FadeIn>

      <FadeIn delay={210}>
        <Text style={styles.sectionLabel}>Tentang aplikasi</Text>
        <View style={styles.block}>
          <Row label="Versi" value="1.0.0" />
          <Row label="Sinkronisasi bot" value="Aktif" last />
        </View>
      </FadeIn>

      <FadeIn delay={240}>
        <Button
          title="Keluar dari akun"
          variant="danger"
          icon="log-out-outline"
          onPress={handleLogout}
          style={styles.logout}
        />
      </FadeIn>

      <LinkGoogleSheet
        visible={linkSheetVisible}
        onClose={() => setLinkSheetVisible(false)}
        onLinked={(linkedUser) => {
          setUser(linkedUser);
          setLinkSheetVisible(false);
        }}
      />
    </Screen>
  );
}

function Row({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.row, last && styles.lastRow]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  title: {
    ...Type.h1,
    marginBottom: Space.lg,
  },
  profile: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    paddingBottom: Space.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
    marginBottom: Space.xl,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Colors.inkTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontFamily: Fonts.serif,
    fontSize: 24,
    color: Colors.ink,
  },
  profileInfo: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  userName: {
    ...Type.title,
  },
  userEmail: {
    ...Type.caption,
  },
  skeletonLine: {
    marginTop: Space.xs,
  },
  sectionLabel: {
    ...Type.micro,
    textTransform: 'uppercase',
    marginBottom: Space.sm,
  },
  block: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: 10,
    paddingHorizontal: Space.lg,
    marginBottom: Space.xl,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
    minHeight: 48,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  lastRow: {
    borderBottomWidth: 0,
  },
  rowLabel: {
    ...Type.body,
    color: Colors.inkSoft,
  },
  rowValue: {
    ...Type.bodyStrong,
    color: Colors.ink,
    flexShrink: 1,
    textAlign: 'right',
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    minHeight: 58,
    paddingVertical: Space.sm,
  },
  linkButton: {
    flexShrink: 0,
  },
  lastNavRow: {
    borderTopWidth: 1,
    borderTopColor: Colors.line,
  },
  navBody: {
    flex: 1,
    minWidth: 0,
  },
  navTitle: {
    ...Type.bodyStrong,
    color: Colors.ink,
  },
  dangerTitle: {
    ...Type.bodyStrong,
    color: Colors.danger,
  },
  navHint: {
    ...Type.caption,
    marginTop: 2,
  },
  pressed: {
    opacity: 0.7,
  },
  logout: {
    marginTop: Space.sm,
  },
});
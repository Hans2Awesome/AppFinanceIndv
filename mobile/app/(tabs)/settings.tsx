import React, { useState, useEffect } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Colors, Fonts, Space, Type } from '../../utils/theme';
import { User } from '../../types';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { FadeIn } from '../../components/ui/FadeIn';
import { authApi, describeApiError } from '../../services/auth';

export default function SettingsScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

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

      <FadeIn delay={180}>
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
  logout: {
    marginTop: Space.sm,
  },
});
import { AppAlert as Alert } from '../services/appAlert';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Space, Type } from '../utils/theme';
import { RecurringTransaction, TransactionType } from '../types';
import { recurringApi } from '../services/recurring';
import { describeApiError } from '../services/auth';
import { formatDateIndo } from '../utils/formatRupiah';
import { describeFrequency, recurringTitle, typeLabel } from '../utils/recurring';
import { Screen } from '../components/ui/Screen';
import { Button } from '../components/ui/Button';
import { Amount } from '../components/ui/Amount';
import { ErrorState } from '../components/ui/ErrorState';
import { EmptyState } from '../components/ui/EmptyState';
import { SkeletonRows } from '../components/ui/Skeleton';
import { FadeIn } from '../components/ui/FadeIn';
import { RecurringFormModal } from '../components/recurring/RecurringFormModal';

const TYPE_TONE: Record<TransactionType, 'income' | 'expense' | 'investment'> = {
  income: 'income',
  expense: 'expense',
  investment: 'investment',
};

const TYPE_ACCENT: Record<TransactionType, string> = {
  income: Colors.income,
  expense: Colors.expense,
  investment: Colors.investment,
};

export default function RecurringScreen() {
  const [items, setItems] = useState<RecurringTransaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [selected, setSelected] = useState<RecurringTransaction | null>(null);

  const loadData = useCallback(async () => {
    try {
      setItems(await recurringApi.getRecurring());
      setError(null);
    } catch (err) {
      setError(describeApiError(err, 'Gagal memuat jadwal transaksi.'));
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const openCreate = () => {
    setSelected(null);
    setFormVisible(true);
  };

  const openEdit = (item: RecurringTransaction) => {
    setSelected(item);
    setFormVisible(true);
  };

  const toggleActive = async (item: RecurringTransaction) => {
    setBusyId(item.id);
    try {
      await recurringApi.updateRecurring(item.id, { is_active: !item.is_active });
      await loadData();
    } catch (err) {
      Alert.alert('Error', describeApiError(err, 'Gagal mengubah status jadwal.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Screen
      bottomInset
      refreshing={refreshing}
      onRefresh={onRefresh}
      footer={
        <View style={styles.footer}>
          <Button
            title="Tambah jadwal"
            icon="add"
            size="lg"
            onPress={openCreate}
          />
        </View>
      }
    >
      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          style={styles.back}
          accessibilityRole="button"
          accessibilityLabel="Kembali"
        >
          <Ionicons name="arrow-back" size={20} color={Colors.ink} />
        </Pressable>
        <Text style={styles.title}>Transaksi berulang</Text>
      </View>

      <FadeIn>
        <Text style={styles.intro}>
          Catat pemasukan atau pengeluaran yang berulang secara otomatis. Transaksi yang
          terlewat akan disusulkan saat jadwal berjalan lagi.
        </Text>
      </FadeIn>

      {error ? <ErrorState message={error} onRetry={loadData} /> : null}

      {items === null ? (
        <View style={styles.loadingBlock}>
          <SkeletonRows count={4} />
        </View>
      ) : items.length === 0 ? (
        <EmptyState
          icon="repeat-outline"
          title="Belum ada jadwal"
          message="Buat jadwal mingguan atau bulanan untuk gaji, sewa, langganan, atau cicilan tetap."
          actionLabel="Buat jadwal"
          onAction={openCreate}
        />
      ) : (
        <View>
          {items.map((item) => (
            <RecurringRow
              key={item.id}
              item={item}
              busy={busyId === item.id}
              onPress={() => openEdit(item)}
              onToggle={() => toggleActive(item)}
            />
          ))}
        </View>
      )}

      <RecurringFormModal
        visible={formVisible}
        schedule={selected}
        onClose={() => setFormVisible(false)}
        onSaved={async () => {
          setFormVisible(false);
          setSelected(null);
          await loadData();
        }}
      />
    </Screen>
  );
}

function RecurringRow({
  item,
  busy,
  onPress,
  onToggle,
}: {
  item: RecurringTransaction;
  busy: boolean;
  onPress: () => void;
  onToggle: () => void;
}) {
  const accent = TYPE_ACCENT[item.type];
  const active = item.is_active;

  return (
    <View style={styles.row}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={`${recurringTitle(item.type, item.category_name, item.note)}, ${describeFrequency(item.frequency, item.day_of_week, item.day_of_month)}`}
        style={({ pressed }) => [styles.mainPress, pressed ? styles.pressed : null]}
      >
        <View style={styles.rowMain}>
          <View style={[styles.dot, { backgroundColor: active ? accent : Colors.lineStrong }]} />
          <View style={styles.rowBody}>
            <Text style={[styles.rowTitle, !active && styles.inactiveText]} numberOfLines={1}>
              {recurringTitle(item.type, item.category_name, item.note)}
            </Text>
            <Text style={styles.rowMeta} numberOfLines={1}>
              {typeLabel(item.type)} · {describeFrequency(item.frequency, item.day_of_week, item.day_of_month)}
            </Text>
            <Text style={styles.rowNext}>
              {active
                ? `Berikutnya ${formatDateIndo(item.next_run_date)}`
                : 'Dijeda, tidak membuat transaksi baru'}
            </Text>
          </View>
          <View style={styles.rowAmount}>
            <Amount value={item.amount} tone={TYPE_TONE[item.type]} />
            <Text style={[styles.status, { color: active ? accent : Colors.inkMuted }]}>
              {active ? 'Aktif' : 'Nonaktif'}
            </Text>
          </View>
        </View>
      </Pressable>

      <View style={styles.switchRow}>
        <Text style={styles.switchLabel}>{active ? 'Jalankan otomatis' : 'Mulai lagi'}</Text>
        <Switch
          value={active}
          onValueChange={onToggle}
          disabled={busy}
          trackColor={{ false: Colors.lineStrong, true: Colors.inkSoft }}
          thumbColor={Colors.surface}
          ios_backgroundColor={Colors.lineStrong}
          accessibilityLabel={active ? 'Nonaktifkan jadwal' : 'Aktifkan jadwal'}
        />
      </View>
    </View>
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
  intro: {
    ...Type.caption,
    marginBottom: Space.lg,
    maxWidth: 360,
  },
  loadingBlock: {
    paddingTop: Space.lg,
  },
  row: {
    paddingVertical: Space.md,
    gap: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  pressed: {
    opacity: 0.7,
  },
  mainPress: {
    minHeight: 44,
  },
  rowMain: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Space.sm,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 7,
  },
  rowBody: {
    flex: 1,
    minWidth: 0,
  },
  rowTitle: {
    fontFamily: Fonts.medium,
    fontSize: 15,
    lineHeight: 20,
    color: Colors.ink,
  },
  inactiveText: {
    color: Colors.inkSoft,
  },
  rowMeta: {
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkMuted,
    marginTop: 2,
  },
  rowNext: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    marginTop: 2,
  },
  rowAmount: {
    alignItems: 'flex-end',
  },
  status: {
    fontFamily: Fonts.medium,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 0.04,
    marginTop: 2,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingLeft: 14,
    minHeight: 32,
  },
  switchLabel: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
  },
  footer: {
    paddingHorizontal: Space.gutter,
    paddingTop: Space.md,
    paddingBottom: Space.md,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    backgroundColor: Colors.paper,
  },
});
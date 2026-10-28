import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Space, Type } from '../utils/theme';
import { Debt, DebtSummary } from '../types';
import { DebtCard } from '../components/DebtCard';
import { DebtSummaryCard } from '../components/DebtSummaryCard';
import { DebtFilterTabs, DebtFilter } from '../components/debts/DebtFilterTabs';
import { CreateDebtModal } from '../components/debts/CreateDebtModal';
import { DebtDetailModal } from '../components/debts/DebtDetailModal';
import { ErrorState } from '../components/ui/ErrorState';
import { EmptyState } from '../components/ui/EmptyState';
import { SkeletonRows } from '../components/ui/Skeleton';
import { Screen } from '../components/ui/Screen';
import { Button } from '../components/ui/Button';
import { FadeIn } from '../components/ui/FadeIn';
import { debtApi } from '../services/debts';
import { describeApiError } from '../services/auth';

export default function DebtsScreen() {
  const [filter, setFilter] = useState<DebtFilter>('all');
  const [debts, setDebts] = useState<Debt[] | null>(null);
  const [summary, setSummary] = useState<DebtSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedDebt, setSelectedDebt] = useState<Debt | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const loadData = useCallback(async () => {
    const filterParams: { type?: Debt['type']; status?: Debt['status'] } = {};
    if (filter === 'debt') filterParams.type = 'debt';
    if (filter === 'receivable') filterParams.type = 'receivable';
    if (filter === 'settled') filterParams.status = 'settled';

    const [debtResult, summaryResult] = await Promise.allSettled([
      debtApi.getDebts(filterParams),
      debtApi.getSummary(),
    ]);

    if (debtResult.status === 'fulfilled') setDebts(debtResult.value);
    if (summaryResult.status === 'fulfilled') setSummary(summaryResult.value);

    const failures = [debtResult, summaryResult].filter(
      (result) => result.status === 'rejected'
    );
    setError(
      failures.length > 0
        ? describeApiError(
            (failures[0] as PromiseRejectedResult).reason,
            'Gagal memuat data hutang/piutang.'
          )
        : null
    );
  }, [filter]);

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

  const openDetail = (debt: Debt) => {
    setSelectedDebt(debt);
    setShowDetailModal(true);
  };

  return (
    <Screen
      bottomInset
      refreshing={refreshing}
      onRefresh={onRefresh}
      footer={
        <View style={styles.footer}>
          <Button
            title="Tambah catatan"
            icon="add"
            size="lg"
            onPress={() => setShowCreateModal(true)}
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
        <Text style={styles.title}>Hutang & piutang</Text>
      </View>

      <FadeIn>
        <DebtSummaryCard summary={summary} />
      </FadeIn>

      {error ? <ErrorState message={error} onRetry={loadData} /> : null}

      <DebtFilterTabs value={filter} onChange={setFilter} />

      {debts === null ? (
        <View style={styles.loadingBlock}>
          <SkeletonRows count={4} />
        </View>
      ) : debts.length === 0 ? (
        <EmptyState
          icon="swap-horizontal-outline"
          title="Belum ada catatan"
          message={
            filter === 'all'
              ? 'Catat hutang atau piutang supaya sisa dan jatuh temponya terlacak.'
              : 'Tidak ada catatan pada filter ini.'
          }
          actionLabel={filter === 'all' ? 'Tambah catatan' : undefined}
          onAction={filter === 'all' ? () => setShowCreateModal(true) : undefined}
        />
      ) : (
        <View>
          {debts.map((debt) => (
            <DebtCard key={debt.id} debt={debt} onPress={() => openDetail(debt)} />
          ))}
        </View>
      )}

      <CreateDebtModal
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={async () => {
          setShowCreateModal(false);
          await loadData();
        }}
      />

      <DebtDetailModal
        debt={selectedDebt}
        visible={showDetailModal}
        onClose={() => {
          setShowDetailModal(false);
          setSelectedDebt(null);
        }}
        onChanged={async () => {
          await loadData();
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginBottom: Space.lg,
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
  footer: {
    paddingHorizontal: Space.gutter,
    paddingTop: Space.md,
    paddingBottom: Space.md,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    backgroundColor: Colors.paper,
  },
});
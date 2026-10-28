import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Colors, Space, Type } from '../../utils/theme';
import { PeriodReport, Transaction, User, DebtSummary } from '../../types';
import { ReportSummaryCard } from '../../components/ReportSummaryCard';
import { QuickInputBar } from '../../components/QuickInputBar';
import { TransactionCard } from '../../components/TransactionCard';
import { DebtSummaryCard } from '../../components/DebtSummaryCard';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Screen } from '../../components/ui/Screen';
import { FadeIn } from '../../components/ui/FadeIn';
import { reportApi } from '../../services/reports';
import { transactionApi } from '../../services/transactions';
import { authApi } from '../../services/auth';
import { debtApi } from '../../services/debts';
import { describeApiError } from '../../services/auth';
import { formatDateIndo } from '../../utils/formatRupiah';
import { localTodayIso } from '../../utils/date';

export default function DashboardScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [debtSummary, setDebtSummary] = useState<DebtSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    const [profileResult, reportResult, txResult, debtResult] = await Promise.allSettled([
      authApi.getProfile(),
      reportApi.getDailyReport(),
      transactionApi.getTransactions({ limit: 10 }),
      debtApi.getSummary(),
    ]);

    if (profileResult.status === 'fulfilled') setUser(profileResult.value);
    if (reportResult.status === 'fulfilled') setReport(reportResult.value);
    if (txResult.status === 'fulfilled') setTransactions(txResult.value);
    if (debtResult.status === 'fulfilled') setDebtSummary(debtResult.value);

    const failures = [profileResult, reportResult, txResult, debtResult].filter(
      (result) => result.status === 'rejected'
    );

    if (failures.length === 0) {
      setError(null);
      return;
    }

    const firstFailure = failures[0] as PromiseRejectedResult;
    const allFailed = failures.length === 4;
    setError(
      allFailed
        ? describeApiError(firstFailure.reason, 'Gagal memuat data. Tarik ke bawah untuk mencoba lagi.')
        : 'Sebagian data gagal dimuat. Tarik ke bawah untuk mencoba lagi.'
    );
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

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <FadeIn>
        <Text style={styles.date}>{formatDateIndo(localTodayIso())}</Text>
        <Text style={styles.greeting} numberOfLines={1}>
          Halo, {user?.first_name || 'Pengguna'}
        </Text>
      </FadeIn>

      <FadeIn delay={60}>
        {error ? <ErrorState message={error} onRetry={loadData} /> : null}
        <ReportSummaryCard report={report} />
      </FadeIn>

      <FadeIn delay={120}>
        <SectionHeader title="Catat cepat" />
        <QuickInputBar onSuccess={loadData} />
      </FadeIn>

      <FadeIn delay={180}>
        <SectionHeader
          title="Hutang & Piutang"
          actionLabel="Lihat"
          onAction={() => router.push('/debts')}
        />
        <Pressable
          onPress={() => router.push('/debts')}
          accessibilityRole="button"
          accessibilityLabel="Buka hutang dan piutang"
          style={({ pressed }) => (pressed ? styles.pressed : null)}
        >
          <DebtSummaryCard summary={debtSummary} />
        </Pressable>
      </FadeIn>

      <FadeIn delay={240}>
        <SectionHeader
          title="Transaksi terbaru"
          actionLabel="Lihat semua"
          onAction={() => router.push('/(tabs)/reports')}
        />

        {transactions.length === 0 ? (
          <EmptyState
            icon="receipt-outline"
            title="Belum ada transaksi hari ini"
            message='Ketik "makan 25000" di kolom catat cepat untuk mulai mencatat.'
            actionLabel="Catat manual"
            onAction={() => router.push('/(tabs)/add')}
          />
        ) : (
          <View>
            {transactions.map((transaction) => (
              <TransactionCard key={transaction.id} transaction={transaction} />
            ))}
          </View>
        )}
      </FadeIn>
    </Screen>
  );
}

const styles = StyleSheet.create({
  date: {
    ...Type.micro,
    textTransform: 'uppercase',
    marginBottom: Space.xs,
  },
  greeting: {
    ...Type.h1,
    marginBottom: Space.lg,
  },
  pressed: {
    opacity: 0.85,
  },
});
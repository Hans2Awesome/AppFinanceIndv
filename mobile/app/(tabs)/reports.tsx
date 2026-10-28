import React, { useState, useCallback } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Colors, Fonts, Space, Type } from '../../utils/theme';
import { PeriodReport, Transaction } from '../../types';
import { ReportSummaryCard } from '../../components/ReportSummaryCard';
import { TransactionCard } from '../../components/TransactionCard';
import { Screen } from '../../components/ui/Screen';
import { Segmented } from '../../components/ui/Segmented';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Progress } from '../../components/ui/Progress';
import { Amount } from '../../components/ui/Amount';
import { Skeleton, SkeletonRows } from '../../components/ui/Skeleton';
import { FadeIn } from '../../components/ui/FadeIn';
import { reportApi } from '../../services/reports';
import { transactionApi } from '../../services/transactions';
import { describeApiError } from '../../services/auth';

type Period = 'daily' | 'weekly' | 'monthly';

const PERIOD_ITEMS = [
  { key: 'daily' as const, label: 'Hari ini' },
  { key: 'weekly' as const, label: 'Minggu ini' },
  { key: 'monthly' as const, label: 'Bulan ini' },
];

export default function ReportsScreen() {
  const [period, setPeriod] = useState<Period>('monthly');
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    try {
      let reportData: PeriodReport;
      if (period === 'daily') {
        reportData = await reportApi.getDailyReport();
      } else if (period === 'weekly') {
        reportData = await reportApi.getWeeklyReport();
      } else {
        reportData = await reportApi.getMonthlyReport();
      }
      setReport(reportData);

      const txs = await transactionApi.getTransactions({
        start_date: reportData.start_date,
        end_date: reportData.end_date,
        limit: 50,
      });
      setTransactions(txs);
      setError(null);
    } catch (err) {
      setError(describeApiError(err, 'Gagal memuat laporan.'));
    }
  }, [period]);

  useFocusEffect(
    useCallback(() => {
      fetchReport();
    }, [fetchReport])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchReport();
    setRefreshing(false);
  };

  return (
    <Screen refreshing={refreshing} onRefresh={onRefresh}>
      <FadeIn>
        <Text style={styles.title}>Laporan</Text>
        <Segmented items={PERIOD_ITEMS} value={period} onChange={setPeriod} label="Periode laporan" />
      </FadeIn>

      {error ? <ErrorState message={error} onRetry={fetchReport} /> : null}

      <FadeIn delay={60}>
        <ReportSummaryCard report={report} />
      </FadeIn>

      <FadeIn delay={120}>
        <SectionHeader title="Pengeluaran per kategori" />
        {!report ? (
          <View style={styles.block}>
            <SkeletonRows count={3} />
          </View>
        ) : report.top_expense_categories.length === 0 ? (
          <EmptyState
            icon="pie-chart-outline"
            title="Belum ada pengeluaran"
            message="Pengeluaran yang tercatat di periode ini akan muncul di sini."
          />
        ) : (
          <View style={styles.block}>
            {report.top_expense_categories.map((cat, index) => (
              <View
                key={`${cat.name}-${index}`}
                style={[
                  styles.categoryRow,
                  index === report.top_expense_categories.length - 1 && styles.lastRow,
                ]}
              >
                <View style={styles.categoryHead}>
                  <Text style={styles.categoryName} numberOfLines={1}>
                    {cat.name}
                  </Text>
                  <Amount value={cat.amount} tone="expense" />
                </View>
                <Progress value={cat.percentage} color={Colors.expense} />
                <Text style={styles.categoryPct}>{Math.round(cat.percentage)}% dari pengeluaran</Text>
              </View>
            ))}
          </View>
        )}
      </FadeIn>

      <FadeIn delay={180}>
        <SectionHeader title={`Daftar transaksi (${transactions.length})`} />
        {transactions.length === 0 ? (
          <EmptyState
            icon="receipt-outline"
            title="Tidak ada transaksi"
            message="Belum ada catatan di periode ini."
          />
        ) : (
          <View>
            {transactions.map((tx) => (
              <TransactionCard key={tx.id} transaction={tx} />
            ))}
          </View>
        )}
      </FadeIn>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    ...Type.h1,
    marginBottom: Space.lg,
  },
  block: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: 10,
    paddingHorizontal: Space.lg,
    paddingVertical: Space.xs,
    marginBottom: Space.xl,
  },
  categoryRow: {
    paddingVertical: Space.md,
    gap: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  lastRow: {
    borderBottomWidth: 0,
  },
  categoryHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
  },
  categoryName: {
    ...Type.bodyStrong,
    flex: 1,
  },
  categoryPct: {
    ...Type.micro,
    letterSpacing: 0,
  },
});
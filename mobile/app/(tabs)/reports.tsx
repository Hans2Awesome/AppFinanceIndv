import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { Colors } from '../../utils/colors';
import { PeriodReport, Transaction } from '../../types';
import { ReportSummaryCard } from '../../components/ReportSummaryCard';
import { TransactionCard } from '../../components/TransactionCard';
import { reportApi } from '../../services/reports';
import { transactionApi } from '../../services/transactions';
import { formatRupiah } from '../../utils/formatRupiah';

export default function ReportsScreen() {
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('monthly');
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [refreshing, setRefreshing] = useState(false);

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

      // Fetch transactions within that period range
      const txs = await transactionApi.getTransactions({
        start_date: reportData.start_date,
        end_date: reportData.end_date,
        limit: 50,
      });
      setTransactions(txs);
    } catch {
      // Handle error
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
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
          />
        }
      >
        <Text style={styles.pageTitle}>Laporan & Analitik</Text>

        {/* Period Tabs */}
        <View style={styles.periodTabs}>
          <TouchableOpacity
            style={[styles.tab, period === 'daily' && styles.tabActive]}
            onPress={() => setPeriod('daily')}
          >
            <Text style={[styles.tabText, period === 'daily' && styles.tabTextActive]}>
              Hari Ini
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tab, period === 'weekly' && styles.tabActive]}
            onPress={() => setPeriod('weekly')}
          >
            <Text style={[styles.tabText, period === 'weekly' && styles.tabTextActive]}>
              Minggu Ini
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tab, period === 'monthly' && styles.tabActive]}
            onPress={() => setPeriod('monthly')}
          >
            <Text style={[styles.tabText, period === 'monthly' && styles.tabTextActive]}>
              Bulan Ini
            </Text>
          </TouchableOpacity>
        </View>

        {/* Financial Summary */}
        <ReportSummaryCard report={report} />

        {/* Category Breakdown */}
        {report && report.top_expense_categories.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Pengeluaran per Kategori</Text>
            <View style={styles.categoryCard}>
              {report.top_expense_categories.map((cat, idx) => (
                <View key={idx} style={styles.catRow}>
                  <View style={styles.catHeader}>
                    <Text style={styles.catName}>{cat.name}</Text>
                    <Text style={styles.catAmount}>{formatRupiah(cat.amount)}</Text>
                  </View>
                  <View style={styles.progressBarBg}>
                    <View
                      style={[
                        styles.progressBarFill,
                        { width: `${Math.min(cat.percentage, 100)}%` },
                      ]}
                    />
                  </View>
                  <Text style={styles.catPct}>{cat.percentage}% dari pengeluaran</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Transaction History for Period */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>
            Daftar Transaksi ({transactions.length})
          </Text>

          {transactions.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyText}>Tidak ada transaksi di periode ini.</Text>
            </View>
          ) : (
            transactions.map((tx) => (
              <TransactionCard key={tx.id} transaction={tx} />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  container: {
    padding: 20,
    paddingBottom: 40,
  },
  pageTitle: {
    color: Colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 20,
    marginTop: 8,
  },
  periodTabs: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    padding: 4,
    borderRadius: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  tab: {
    flex: 1,
    paddingVertical: 9,
    alignItems: 'center',
    borderRadius: 10,
  },
  tabActive: {
    backgroundColor: Colors.primary,
  },
  tabText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  tabTextActive: {
    color: '#fff',
    fontWeight: '700',
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  categoryCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 16,
    padding: 16,
  },
  catRow: {
    marginBottom: 14,
  },
  catHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  catName: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  catAmount: {
    color: Colors.textSecondary,
    fontSize: 14,
    fontWeight: '700',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: Colors.surfaceLight,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.primary,
    borderRadius: 4,
  },
  catPct: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 4,
  },
  emptyCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
  },
  emptyText: {
    color: Colors.textSecondary,
    fontSize: 14,
  },
});

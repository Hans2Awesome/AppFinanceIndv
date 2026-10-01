import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../utils/colors';
import { PeriodReport, Transaction, User, DebtSummary } from '../../types';
import { ReportSummaryCard } from '../../components/ReportSummaryCard';
import { QuickInputBar } from '../../components/QuickInputBar';
import { TransactionCard } from '../../components/TransactionCard';
import { reportApi } from '../../services/reports';
import { transactionApi } from '../../services/transactions';
import { authApi } from '../../services/auth';
import { debtApi } from '../../services/debts';
import { getAuthToken } from '../../services/api';
import { formatRupiah } from '../../utils/formatRupiah';

export default function DashboardScreen() {
  const [user, setUser] = useState<User | null>(null);
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [debtSummary, setDebtSummary] = useState<DebtSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    // If no auth token, redirect to login
    if (!getAuthToken()) {
      router.replace('/(auth)/login');
      return;
    }

    try {
      const [profileData, reportData, txData, debtData] = await Promise.all([
        authApi.getProfile().catch(() => null),
        reportApi.getDailyReport().catch(() => null),
        transactionApi.getTransactions({ limit: 10 }).catch(() => []),
        debtApi.getSummary().catch(() => null),
      ]);

      if (profileData) setUser(profileData);
      if (reportData) setReport(reportData);
      setTransactions(txData);
      setDebtSummary(debtData);
    } catch {
      // User might be unauthenticated
      router.replace('/(auth)/login');
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
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>
              Halo, {user?.first_name || 'Pengguna'} 👋
            </Text>
            <Text style={styles.subGreeting}>
              Catatan keuangan hari ini
            </Text>
          </View>
        </View>

        {/* Financial Summary Card */}
        <ReportSummaryCard report={report} />

        {/* Quick Text Input */}
        <Text style={styles.sectionTitle}>Input Cepat</Text>
        <QuickInputBar onSuccess={loadData} />

        {/* Debt & Receivable Section */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => router.push('/(tabs)/debts')}
          style={styles.debtSection}
        >
          <View style={styles.debtSectionHeader}>
            <View style={styles.debtSectionTitleRow}>
              <Ionicons name="people-outline" size={18} color={Colors.text} />
              <Text style={styles.sectionTitle}>Hutang & Piutang</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
          </View>
          <View style={styles.debtMiniStats}>
            <View style={styles.debtMiniStat}>
              <Text style={styles.debtMiniLabel}>Hutang</Text>
              <Text style={[styles.debtMiniValue, { color: Colors.debt }]}>
                {formatRupiah(debtSummary?.total_debt_remaining ?? 0)}
              </Text>
            </View>
            <View style={styles.debtMiniDivider} />
            <View style={styles.debtMiniStat}>
              <Text style={styles.debtMiniLabel}>Piutang</Text>
              <Text style={[styles.debtMiniValue, { color: Colors.receivable }]}>
                {formatRupiah(debtSummary?.total_receivable_remaining ?? 0)}
              </Text>
            </View>
          </View>
          {(debtSummary?.due_soon_count ?? 0) > 0 && (
            <View style={styles.debtAlert}>
              <Text style={styles.debtAlertText}>
                ⚠️ {debtSummary!.due_soon_count} jatuh tempo dalam 7 hari
              </Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Recent Transactions */}
        <View style={styles.transactionsHeader}>
          <Text style={styles.sectionTitle}>Transaksi Terbaru</Text>
          <TouchableOpacity onPress={() => router.push('/(tabs)/reports')}>
            <Text style={styles.seeAllText}>Lihat Semua</Text>
          </TouchableOpacity>
        </View>

        {transactions.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>Belum ada transaksi hari ini.</Text>
            <Text style={styles.emptySubText}>
              Coba ketik "makan 25000" di kolom input cepat di atas.
            </Text>
          </View>
        ) : (
          transactions.map((tx) => (
            <TransactionCard
              key={tx.id}
              transaction={tx}
              onPress={() => {}}
            />
          ))
        )}
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    marginTop: 8,
  },
  greeting: {
    color: Colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  subGreeting: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 2,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 10,
  },
  transactionsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    marginTop: 10,
  },
  seeAllText: {
    color: Colors.primary,
    fontSize: 13,
    fontWeight: '600',
  },
  emptyCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
    marginTop: 8,
  },
  emptyText: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  emptySubText: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
  debtSection: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 14,
    padding: 16,
    marginBottom: 20,
  },
  debtSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  debtSectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  debtMiniStats: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: Colors.surfaceLight,
    padding: 12,
    borderRadius: 10,
  },
  debtMiniStat: {
    flex: 1,
    alignItems: 'center',
  },
  debtMiniDivider: {
    width: 1,
    height: 28,
    backgroundColor: Colors.surfaceBorder,
  },
  debtMiniLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    marginBottom: 4,
  },
  debtMiniValue: {
    fontSize: 14,
    fontWeight: '700',
  },
  debtAlert: {
    marginTop: 10,
    backgroundColor: 'rgba(251, 146, 60, 0.1)',
    padding: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  debtAlertText: {
    color: Colors.dueSoon,
    fontSize: 11,
    fontWeight: '600',
  },
});

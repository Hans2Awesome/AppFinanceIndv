import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { PeriodReport } from '../types';
import { Colors } from '../utils/colors';
import { formatRupiah } from '../utils/formatRupiah';
import { Card } from './ui/Card';

interface ReportSummaryCardProps {
  report: PeriodReport | null;
  loading?: boolean;
}

export const ReportSummaryCard: React.FC<ReportSummaryCardProps> = ({
  report,
}) => {
  const net = report?.net ?? 0;
  const isNetPositive = net >= 0;

  return (
    <Card style={styles.card}>
      <Text style={styles.title}>{report?.title || 'Ringkasan Keuangan'}</Text>
      
      <View style={styles.netContainer}>
        <Text style={styles.netLabel}>Sisa Bersih</Text>
        <Text
          style={[
            styles.netAmount,
            { color: isNetPositive ? Colors.income : Colors.danger },
          ]}
        >
          {formatRupiah(net)}
        </Text>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Pemasukan</Text>
          <Text style={[styles.statValue, { color: Colors.income }]}>
            {formatRupiah(report?.total_income ?? 0)}
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Pengeluaran</Text>
          <Text style={[styles.statValue, { color: Colors.expense }]}>
            {formatRupiah(report?.total_expense ?? 0)}
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Investasi</Text>
          <Text style={[styles.statValue, { color: Colors.investment }]}>
            {formatRupiah(report?.total_investment ?? 0)}
          </Text>
        </View>
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    padding: 20,
    marginBottom: 20,
  },
  title: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 8,
  },
  netContainer: {
    marginBottom: 20,
  },
  netLabel: {
    color: Colors.textMuted,
    fontSize: 12,
  },
  netAmount: {
    fontSize: 28,
    fontWeight: '800',
    marginTop: 4,
    letterSpacing: -0.5,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surfaceLight,
    padding: 14,
    borderRadius: 12,
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
  },
  divider: {
    width: 1,
    height: 28,
    backgroundColor: Colors.surfaceBorder,
  },
  statLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    marginBottom: 4,
  },
  statValue: {
    fontSize: 13,
    fontWeight: '700',
  },
});

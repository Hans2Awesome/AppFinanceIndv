import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { DebtSummary } from '../types';
import { Colors } from '../utils/colors';
import { formatRupiah } from '../utils/formatRupiah';
import { Card } from './ui/Card';

interface DebtSummaryCardProps {
  summary: DebtSummary | null;
}

export const DebtSummaryCard: React.FC<DebtSummaryCardProps> = ({ summary }) => {
  const debtRemaining = summary?.total_debt_remaining ?? 0;
  const receivableRemaining = summary?.total_receivable_remaining ?? 0;
  const dueSoonCount = summary?.due_soon_count ?? 0;

  return (
    <Card style={styles.card}>
      <Text style={styles.title}>Ringkasan Hutang & Piutang</Text>

      {dueSoonCount > 0 && (
        <View style={styles.alertBanner}>
          <Text style={styles.alertIcon}>⚠️</Text>
          <Text style={styles.alertText}>
            {dueSoonCount} item jatuh tempo dalam 7 hari
          </Text>
        </View>
      )}

      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Hutang</Text>
          <Text style={[styles.statValue, { color: Colors.debt }]}>
            {formatRupiah(debtRemaining)}
          </Text>
          <Text style={styles.statCount}>
            {summary?.active_debt_count ?? 0} aktif
          </Text>
        </View>

        <View style={styles.divider} />

        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Piutang</Text>
          <Text style={[styles.statValue, { color: Colors.receivable }]}>
            {formatRupiah(receivableRemaining)}
          </Text>
          <Text style={styles.statCount}>
            {summary?.active_receivable_count ?? 0} aktif
          </Text>
        </View>
      </View>

      {/* Net position */}
      <View style={styles.netRow}>
        <Text style={styles.netLabel}>Posisi Bersih</Text>
        <Text
          style={[
            styles.netValue,
            {
              color: receivableRemaining >= debtRemaining
                ? Colors.income
                : Colors.danger,
            },
          ]}
        >
          {receivableRemaining >= debtRemaining ? '+' : ''}
          {formatRupiah(receivableRemaining - debtRemaining)}
        </Text>
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
    marginBottom: 12,
  },
  alertBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.dueSoonBg,
    padding: 10,
    borderRadius: 10,
    marginBottom: 14,
    gap: 8,
  },
  alertIcon: {
    fontSize: 14,
  },
  alertText: {
    color: Colors.dueSoon,
    fontSize: 12,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surfaceLight,
    padding: 14,
    borderRadius: 12,
    marginBottom: 12,
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
  },
  divider: {
    width: 1,
    height: 40,
    backgroundColor: Colors.surfaceBorder,
  },
  statLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    marginBottom: 4,
  },
  statValue: {
    fontSize: 15,
    fontWeight: '700',
  },
  statCount: {
    color: Colors.textMuted,
    fontSize: 10,
    marginTop: 2,
  },
  netRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 4,
  },
  netLabel: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  netValue: {
    fontSize: 15,
    fontWeight: '700',
  },
});

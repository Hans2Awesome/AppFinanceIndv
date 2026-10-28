import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { DebtSummary } from '../types';
import { Colors, Fonts, Space, Type } from '../utils/theme';
import { amountFontSize, formatRupiah } from '../utils/formatRupiah';
import { Card } from './ui/Card';
import { Amount } from './ui/Amount';
import { Skeleton } from './ui/Skeleton';

interface DebtSummaryCardProps {
  summary: DebtSummary | null;
}

/** Two semantic columns plus the net position, set on paper. */
export function DebtSummaryCard({ summary }: DebtSummaryCardProps) {
  if (!summary) {
    return (
      <Card style={styles.card}>
        <View style={styles.columns}>
          {[0, 1].map((index) => (
            <View key={index} style={styles.column}>
              <Skeleton width="50%" height={10} />
              <Skeleton width="80%" height={20} style={styles.skeletonValue} />
            </View>
          ))}
        </View>
      </Card>
    );
  }

  const debt = summary.total_debt_remaining ?? 0;
  const receivable = summary.total_receivable_remaining ?? 0;
  const net = receivable - debt;
  const dueSoon = summary.due_soon_count ?? 0;

  return (
    <Card style={styles.card}>
      <View style={styles.columns}>
        <Column
          label="Hutang"
          dot={Colors.debt}
          amount={debt}
          count={summary.active_debt_count ?? 0}
          tone="debt"
        />
        <View style={styles.divider} />
        <Column
          label="Piutang"
          dot={Colors.receivable}
          amount={receivable}
          count={summary.active_receivable_count ?? 0}
          tone="receivable"
        />
      </View>

      <View style={styles.netRow}>
        <Text style={styles.netLabel}>Posisi bersih</Text>
        <Amount
          value={net}
          signed
          tone={net >= 0 ? 'income' : 'expense'}
          size="large"
          style={{ fontSize: amountFontSize(formatRupiah(net), 17, 10) }}
        />
      </View>

      {dueSoon > 0 ? (
        <View style={styles.dueSoon}>
          <View style={styles.dueSoonDot} />
          <Text style={styles.dueSoonText}>
            {dueSoon} item jatuh tempo dalam 7 hari
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

function Column({
  label,
  dot,
  amount,
  count,
  tone,
}: {
  label: string;
  dot: string;
  amount: number;
  count: number;
  tone: 'debt' | 'receivable';
}) {
  return (
    <View style={styles.column}>
      <View style={styles.labelRow}>
        <View style={[styles.dot, { backgroundColor: dot }]} />
        <Text style={styles.columnLabel}>{label}</Text>
      </View>
      <Amount
        value={amount}
        tone={tone}
        size="large"
        style={{ fontSize: amountFontSize(formatRupiah(amount), 17, 10) }}
      />
      <Text style={styles.columnCount}>{count} aktif</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: Space.lg,
    marginBottom: Space.lg,
  },
  columns: {
    flexDirection: 'row',
    alignItems: 'stretch',
  },
  column: {
    flex: 1,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: Space.xs,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  columnLabel: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
  },
  columnCount: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    marginTop: 2,
  },
  skeletonValue: {
    marginTop: Space.sm,
  },
  divider: {
    width: 1,
    backgroundColor: Colors.line,
    marginHorizontal: Space.md,
  },
  netRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    marginTop: Space.md,
    paddingTop: Space.md,
  },
  netLabel: {
    ...Type.caption,
    color: Colors.inkSoft,
  },
  dueSoon: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Colors.investmentTint,
    borderRadius: 6,
    paddingVertical: Space.sm,
    paddingHorizontal: Space.md,
    marginTop: Space.md,
  },
  dueSoonDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.investment,
  },
  dueSoonText: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.investment,
    flex: 1,
  },
});
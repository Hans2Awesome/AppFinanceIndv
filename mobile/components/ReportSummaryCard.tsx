import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { PeriodReport } from '../types';
import { Colors, Fonts, Space, Type } from '../utils/theme';
import { amountFontSize, formatRupiah } from '../utils/formatRupiah';
import { Card } from './ui/Card';
import { Amount } from './ui/Amount';
import { Skeleton } from './ui/Skeleton';

interface ReportSummaryCardProps {
  report: PeriodReport | null;
}

/** Hero balance block: one large serif figure, three semantic columns. */
export function ReportSummaryCard({ report }: ReportSummaryCardProps) {
  if (!report) {
    return (
      <Card style={styles.card}>
        <Skeleton width="38%" height={11} />
        <Skeleton width="62%" height={40} style={styles.skeletonAmount} />
        <View style={styles.statsRow}>
          {[0, 1, 2].map((index) => (
            <View key={index} style={styles.stat}>
              <Skeleton width="70%" height={10} />
              <Skeleton width="88%" height={14} style={styles.skeletonStat} />
            </View>
          ))}
        </View>
      </Card>
    );
  }

  const net = report.net ?? 0;
  const positive = net >= 0;
  const sign = net > 0 ? '+' : net < 0 ? '−' : '';
  const figure = `${sign}${formatRupiah(Math.abs(net))}`;

  return (
    <Card style={styles.card}>
      <Text style={styles.eyebrow}>{report.title}</Text>
      <Text
        style={[
          Type.hero,
          { fontSize: amountFontSize(figure), lineHeight: amountFontSize(figure) + 4 },
          { color: positive ? Colors.income : Colors.expense },
        ]}
        numberOfLines={1}
        accessibilityLabel={`Sisa bersih ${figure}`}
      >
        {figure}
      </Text>

      <View style={styles.statsRow}>
        <Stat label="Pemasukan" value={report.total_income} tone="income" />
        <View style={styles.divider} />
        <Stat label="Pengeluaran" value={report.total_expense} tone="expense" />
        <View style={styles.divider} />
        <Stat label="Investasi" value={report.total_investment} tone="investment" />
      </View>
    </Card>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'income' | 'expense' | 'investment';
}) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel} numberOfLines={1}>
        {label}
      </Text>
      <Amount
        value={value}
        tone={tone}
        size="large"
        style={{ fontSize: amountFontSize(formatRupiah(value), 17, 10) }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    paddingVertical: Space.xl,
    paddingHorizontal: Space.lg,
    marginBottom: Space.lg,
  },
  eyebrow: {
    ...Type.micro,
    textTransform: 'uppercase',
    marginBottom: Space.sm,
  },
  skeletonAmount: {
    marginBottom: Space.xl,
  },
  skeletonStat: {
    marginTop: Space.sm,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    paddingTop: Space.md,
    marginTop: Space.md,
  },
  stat: {
    flex: 1,
  },
  statLabel: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    marginBottom: Space.xs,
  },
  divider: {
    width: 1,
    backgroundColor: Colors.line,
    marginHorizontal: Space.md,
  },
});
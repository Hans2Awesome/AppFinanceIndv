import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Debt } from '../types';
import { Colors, Fonts, Space } from '../utils/theme';
import { formatDateIndo } from '../utils/formatRupiah';
import { Amount } from './ui/Amount';
import { Progress } from './ui/Progress';

interface DebtCardProps {
  debt: Debt;
  onPress?: () => void;
}

/** Ledger row for one debt or receivable. */
export function DebtCard({ debt, onPress }: DebtCardProps) {
  const isDebt = debt.type === 'debt';
  const tone = isDebt ? 'debt' : 'receivable';
  const accent = isDebt ? Colors.debt : Colors.receivable;
  const remaining = Math.max(debt.total_amount - debt.paid_amount, 0);
  const progress = debt.total_amount > 0 ? (debt.paid_amount / debt.total_amount) * 100 : 0;
  const settled = debt.status === 'settled';

  const dueState = getDueState(debt.due_date, settled);

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={`${isDebt ? 'Hutang' : 'Piutang'} ${debt.person_name}, sisa ${remaining}`}
      style={({ pressed }) => [styles.row, pressed && onPress ? styles.pressed : null]}
    >
      <View style={styles.top}>
        <View style={styles.nameCol}>
          <View style={styles.nameRow}>
            <View style={[styles.dot, { backgroundColor: accent }]} />
            <Text style={[styles.name, settled && styles.settledName]} numberOfLines={1}>
              {debt.person_name}
            </Text>
          </View>
          <Text style={styles.meta} numberOfLines={1}>
            {isDebt ? 'Hutang' : 'Piutang'}
            {debt.due_date ? ` · ${formatDateIndo(debt.due_date)}` : ''}
          </Text>
        </View>

        <View style={styles.amountCol}>
          <Amount value={debt.total_amount} tone={tone} size="large" />
          <Text style={styles.remaining}>
            {settled ? 'Lunas' : `Sisa ${formatShort(debt.total_amount - debt.paid_amount)}`}
          </Text>
        </View>
      </View>

      <View style={styles.progressRow}>
        <Progress value={progress} color={settled ? Colors.income : accent} style={styles.progress} />
        <Text style={styles.percent}>{Math.round(progress)}%</Text>
      </View>

      <View style={styles.badges}>
        <StatusTag
          label={settled ? 'Lunas' : dueState.label}
          color={settled ? Colors.income : dueState.color}
          tint={settled ? Colors.incomeTint : dueState.tint}
        />
      </View>
    </Pressable>
  );
}

function StatusTag({ label, color, tint }: { label: string; color: string; tint: string }) {
  return (
    <View style={[styles.tag, { backgroundColor: tint }]}>
      <Text style={[styles.tagText, { color }]}>{label}</Text>
    </View>
  );
}

function getDueState(dueDate: string | null | undefined, settled: boolean) {
  if (settled || !dueDate) {
    return { label: 'Aktif', color: Colors.inkSoft, tint: Colors.inkTint };
  }
  const now = new Date();
  const due = new Date(`${dueDate}T00:00:00`);
  const days = Math.ceil((due.getTime() - now.getTime()) / 86400000);

  if (days < 0) return { label: 'Lewat tempo', color: Colors.expense, tint: Colors.expenseTint };
  if (days <= 7) return { label: 'Segera', color: Colors.investment, tint: Colors.investmentTint };
  return { label: 'Aktif', color: Colors.inkSoft, tint: Colors.inkTint };
}

function formatShort(value: number): string {
  return `Rp${Math.abs(Math.round(value)).toLocaleString('id-ID')}`;
}

const styles = StyleSheet.create({
  row: {
    paddingVertical: Space.md,
    gap: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  pressed: {
    opacity: 0.7,
  },
  top: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Space.md,
  },
  nameCol: {
    flex: 1,
    minWidth: 0,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  name: {
    fontFamily: Fonts.medium,
    fontSize: 15,
    lineHeight: 20,
    color: Colors.ink,
    flexShrink: 1,
  },
  settledName: {
    color: Colors.inkSoft,
    textDecorationLine: 'line-through',
  },
  meta: {
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkMuted,
    marginTop: 2,
  },
  amountCol: {
    alignItems: 'flex-end',
  },
  remaining: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    marginTop: 2,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
  },
  progress: {
    flex: 1,
  },
  percent: {
    fontFamily: Fonts.medium,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    minWidth: 32,
    textAlign: 'right',
  },
  badges: {
    flexDirection: 'row',
    gap: Space.sm,
  },
  tag: {
    paddingHorizontal: Space.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  tagText: {
    fontFamily: Fonts.medium,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 0.02,
  },
});
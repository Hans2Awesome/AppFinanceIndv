import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Transaction } from '../types';
import { Colors, Fonts, Space } from '../utils/theme';
import { formatDateIndo } from '../utils/formatRupiah';
import { Amount } from './ui/Amount';

interface TransactionCardProps {
  transaction: Transaction;
  onPress?: () => void;
}

const TYPE_META = {
  income: { icon: 'arrow-down' as const, tone: 'income' as const, color: Colors.income, tint: Colors.incomeTint },
  expense: { icon: 'arrow-up' as const, tone: 'expense' as const, color: Colors.expense, tint: Colors.expenseTint },
  investment: {
    icon: 'trending-up' as const,
    tone: 'investment' as const,
    color: Colors.investment,
    tint: Colors.investmentTint,
  },
};

/** One ledger line: type mark, label, signed amount, date. */
export function TransactionCard({ transaction, onPress }: TransactionCardProps) {
  const meta = TYPE_META[transaction.type] ?? TYPE_META.expense;
  const sign = transaction.type === 'income' ? 1 : transaction.type === 'expense' ? -1 : 1;

  const title =
    transaction.category_name || (transaction.asset_name ? transaction.asset_name : 'Lainnya');

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={`${title}, ${formatDateIndo(transaction.transaction_date)}`}
      style={({ pressed }) => [styles.row, pressed && onPress ? styles.pressed : null]}
    >
      <View style={[styles.mark, { backgroundColor: meta.tint }]}>
        <Ionicons name={meta.icon} size={16} color={meta.color} />
      </View>

      <View style={styles.body}>
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {transaction.note || formatDateIndo(transaction.transaction_date)}
        </Text>
      </View>

      <View style={styles.amountCol}>
        <Amount value={sign * transaction.amount} tone={meta.tone} signed />
        <Text style={styles.date}>{formatDateIndo(transaction.transaction_date)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    paddingVertical: Space.md,
    minHeight: 60,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  pressed: {
    opacity: 0.7,
  },
  mark: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    fontFamily: Fonts.medium,
    fontSize: 15,
    lineHeight: 20,
    color: Colors.ink,
  },
  meta: {
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkMuted,
    marginTop: 1,
  },
  amountCol: {
    alignItems: 'flex-end',
  },
  date: {
    fontFamily: Fonts.regular,
    fontSize: 11,
    lineHeight: 15,
    color: Colors.inkMuted,
    marginTop: 2,
  },
});
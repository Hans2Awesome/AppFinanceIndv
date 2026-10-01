import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Transaction } from '../types';
import { Colors } from '../utils/colors';
import { formatDateIndo, formatRupiah } from '../utils/formatRupiah';

interface TransactionCardProps {
  transaction: Transaction;
  onPress?: () => void;
  onDelete?: () => void;
}

export const TransactionCard: React.FC<TransactionCardProps> = ({
  transaction,
  onPress,
}) => {
  const isIncome = transaction.type === 'income';
  const isExpense = transaction.type === 'expense';
  const isInvestment = transaction.type === 'investment';

  const amountColor = isIncome
    ? Colors.income
    : isExpense
    ? Colors.expense
    : Colors.investment;

  const typePrefix = isIncome ? '+' : isExpense ? '-' : '•';

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={styles.container}
    >
      <View
        style={[
          styles.badge,
          {
            backgroundColor: isIncome
              ? Colors.incomeBg
              : isExpense
              ? Colors.expenseBg
              : Colors.investmentBg,
          },
        ]}
      >
        <Text style={[styles.badgeText, { color: amountColor }]}>
          {transaction.category_name ? transaction.category_name[0] : 'T'}
        </Text>
      </View>

      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>
          {transaction.category_name || (isInvestment ? transaction.asset_name : 'Lainnya')}
        </Text>
        <Text style={styles.subtitle} numberOfLines={1}>
          {transaction.note ? transaction.note : formatDateIndo(transaction.transaction_date)}
        </Text>
      </View>

      <View style={styles.amountContainer}>
        <Text style={[styles.amount, { color: amountColor }]}>
          {typePrefix} {formatRupiah(transaction.amount)}
        </Text>
        <Text style={styles.dateText}>
          {formatDateIndo(transaction.transaction_date)}
        </Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    padding: 14,
    borderRadius: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  badge: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  badgeText: {
    fontSize: 18,
    fontWeight: '700',
  },
  content: {
    flex: 1,
    marginRight: 8,
  },
  title: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 2,
  },
  amountContainer: {
    alignItems: 'flex-end',
  },
  amount: {
    fontSize: 15,
    fontWeight: '700',
  },
  dateText: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
});

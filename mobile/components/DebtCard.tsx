import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Debt } from '../types';
import { Colors } from '../utils/colors';
import { formatRupiah, formatDateIndo } from '../utils/formatRupiah';

interface DebtCardProps {
  debt: Debt;
  onPress?: () => void;
}

export const DebtCard: React.FC<DebtCardProps> = ({ debt, onPress }) => {
  const isDebt = debt.type === 'debt';
  const accentColor = isDebt ? Colors.debt : Colors.receivable;
  const bgColor = isDebt ? Colors.debtBg : Colors.receivableBg;
  const remaining = debt.total_amount - debt.paid_amount;
  const progress = debt.total_amount > 0 ? (debt.paid_amount / debt.total_amount) * 100 : 0;
  const isSettled = debt.status === 'settled';

  // Check if due soon (within 7 days)
  const isDueSoon = (() => {
    if (!debt.due_date || isSettled) return false;
    const now = new Date();
    const due = new Date(debt.due_date + 'T00:00:00');
    const diffDays = Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diffDays >= 0 && diffDays <= 7;
  })();

  const isOverdue = (() => {
    if (!debt.due_date || isSettled) return false;
    const now = new Date();
    const due = new Date(debt.due_date + 'T00:00:00');
    return due < now;
  })();

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[styles.container, isSettled && styles.settledContainer]}
    >
      {/* Badge */}
      <View style={[styles.badge, { backgroundColor: bgColor }]}>
        <Text style={[styles.badgeText, { color: accentColor }]}>
          {isDebt ? 'H' : 'P'}
        </Text>
      </View>

      {/* Content */}
      <View style={styles.content}>
        <View style={styles.topRow}>
          <Text style={[styles.personName, isSettled && styles.settledText]} numberOfLines={1}>
            {debt.person_name}
          </Text>
          {isSettled && (
            <View style={styles.settledBadge}>
              <Text style={styles.settledBadgeText}>Lunas</Text>
            </View>
          )}
          {isDueSoon && !isSettled && (
            <View style={styles.dueSoonBadge}>
              <Text style={styles.dueSoonBadgeText}>Segera</Text>
            </View>
          )}
          {isOverdue && !isSettled && (
            <View style={styles.overdueBadge}>
              <Text style={styles.overdueBadgeText}>Lewat</Text>
            </View>
          )}
        </View>

        <Text style={styles.typeLabel}>
          {isDebt ? 'Hutang' : 'Piutang'}
          {debt.due_date ? ` · Jatuh tempo ${formatDateIndo(debt.due_date)}` : ''}
        </Text>

        {/* Progress bar */}
        <View style={styles.progressContainer}>
          <View style={styles.progressBarBg}>
            <View
              style={[
                styles.progressBarFill,
                {
                  width: `${Math.min(progress, 100)}%`,
                  backgroundColor: isSettled ? Colors.success : accentColor,
                },
              ]}
            />
          </View>
          <Text style={styles.progressText}>
            {Math.round(progress)}%
          </Text>
        </View>

        {/* Amount row */}
        <View style={styles.amountRow}>
          <Text style={styles.paidText}>
            Dibayar {formatRupiah(debt.paid_amount)}
          </Text>
          <Text style={[styles.remainingText, { color: isSettled ? Colors.success : accentColor }]}>
            {isSettled ? 'Lunas' : `Sisa ${formatRupiah(remaining)}`}
          </Text>
        </View>
      </View>

      {/* Total amount */}
      <View style={styles.totalContainer}>
        <Text style={[styles.totalAmount, { color: accentColor }]}>
          {formatRupiah(debt.total_amount)}
        </Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: Colors.surface,
    padding: 14,
    borderRadius: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  settledContainer: {
    opacity: 0.65,
  },
  badge: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    marginTop: 2,
  },
  badgeText: {
    fontSize: 18,
    fontWeight: '700',
  },
  content: {
    flex: 1,
    marginRight: 8,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 2,
  },
  personName: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  settledText: {
    textDecorationLine: 'line-through',
  },
  settledBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  settledBadgeText: {
    color: Colors.success,
    fontSize: 10,
    fontWeight: '700',
  },
  dueSoonBadge: {
    backgroundColor: Colors.dueSoonBg,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  dueSoonBadgeText: {
    color: Colors.dueSoon,
    fontSize: 10,
    fontWeight: '700',
  },
  overdueBadge: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  overdueBadgeText: {
    color: Colors.danger,
    fontSize: 10,
    fontWeight: '700',
  },
  typeLabel: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginBottom: 8,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  progressBarBg: {
    flex: 1,
    height: 6,
    backgroundColor: Colors.surfaceLight,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  progressText: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    width: 32,
    textAlign: 'right',
  },
  amountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  paidText: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  remainingText: {
    fontSize: 11,
    fontWeight: '600',
  },
  totalContainer: {
    alignItems: 'flex-end',
    marginTop: 2,
  },
  totalAmount: {
    fontSize: 14,
    fontWeight: '700',
  },
});

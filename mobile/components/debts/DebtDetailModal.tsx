import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Space, Type } from '../../utils/theme';
import { Debt, DebtPayment } from '../../types';
import { debtApi } from '../../services/debts';
import { describeApiError } from '../../services/auth';
import { amountFontSize, formatDateIndo, formatRupiah } from '../../utils/formatRupiah';
import { localTodayIso } from '../../utils/date';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Amount } from '../ui/Amount';
import { Progress } from '../ui/Progress';
import { Sheet } from '../ui/Sheet';

interface DebtDetailModalProps {
  debt: Debt | null;
  visible: boolean;
  onClose: () => void;
  onChanged: () => void;
}

export function DebtDetailModal({ debt, visible, onClose, onChanged }: DebtDetailModalProps) {
  const [record, setRecord] = useState<Debt | null>(debt);
  const [payments, setPayments] = useState<DebtPayment[]>([]);
  const [showPaymentInput, setShowPaymentInput] = useState(false);
  const [payAmount, setPayAmount] = useState('');
  const [payNote, setPayNote] = useState('');
  const [payLoading, setPayLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPayments = useCallback(async (debtId: number) => {
    try {
      setPayments(await debtApi.getPayments(debtId));
      setError(null);
    } catch (err) {
      setError(describeApiError(err, 'Gagal memuat riwayat pembayaran.'));
    }
  }, []);

  useEffect(() => {
    setShowPaymentInput(false);
    setPayAmount('');
    setPayNote('');
    setError(null);
    if (visible && debt) {
      setRecord(debt);
      loadPayments(debt.id);
    }
  }, [debt, loadPayments, visible]);

  if (!record) {
    return null;
  }

  const accent = record.type === 'debt' ? Colors.debt : Colors.receivable;
  const tone = record.type === 'debt' ? 'debt' : 'receivable';
  const paidPercentage =
    record.total_amount > 0 ? Math.min((record.paid_amount / record.total_amount) * 100, 100) : 0;
  const isActive = record.status === 'active';
  const settled = record.status === 'settled';

  const handleAddPayment = async () => {
    const parsedAmount = parseInt(payAmount.replace(/[^0-9]/g, ''), 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Nominal pembayaran harus lebih dari 0.');
      return;
    }

    setPayLoading(true);
    setError(null);
    try {
      await debtApi.addPayment(record.id, {
        amount: parsedAmount,
        note: payNote.trim() || undefined,
        payment_date: localTodayIso(),
      });
      setShowPaymentInput(false);
      setPayAmount('');
      setPayNote('');
      const [updatedDebt] = await Promise.all([
        debtApi.getDebt(record.id),
        loadPayments(record.id),
      ]);
      setRecord(updatedDebt);
      onChanged();
    } catch (err) {
      setError(describeApiError(err, 'Gagal mencatat pembayaran.'));
    } finally {
      setPayLoading(false);
    }
  };

  const handleMarkSettled = () => {
    Alert.alert(
      'Tandai lunas',
      `Tandai ${record.type === 'debt' ? 'hutang' : 'piutang'} kepada ${record.person_name} sebagai lunas?`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Lunas',
          onPress: async () => {
            try {
              setRecord(await debtApi.updateDebt(record.id, { status: 'settled' }));
              onChanged();
            } catch (err) {
              Alert.alert('Error', describeApiError(err, 'Gagal memperbarui status.'));
            }
          },
        },
      ]
    );
  };

  const handleDelete = () => {
    Alert.alert(
      'Hapus',
      `Hapus ${record.type === 'debt' ? 'hutang' : 'piutang'} kepada ${record.person_name}?`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Hapus',
          style: 'destructive',
          onPress: async () => {
            try {
              await debtApi.deleteDebt(record.id);
              onClose();
              onChanged();
            } catch (err) {
              Alert.alert('Error', describeApiError(err, 'Gagal menghapus.'));
            }
          },
        },
      ]
    );
  };

  return (
    <Sheet visible={visible} onClose={onClose} title="Detail catatan">
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {error ? (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {error}
          </Text>
        ) : null}

        <View style={styles.identityRow}>
          <View style={[styles.tag, { backgroundColor: record.type === 'debt' ? Colors.debtTint : Colors.receivableTint }]}>
            <Text style={[styles.tagText, { color: accent }]}>
              {record.type === 'debt' ? 'HUTANG' : 'PIUTANG'}
            </Text>
          </View>
          {settled ? (
            <View style={[styles.tag, { backgroundColor: Colors.incomeTint }]}>
              <Text style={[styles.tagText, { color: Colors.income }]}>LUNAS</Text>
            </View>
          ) : null}
        </View>

        <Text style={styles.person}>{record.person_name}</Text>
        <Amount
          value={record.total_amount}
          tone={tone}
          style={[
            styles.total,
            {
              fontSize: amountFontSize(formatRupiah(record.total_amount), 38, 22),
              lineHeight: amountFontSize(formatRupiah(record.total_amount), 38, 22) + 4,
            },
          ]}
        />

        <View style={styles.progressBlock}>
          <View style={styles.progressLabels}>
            <Text style={styles.progressLabel}>Progress</Text>
            <Text style={styles.progressValue}>{Math.round(paidPercentage)}%</Text>
          </View>
          <Progress value={paidPercentage} color={settled ? Colors.income : accent} />
          <View style={styles.splitRow}>
            <Text style={styles.splitText}>Dibayar {formatRupiah(record.paid_amount)}</Text>
            <Text style={styles.splitText}>
              Sisa {formatRupiah(record.total_amount - record.paid_amount)}
            </Text>
          </View>
        </View>

        {record.due_date ? (
          <View style={styles.infoRow}>
            <Ionicons name="calendar-outline" size={15} color={Colors.inkMuted} />
            <Text style={styles.infoText}>Jatuh tempo {formatDateIndo(record.due_date)}</Text>
          </View>
        ) : null}
        {record.note ? (
          <View style={styles.infoRow}>
            <Ionicons name="document-text-outline" size={15} color={Colors.inkMuted} />
            <Text style={styles.infoText}>{record.note}</Text>
          </View>
        ) : null}

        {isActive ? (
          <View style={styles.actions}>
            <Button
              title={record.type === 'debt' ? 'Catat cicilan' : 'Terima pembayaran'}
              onPress={() => setShowPaymentInput(!showPaymentInput)}
              style={styles.actionPrimary}
            />
            <Button
              title="Lunas"
              variant="secondary"
              icon="checkmark"
              onPress={handleMarkSettled}
              style={styles.actionSecondary}
            />
          </View>
        ) : null}

        {showPaymentInput && isActive ? (
          <Card variant="inset" style={styles.paymentCard}>
            <Text style={styles.cardTitle}>Pembayaran baru</Text>
            <Input
              label="Nominal"
              placeholder="100000"
              value={payAmount}
              onChangeText={setPayAmount}
              keyboardType="numeric"
              leading="Rp"
            />
            <Input
              label="Catatan (opsional)"
              placeholder="Keterangan pembayaran"
              value={payNote}
              onChangeText={setPayNote}
            />
            <Button title="Simpan pembayaran" loading={payLoading} onPress={handleAddPayment} />
          </Card>
        ) : null}

        <Text style={styles.sectionTitle}>Riwayat pembayaran</Text>

        {payments.length === 0 ? (
          <Text style={styles.emptyPayments}>Belum ada pembayaran tercatat.</Text>
        ) : (
          payments.map((payment) => (
            <View key={payment.id} style={styles.paymentRow}>
              <View style={styles.paymentBody}>
                <Text style={styles.paymentNote}>{payment.note || 'Pembayaran'}</Text>
                <Text style={styles.paymentDate}>{formatDateIndo(payment.payment_date)}</Text>
              </View>
              <Amount value={payment.amount} tone="income" />
            </View>
          ))
        )}

        <Pressable
          onPress={handleDelete}
          style={styles.deleteRow}
          accessibilityRole="button"
          accessibilityLabel="Hapus hutang atau piutang"
        >
          <Ionicons name="trash-outline" size={16} color={Colors.danger} />
          <Text style={styles.deleteText}>Hapus catatan</Text>
        </Pressable>
      </ScrollView>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flexGrow: 0,
    flexShrink: 1,
  },
  content: {
    paddingTop: Space.sm,
    paddingBottom: Space.lg,
  },
  error: {
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  identityRow: {
    flexDirection: 'row',
    gap: Space.sm,
    marginBottom: Space.sm,
  },
  tag: {
    paddingHorizontal: Space.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  tagText: {
    fontFamily: Fonts.semibold,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 0.06,
  },
  person: {
    ...Type.h3,
    color: Colors.ink,
  },
  total: {
    fontFamily: Fonts.serif,
    fontSize: 38,
    lineHeight: 42,
    letterSpacing: -0.5,
    marginTop: 2,
  },
  progressBlock: {
    marginTop: Space.lg,
    gap: Space.sm,
    paddingBottom: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  progressLabel: {
    ...Type.caption,
    color: Colors.inkSoft,
  },
  progressValue: {
    ...Type.caption,
    color: Colors.ink,
    fontFamily: Fonts.semibold,
  },
  splitRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  splitText: {
    ...Type.micro,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    paddingVertical: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  infoText: {
    ...Type.body,
    color: Colors.inkSoft,
    flex: 1,
  },
  actions: {
    flexDirection: 'row',
    gap: Space.sm,
    marginTop: Space.lg,
  },
  actionPrimary: {
    flex: 1,
  },
  actionSecondary: {
    flex: 0.55,
  },
  paymentCard: {
    marginTop: Space.lg,
  },
  cardTitle: {
    ...Type.title,
    marginBottom: Space.md,
  },
  sectionTitle: {
    ...Type.title,
    marginTop: Space.xl,
    marginBottom: Space.sm,
  },
  emptyPayments: {
    ...Type.caption,
    paddingVertical: Space.md,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
  },
  paymentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
    paddingVertical: Space.md,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
  },
  paymentBody: {
    flex: 1,
    minWidth: 0,
  },
  paymentNote: {
    ...Type.bodyStrong,
  },
  paymentDate: {
    ...Type.micro,
    marginTop: 2,
  },
  deleteRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    minHeight: 44,
    marginTop: Space.xl,
  },
  deleteText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
  },
});
import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';
import { Colors, Fonts, Space } from '../../utils/theme';
import { DebtType } from '../../types';
import { debtApi } from '../../services/debts';
import { describeApiError } from '../../services/auth';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Sheet } from '../ui/Sheet';
import { Segmented, SegmentedItem } from '../ui/Segmented';

interface CreateDebtModalProps {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const TYPE_ITEMS: ReadonlyArray<SegmentedItem<DebtType>> = [
  { key: 'debt', label: 'Hutang', dotColor: Colors.debt },
  { key: 'receivable', label: 'Piutang', dotColor: Colors.receivable },
];

export function CreateDebtModal({ visible, onClose, onCreated }: CreateDebtModalProps) {
  const [type, setType] = useState<DebtType>('debt');
  const [personName, setPersonName] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setPersonName('');
    setAmount('');
    setNote('');
    setDueDate('');
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const handleCreate = async () => {
    const parsedAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10);

    if (!personName.trim()) {
      setError('Nama orang harus diisi.');
      return;
    }
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Nominal harus lebih dari 0.');
      return;
    }
    if (dueDate.trim() && !ISO_DATE_PATTERN.test(dueDate.trim())) {
      setError('Jatuh tempo harus berformat YYYY-MM-DD.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await debtApi.createDebt({
        type,
        person_name: personName.trim(),
        total_amount: parsedAmount,
        note: note.trim() || undefined,
        due_date: dueDate.trim() || undefined,
      });
      reset();
      onCreated();
    } catch (err) {
      setError(describeApiError(err, 'Gagal membuat hutang/piutang.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Sheet
      visible={visible}
      onClose={close}
      title="Tambah catatan"
      footer={
        <Button
          title="Simpan"
          loading={loading}
          onPress={handleCreate}
          size="lg"
          icon="checkmark"
        />
      }
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <Segmented items={TYPE_ITEMS} value={type} onChange={setType} label="Jenis catatan" />

        {error ? (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {error}
          </Text>
        ) : null}

        <Input
          label="Nama orang"
          placeholder={type === 'debt' ? 'Siapa yang kamu hutangi?' : 'Siapa yang berhutang?'}
          value={personName}
          onChangeText={setPersonName}
          autoCapitalize="words"
        />
        <Input
          label="Nominal"
          placeholder="500000"
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          leading="Rp"
        />
        <Input
          label="Jatuh tempo (opsional)"
          placeholder="2026-12-31"
          value={dueDate}
          onChangeText={setDueDate}
          keyboardType="numbers-and-punctuation"
          hint="Format YYYY-MM-DD"
          autoCapitalize="none"
        />
        <Input
          label="Catatan (opsional)"
          placeholder="Catatan tambahan"
          value={note}
          onChangeText={setNote}
        />
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
    paddingTop: Space.md,
  },
  error: {
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
    marginBottom: Space.md,
  },
});
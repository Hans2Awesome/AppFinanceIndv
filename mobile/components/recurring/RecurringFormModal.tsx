import React, { useEffect, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { Colors, Fonts, Radius, Space } from '../../utils/theme';
import { Category, RecurringFrequency, RecurringTransaction, TransactionType } from '../../types';
import { categoryApi } from '../../services/categories';
import { recurringApi } from '../../services/recurring';
import { describeApiError } from '../../services/auth';
import { localTodayIso } from '../../utils/date';
import {
  WEEKDAY_LABELS,
  WEEKDAY_SHORT,
  typeLabel,
} from '../../utils/recurring';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Sheet } from '../ui/Sheet';
import { Segmented, SegmentedItem } from '../ui/Segmented';
import { Chip } from '../ui/Chip';
import { Checkbox } from '../ui/Checkbox';
import { Skeleton } from '../ui/Skeleton';

interface RecurringFormModalProps {
  visible: boolean;
  schedule: RecurringTransaction | null;
  onClose: () => void;
  onSaved: () => void;
}

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const MONTH_DAYS = Array.from({ length: 31 }, (_, index) => index + 1);

const TYPE_ITEMS: ReadonlyArray<SegmentedItem<TransactionType>> = [
  { key: 'expense', label: 'Pengeluaran', dotColor: Colors.expense },
  { key: 'income', label: 'Pemasukan', dotColor: Colors.income },
  { key: 'investment', label: 'Investasi', dotColor: Colors.investment },
];

const FREQUENCY_ITEMS: ReadonlyArray<SegmentedItem<RecurringFrequency>> = [
  { key: 'weekly', label: 'Mingguan' },
  { key: 'monthly', label: 'Bulanan' },
];

function todayWeekday(): number {
  return (new Date().getDay() + 6) % 7;
}

/** Ruled day grid: seven columns for weekdays and month dates. */
function DayGrid({
  values,
  labels,
  selected,
  onSelect,
  groupLabel,
}: {
  values: readonly number[];
  labels: readonly string[];
  selected: number;
  onSelect: (value: number) => void;
  groupLabel: string;
}) {
  const { width } = useWindowDimensions();
  const cellWidth = Math.max(
    34,
    Math.min(52, Math.floor((width - Space.gutter * 2 - Space.sm * 6) / 7))
  );

  return (
    <View style={styles.grid} accessibilityRole="radiogroup" accessibilityLabel={groupLabel}>
      {values.map((value, index) => {
        const active = value === selected;
        return (
          <Pressable
            key={value}
            onPress={() => onSelect(value)}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            accessibilityLabel={labels[index]}
            style={({ pressed }) => [
              styles.dayCell,
              { width: cellWidth },
              active && styles.dayCellActive,
              pressed && !active ? styles.dayCellPressed : null,
            ]}
          >
            <Text style={[styles.dayText, active && styles.dayTextActive]}>{labels[index]}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function RecurringFormModal({
  visible,
  schedule,
  onClose,
  onSaved,
}: RecurringFormModalProps) {
  const [type, setType] = useState<TransactionType>('expense');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [assetName, setAssetName] = useState('');
  const [frequency, setFrequency] = useState<RecurringFrequency>('monthly');
  const [dayOfWeek, setDayOfWeek] = useState(todayWeekday());
  const [dayOfMonth, setDayOfMonth] = useState(new Date().getDate());
  const [startDate, setStartDate] = useState(localTodayIso());
  const [isActive, setIsActive] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;

    setLoading(false);
    setError(null);

    if (schedule) {
      setType(schedule.type);
      setAmount(String(schedule.amount));
      setNote(schedule.note ?? '');
      setAssetName(schedule.asset_name ?? '');
      setFrequency(schedule.frequency);
      setDayOfWeek(schedule.day_of_week ?? todayWeekday());
      setDayOfMonth(schedule.day_of_month ?? new Date().getDate());
      setStartDate(schedule.start_date);
      setIsActive(schedule.is_active);
      setSelectedCategory(schedule.category_name ?? '');
      return;
    }

    setType('expense');
    setAmount('');
    setNote('');
    setAssetName('');
    setFrequency('monthly');
    setDayOfWeek(todayWeekday());
    setDayOfMonth(new Date().getDate());
    setStartDate(localTodayIso());
    setIsActive(true);
    setSelectedCategory('');
  }, [schedule, visible]);

  useEffect(() => {
    if (!visible) return;

    let active = true;
    setLoadingCategories(true);

    categoryApi
      .getCategories(type)
      .then((items) => {
        if (!active) return;
        setCategories(items);
        setSelectedCategory((current) =>
          items.some((item) => item.name === current) ? current : items[0]?.name ?? ''
        );
      })
      .catch((err) => {
        if (active) setError(describeApiError(err, 'Gagal memuat kategori.'));
      })
      .finally(() => {
        if (active) setLoadingCategories(false);
      });

    return () => {
      active = false;
    };
  }, [type, visible]);

  const handleSubmit = async () => {
    const parsedAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10);

    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Nominal harus lebih dari 0.');
      return;
    }
    if (!ISO_DATE_PATTERN.test(startDate.trim())) {
      setError('Tanggal mulai harus berformat YYYY-MM-DD.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload = {
      type,
      category_name: selectedCategory || undefined,
      amount: parsedAmount,
      note: note.trim() || undefined,
      asset_name: type === 'investment' ? assetName.trim() || undefined : undefined,
      frequency,
      day_of_week: frequency === 'weekly' ? dayOfWeek : null,
      day_of_month: frequency === 'monthly' ? dayOfMonth : null,
      start_date: startDate.trim(),
      is_active: isActive,
    };

    try {
      if (schedule) {
        await recurringApi.updateRecurring(schedule.id, payload);
      } else {
        await recurringApi.createRecurring(payload);
      }
      onSaved();
    } catch (err) {
      setError(
        describeApiError(
          err,
          schedule ? 'Gagal menyimpan perubahan jadwal.' : 'Gagal membuat jadwal.'
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = () => {
    if (!schedule) return;

    Alert.alert(
      'Hapus jadwal',
      `Hentikan jadwal "${note.trim() || schedule.category_name || typeLabel(schedule.type)}"? Transaksi yang sudah tercatat tetap ada.`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Hapus',
          style: 'destructive',
          onPress: async () => {
            try {
              await recurringApi.deleteRecurring(schedule.id);
              onSaved();
            } catch (err) {
              Alert.alert('Error', describeApiError(err, 'Gagal menghapus jadwal.'));
            }
          },
        },
      ]
    );
  };

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      title={schedule ? 'Ubah jadwal' : 'Jadwal baru'}
      footer={
        <Button
          title={schedule ? 'Simpan perubahan' : 'Buat jadwal'}
          loading={loading}
          onPress={handleSubmit}
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
        <Segmented items={TYPE_ITEMS} value={type} onChange={setType} label="Jenis transaksi" />

        {error ? (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {error}
          </Text>
        ) : null}

        <Input
          label="Nominal"
          placeholder="0"
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          leading="Rp"
          fieldStyle={styles.amountField}
        />

        <Text style={styles.fieldLabel}>Kategori</Text>
        {loadingCategories ? (
          <View style={styles.chips}>
            {[88, 104, 76].map((width) => (
              <Skeleton key={width} width={width} height={44} radius={999} />
            ))}
          </View>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chips}
            keyboardShouldPersistTaps="handled"
          >
            {categories.map((category) => (
              <Chip
                key={category.id}
                label={category.name}
                selected={selectedCategory === category.name}
                onPress={() => setSelectedCategory(category.name)}
              />
            ))}
          </ScrollView>
        )}
        <View style={styles.fieldSpacer} />

        <Text style={styles.fieldLabel}>Frekuensi</Text>
        <Segmented
          items={FREQUENCY_ITEMS}
          value={frequency}
          onChange={setFrequency}
          label="Frekuensi transaksi"
        />

        <Text style={styles.fieldLabel}>
          {frequency === 'weekly' ? 'Hari dalam minggu' : 'Tanggal dalam bulan'}
        </Text>
        {frequency === 'weekly' ? (
          <DayGrid
            values={[0, 1, 2, 3, 4, 5, 6]}
            labels={WEEKDAY_SHORT}
            selected={dayOfWeek}
            onSelect={setDayOfWeek}
            groupLabel="Pilih hari"
          />
        ) : (
          <DayGrid
            values={MONTH_DAYS}
            labels={MONTH_DAYS.map(String)}
            selected={dayOfMonth}
            onSelect={setDayOfMonth}
            groupLabel="Pilih tanggal"
          />
        )}
        <Text style={styles.hint}>
          {frequency === 'weekly'
            ? `Berulang setiap ${WEEKDAY_LABELS[dayOfWeek]}.`
            : `Tanggal 29, 30, dan 31 mengikuti hari terakhir bulan pendek.`}
        </Text>

        <Input
          label="Mulai"
          placeholder="2026-11-02"
          value={startDate}
          onChangeText={setStartDate}
          keyboardType="numbers-and-punctuation"
          hint="Format YYYY-MM-DD. Jadwal mulai berjalan dari tanggal ini."
          autoCapitalize="none"
        />

        {type === 'investment' ? (
          <Input
            label="Nama aset (opsional)"
            placeholder="BTC, BBCA, Emas Antam"
            value={assetName}
            onChangeText={setAssetName}
          />
        ) : null}

        <Input
          label="Catatan (opsional)"
          placeholder="Misalnya: gaji bulanan, sewa kos"
          value={note}
          onChangeText={setNote}
        />

        <Checkbox
          checked={isActive}
          onChange={setIsActive}
          label="Jadwal aktif"
          hint="Matikan untuk berhenti membuat transaksi otomatis tanpa menghapus jadwal."
        />

        {schedule ? (
          <Pressable
            onPress={handleDelete}
            style={styles.deleteRow}
            accessibilityRole="button"
            accessibilityLabel="Hapus jadwal"
          >
            <Text style={styles.deleteText}>Hapus jadwal</Text>
          </Pressable>
        ) : null}
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
    paddingBottom: Space.sm,
  },
  amountField: {
    fontFamily: Fonts.serif,
    fontSize: 34,
    lineHeight: 40,
    letterSpacing: -0.4,
  },
  fieldLabel: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
    marginBottom: Space.xs,
  },
  fieldSpacer: {
    height: Space.lg,
  },
  chips: {
    flexDirection: 'row',
    gap: Space.sm,
    paddingVertical: Space.xs,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    columnGap: Space.sm,
    rowGap: Space.sm,
    marginBottom: Space.sm,
  },
  dayCell: {
    minHeight: 44,
    borderRadius: Radius.control,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayCellActive: {
    backgroundColor: Colors.ink,
    borderColor: Colors.ink,
  },
  dayCellPressed: {
    backgroundColor: Colors.surfaceAlt,
  },
  dayText: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
  },
  dayTextActive: {
    color: Colors.onInk,
  },
  hint: {
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 17,
    color: Colors.inkMuted,
    marginBottom: Space.lg,
  },
  error: {
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  deleteRow: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Space.sm,
  },
  deleteText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
  },
});
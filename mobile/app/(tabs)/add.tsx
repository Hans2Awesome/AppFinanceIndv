import React, { useState, useEffect } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Colors, Fonts, Space, Type } from '../../utils/theme';
import { Category, TransactionType } from '../../types';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Screen } from '../../components/ui/Screen';
import { Segmented, SegmentedItem } from '../../components/ui/Segmented';
import { Chip } from '../../components/ui/Chip';
import { Skeleton } from '../../components/ui/Skeleton';
import { FadeIn } from '../../components/ui/FadeIn';
import { categoryApi } from '../../services/categories';
import { transactionApi } from '../../services/transactions';
import { describeApiError } from '../../services/auth';
import { localTodayIso } from '../../utils/date';

const TYPE_ITEMS: ReadonlyArray<SegmentedItem<TransactionType>> = [
  { key: 'expense', label: 'Pengeluaran', dotColor: Colors.expense },
  { key: 'income', label: 'Pemasukan', dotColor: Colors.income },
  { key: 'investment', label: 'Investasi', dotColor: Colors.investment },
];

export default function AddTransactionScreen() {
  const [type, setType] = useState<TransactionType>('expense');
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [assetName, setAssetName] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingCategories(true);

    categoryApi
      .getCategories(type)
      .then((cats) => {
        if (!active) return;
        setCategories(cats);
        setSelectedCategory(cats.length > 0 ? cats[0].name : '');
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
  }, [type]);

  const handleSave = async () => {
    const parsedAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Nominal harus lebih dari 0.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await transactionApi.createTransaction({
        type,
        amount: parsedAmount,
        category_name: selectedCategory || 'Lainnya',
        note: note.trim() || undefined,
        asset_name: type === 'investment' ? assetName.trim() || undefined : undefined,
        transaction_date: localTodayIso(),
      });

      setAmount('');
      setNote('');
      setAssetName('');

      Alert.alert('Tersimpan', 'Transaksi berhasil dicatat.', [
        { text: 'OK', onPress: () => router.push('/(tabs)') },
      ]);
    } catch (err) {
      setError(describeApiError(err, 'Gagal menyimpan transaksi.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen
      footer={
        <View style={styles.footer}>
          <Button title="Simpan transaksi" loading={loading} onPress={handleSave} size="lg" />
        </View>
      }
    >
      <FadeIn>
        <Text style={styles.title}>Catat transaksi</Text>
        <Segmented items={TYPE_ITEMS} value={type} onChange={setType} label="Jenis transaksi" />
      </FadeIn>

      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : null}

      <FadeIn delay={60}>
        <Input
          label="Nominal"
          placeholder="0"
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          leading="Rp"
          fieldStyle={styles.amountField}
        />
      </FadeIn>

      <FadeIn delay={90}>
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
            {categories.map((cat) => (
              <Chip
                key={cat.id}
                label={cat.name}
                selected={selectedCategory === cat.name}
                onPress={() => setSelectedCategory(cat.name)}
              />
            ))}
          </ScrollView>
        )}
        <View style={styles.chipsSpacer} />
      </FadeIn>

      <FadeIn delay={120}>
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
          placeholder="Catatan tambahan"
          value={note}
          onChangeText={setNote}
          returnKeyType="done"
        />
      </FadeIn>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    ...Type.h1,
    marginBottom: Space.lg,
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
  chips: {
    flexDirection: 'row',
    gap: Space.sm,
    paddingVertical: Space.xs,
  },
  chipsSpacer: {
    height: Space.lg,
  },
  error: {
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  footer: {
    paddingHorizontal: Space.gutter,
    paddingTop: Space.md,
    paddingBottom: Space.md,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    backgroundColor: Colors.paper,
  },
});
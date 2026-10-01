import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
  Alert,
} from 'react-native';
import { router } from 'expo-router';
import { Colors } from '../../utils/colors';
import { Category, TransactionType } from '../../types';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { categoryApi } from '../../services/categories';
import { transactionApi } from '../../services/transactions';

export default function AddTransactionScreen() {
  const [type, setType] = useState<TransactionType>('expense');
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [assetName, setAssetName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    categoryApi.getCategories(type).then((cats) => {
      setCategories(cats);
      if (cats.length > 0) {
        setSelectedCategory(cats[0].name);
      }
    });
  }, [type]);

  const handleSave = async () => {
    const parsedAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Nominal harus lebih dari 0.');
      return;
    }

    setLoading(true);
    setError(null);

    const todayStr = new Date().toISOString().split('T')[0];

    try {
      await transactionApi.createTransaction({
        type,
        amount: parsedAmount,
        category_name: selectedCategory || 'Lainnya',
        note: note.trim() || undefined,
        asset_name: type === 'investment' ? assetName.trim() || undefined : undefined,
        transaction_date: todayStr,
      });

      // Clear form
      setAmount('');
      setNote('');
      setAssetName('');

      Alert.alert('Sukses', 'Transaksi berhasil disimpan!', [
        { text: 'OK', onPress: () => router.push('/(tabs)') },
      ]);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Gagal menyimpan transaksi.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.pageTitle}>Catat Transaksi</Text>

        {/* Type Selector Tabs */}
        <View style={styles.typeSelector}>
          <TouchableOpacity
            style={[
              styles.typeTab,
              type === 'expense' && styles.typeTabActiveExpense,
            ]}
            onPress={() => setType('expense')}
          >
            <Text
              style={[
                styles.typeTabText,
                type === 'expense' && styles.typeTabTextActive,
              ]}
            >
              Pengeluaran
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.typeTab,
              type === 'income' && styles.typeTabActiveIncome,
            ]}
            onPress={() => setType('income')}
          >
            <Text
              style={[
                styles.typeTabText,
                type === 'income' && styles.typeTabTextActive,
              ]}
            >
              Pemasukan
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.typeTab,
              type === 'investment' && styles.typeTabActiveInvest,
            ]}
            onPress={() => setType('investment')}
          >
            <Text
              style={[
                styles.typeTabText,
                type === 'investment' && styles.typeTabTextActive,
              ]}
            >
              Investasi
            </Text>
          </TouchableOpacity>
        </View>

        {error && <Text style={styles.errorText}>{error}</Text>}

        {/* Amount Input */}
        <Input
          label="Nominal (Rp)"
          placeholder="Contoh: 50000"
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          style={styles.amountInput}
        />

        {/* Category Picker */}
        <Text style={styles.fieldLabel}>Kategori</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.categoryScroll}
          contentContainerStyle={styles.categoryContainer}
        >
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat.name;
            return (
              <TouchableOpacity
                key={cat.id}
                onPress={() => setSelectedCategory(cat.name)}
                style={[
                  styles.categoryChip,
                  isSelected && styles.categoryChipSelected,
                ]}
              >
                <Text
                  style={[
                    styles.categoryChipText,
                    isSelected && styles.categoryChipTextSelected,
                  ]}
                >
                  {cat.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Investment Asset Name */}
        {type === 'investment' && (
          <Input
            label="Nama Aset (Opsional)"
            placeholder="Contoh: BTC, BBCA, Emas Antam"
            value={assetName}
            onChangeText={setAssetName}
          />
        )}

        {/* Notes */}
        <Input
          label="Catatan (Opsional)"
          placeholder="Catatan tambahan..."
          value={note}
          onChangeText={setNote}
        />

        {/* Submit Button */}
        <Button
          title="Simpan Transaksi"
          loading={loading}
          onPress={handleSave}
          style={styles.submitBtn}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  container: {
    padding: 20,
    paddingBottom: 40,
  },
  pageTitle: {
    color: Colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 20,
    marginTop: 8,
  },
  typeSelector: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    padding: 4,
    borderRadius: 14,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  typeTab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 10,
  },
  typeTabActiveExpense: {
    backgroundColor: Colors.expense,
  },
  typeTabActiveIncome: {
    backgroundColor: Colors.income,
  },
  typeTabActiveInvest: {
    backgroundColor: Colors.investment,
  },
  typeTabText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  typeTabTextActive: {
    color: '#fff',
    fontWeight: '700',
  },
  amountInput: {
    fontSize: 20,
    fontWeight: '700',
  },
  fieldLabel: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 8,
  },
  categoryScroll: {
    marginBottom: 20,
  },
  categoryContainer: {
    gap: 8,
  },
  categoryChip: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
  },
  categoryChipSelected: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  categoryChipText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  categoryChipTextSelected: {
    color: '#fff',
    fontWeight: '600',
  },
  submitBtn: {
    marginTop: 12,
  },
  errorText: {
    color: Colors.danger,
    fontSize: 13,
    marginBottom: 16,
    textAlign: 'center',
  },
});

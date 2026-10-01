import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { QuickInputPreview } from '../types';
import { Colors } from '../utils/colors';
import { formatRupiah } from '../utils/formatRupiah';
import { transactionApi } from '../services/transactions';

interface QuickInputBarProps {
  onSuccess?: () => void;
}

export const QuickInputBar: React.FC<QuickInputBarProps> = ({ onSuccess }) => {
  const [text, setText] = useState('');
  const [preview, setPreview] = useState<QuickInputPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTextChange = async (value: string) => {
    setText(value);
    setError(null);

    if (value.trim().length > 3) {
      setLoading(true);
      try {
        const res = await transactionApi.previewQuickInput(value);
        if (res.is_valid) {
          setPreview(res);
          setError(null);
        } else {
          setPreview(null);
        }
      } catch {
        setPreview(null);
      } finally {
        setLoading(false);
      }
    } else {
      setPreview(null);
    }
  };

  const handleSave = async () => {
    if (!text.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await transactionApi.confirmQuickInput(text);
      setText('');
      setPreview(null);
      onSuccess?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Gagal menyimpan transaksi.');
    } finally {
      setSaving(false);
    }
  };

  const getTypeColor = (type?: string | null) => {
    if (type === 'income') return Colors.income;
    if (type === 'expense') return Colors.expense;
    return Colors.investment;
  };

  return (
    <View style={styles.container}>
      <View style={styles.inputRow}>
        <TextInput
          value={text}
          onChangeText={handleTextChange}
          placeholder='Input cepat: "makan 25000", "gaji 5jt"'
          placeholderTextColor={Colors.textMuted}
          style={styles.input}
          returnKeyType="done"
          onSubmitEditing={handleSave}
        />
        {loading && (
          <ActivityIndicator
            size="small"
            color={Colors.primary}
            style={styles.loader}
          />
        )}
      </View>

      {error && <Text style={styles.errorText}>{error}</Text>}

      {preview && preview.is_valid && (
        <View style={styles.previewCard}>
          <View style={styles.previewInfo}>
            <View
              style={[
                styles.typeTag,
                { backgroundColor: getTypeColor(preview.type) + '20' },
              ]}
            >
              <Text
                style={[
                  styles.typeTagText,
                  { color: getTypeColor(preview.type) },
                ]}
              >
                {preview.type_label || preview.type}
              </Text>
            </View>

            <Text style={styles.previewCategory}>
              {preview.category_name}
            </Text>

            <Text style={styles.previewAmount}>
              {formatRupiah(preview.amount || 0)}
            </Text>
          </View>

          <TouchableOpacity
            style={styles.saveBtn}
            onPress={handleSave}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.saveBtnText}>Simpan</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: 20,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 14,
    paddingHorizontal: 14,
  },
  input: {
    flex: 1,
    height: 48,
    color: Colors.text,
    fontSize: 14,
  },
  loader: {
    marginLeft: 8,
  },
  errorText: {
    color: Colors.danger,
    fontSize: 12,
    marginTop: 6,
    marginLeft: 4,
  },
  previewCard: {
    marginTop: 10,
    backgroundColor: Colors.surfaceLight,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 12,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  previewInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    flexWrap: 'wrap',
    gap: 8,
  },
  typeTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  typeTagText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  previewCategory: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  previewAmount: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  saveBtn: {
    backgroundColor: Colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    marginLeft: 10,
  },
  saveBtnText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
});

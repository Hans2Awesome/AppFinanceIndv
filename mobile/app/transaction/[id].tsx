import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space, Type } from '../../utils/theme';
import { Category, Transaction, TransactionType } from '../../types';
import { transactionApi } from '../../services/transactions';
import { categoryApi } from '../../services/categories';
import { describeApiError } from '../../services/auth';
import { amountFontSize, formatDateIndo, formatRupiah } from '../../utils/formatRupiah';
import {
  MAX_ASSET_NAME_LENGTH,
  MAX_TRANSACTION_NOTE_LENGTH,
  buildTransactionUpdatePayload,
  canDeleteTransaction,
  canEditTransaction,
  hasTransactionChanges,
  transactionTypeLabel,
  validateTransactionDraft,
} from '../../utils/transactions';
import { Screen } from '../../components/ui/Screen';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Chip } from '../../components/ui/Chip';
import { Amount } from '../../components/ui/Amount';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton, SkeletonRows } from '../../components/ui/Skeleton';
import { FadeIn } from '../../components/ui/FadeIn';

const TYPE_META: Record<
  TransactionType,
  {
    tone: 'income' | 'expense' | 'investment';
    color: string;
    tint: string;
    icon: keyof typeof Ionicons.glyphMap;
  }
> = {
  income: {
    tone: 'income',
    color: Colors.income,
    tint: Colors.incomeTint,
    icon: 'arrow-down',
  },
  expense: {
    tone: 'expense',
    color: Colors.expense,
    tint: Colors.expenseTint,
    icon: 'arrow-up',
  },
  investment: {
    tone: 'investment',
    color: Colors.investment,
    tint: Colors.investmentTint,
    icon: 'trending-up',
  },
};

export default function TransactionDetailScreen() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const rawId = Array.isArray(params.id) ? params.id[0] : params.id;
  const transactionId = Number.parseInt(String(rawId ?? ''), 10);
  const validId = Number.isSafeInteger(transactionId) && transactionId > 0;

  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [amount, setAmount] = useState('');
  const [transactionDate, setTransactionDate] = useState('');
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [assetName, setAssetName] = useState('');

  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);
  const draftHydratedForIdRef = useRef<number | null>(null);
  const savingRef = useRef(false);
  const deletingRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const hydrateDraft = useCallback((tx: Transaction) => {
    setAmount(String(tx.amount));
    setTransactionDate(tx.transaction_date);
    setSelectedCategoryId(tx.category_id ?? null);
    setNote(tx.note ?? '');
    setAssetName(tx.asset_name ?? '');
    draftHydratedForIdRef.current = tx.id;
  }, []);

  const loadCategories = useCallback(async (type: TransactionType) => {
    const currentRequest = requestIdRef.current;
    setLoadingCategories(true);
    setCategoryError(null);
    try {
      const items = await categoryApi.getCategories(type);
      if (!mountedRef.current || currentRequest !== requestIdRef.current) return;
      setCategories(items);
    } catch (err) {
      if (!mountedRef.current || currentRequest !== requestIdRef.current) return;
      setCategoryError(describeApiError(err, 'Gagal memuat daftar kategori.'));
    } finally {
      if (mountedRef.current && currentRequest === requestIdRef.current) {
        setLoadingCategories(false);
      }
    }
  }, []);

  const loadDetail = useCallback(
    async (options?: { forceResetDraft?: boolean }) => {
      if (!validId) {
        setLoading(false);
        setLoadError('ID transaksi tidak valid.');
        return;
      }

      const currentRequest = ++requestIdRef.current;
      setLoading(true);
      setLoadError(null);

      try {
        const tx = await transactionApi.getTransaction(transactionId);
        if (!mountedRef.current || currentRequest !== requestIdRef.current) {
          return;
        }
        setTransaction(tx);

        if (options?.forceResetDraft || draftHydratedForIdRef.current !== tx.id) {
          hydrateDraft(tx);
        }

        if (canEditTransaction(tx)) {
          await loadCategories(tx.type);
        }
      } catch (err) {
        if (!mountedRef.current || currentRequest !== requestIdRef.current) {
          return;
        }
        setLoadError(
          describeApiError(
            err,
            'Gagal memuat detail transaksi. Periksa koneksi lalu coba lagi.'
          )
        );
      } finally {
        if (mountedRef.current && currentRequest === requestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [hydrateDraft, loadCategories, transactionId, validId]
  );

  useEffect(() => {
    draftHydratedForIdRef.current = null;
    loadDetail({ forceResetDraft: true });
  }, [loadDetail]);

  const editable = canEditTransaction(transaction);
  const deletable = canDeleteTransaction(transaction);
  const busy = saving || deleting;

  const handleOpenHistory = () => {
    if (!validId) return;
    router.push({
      pathname: '/transaction-history',
      params: { transaction_id: String(transactionId) },
    });
  };

  const handleSave = async () => {
    if (!transaction || loadError || loading || !editable || savingRef.current || deletingRef.current) {
      return;
    }

    const draft = {
      amount,
      transactionDate,
      categoryId: selectedCategoryId,
      note,
      assetName,
      type: transaction.type,
    };

    const validationError = validateTransactionDraft(draft);
    if (validationError) {
      setFormError(validationError);
      return;
    }

    const payload = buildTransactionUpdatePayload(transaction, draft);
    if (!hasTransactionChanges(payload)) {
      setFormError('Belum ada perubahan untuk disimpan.');
      return;
    }

    savingRef.current = true;
    setSaving(true);
    setFormError(null);

    try {
      const updated = await transactionApi.updateTransaction(transaction.id, payload);
      if (!mountedRef.current) return;
      setTransaction(updated);
      hydrateDraft(updated);
      Alert.alert('Tersimpan', 'Perubahan transaksi berhasil disimpan.', [
        {
          text: 'OK',
          onPress: () => {
            if (mountedRef.current) {
              router.back();
            }
          },
        },
      ]);
    } catch (err) {
      if (!mountedRef.current) return;
      setFormError(describeApiError(err, 'Gagal menyimpan perubahan transaksi.'));
    } finally {
      savingRef.current = false;
      if (mountedRef.current) {
        setSaving(false);
      }
    }
  };

  const performDelete = async () => {
    if (!transaction || loadError || loading || !deletable || savingRef.current || deletingRef.current) {
      return;
    }

    deletingRef.current = true;
    setDeleting(true);
    setFormError(null);

    try {
      await transactionApi.deleteTransaction(transaction.id);
      if (!mountedRef.current) return;
      router.back();
    } catch (err) {
      if (!mountedRef.current) return;
      setFormError(describeApiError(err, 'Gagal menghapus transaksi.'));
    } finally {
      deletingRef.current = false;
      if (mountedRef.current) {
        setDeleting(false);
      }
    }
  };

  const handleConfirmDelete = () => {
    if (!transaction || !deletable || savingRef.current || deletingRef.current) {
      return;
    }

    const label =
      transaction.category_name ||
      transaction.asset_name ||
      transactionTypeLabel(transaction.type);

    Alert.alert(
      'Hapus transaksi',
      `Hapus transaksi "${label}" sebesar ${formatRupiah(transaction.amount)}? Catatan dihapus dari laporan aktif tetapi tetap tercatat di riwayat perubahan.`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Hapus',
          style: 'destructive',
          onPress: () => {
            void performDelete();
          },
        },
      ]
    );
  };

  const meta = transaction ? TYPE_META[transaction.type] : TYPE_META.expense;
  const heroText = transaction ? formatRupiah(transaction.amount) : 'Rp0';
  const heroSize = amountFontSize(heroText, 40, 24);

  return (
    <Screen
      bottomInset
      keyboardBehavior="padding"
      footer={
        transaction && editable && !loadError ? (
          <View style={styles.footer}>
            <Button
              title="Simpan perubahan"
              loading={saving}
              disabled={busy}
              onPress={handleSave}
              size="lg"
              icon="checkmark"
            />
          </View>
        ) : undefined
      }
    >
      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          style={styles.back}
          accessibilityRole="button"
          accessibilityLabel="Kembali"
        >
          <Ionicons name="arrow-back" size={20} color={Colors.ink} />
        </Pressable>
        <Text style={styles.title} numberOfLines={1}>
          Detail transaksi
        </Text>
        {validId ? (
          <Pressable
            onPress={handleOpenHistory}
            hitSlop={8}
            style={({ pressed }) => [styles.historyAction, pressed ? styles.pressed : null]}
            accessibilityRole="button"
            accessibilityLabel="Lihat riwayat perubahan transaksi ini"
          >
            <Ionicons name="time-outline" size={16} color={Colors.inkSoft} />
            <Text style={styles.historyActionText}>Riwayat</Text>
          </Pressable>
        ) : null}
      </View>

      {loadError ? (
        <View style={styles.errorWrap}>
          <ErrorState
            message={loadError}
            onRetry={() => loadDetail({ forceResetDraft: false })}
          />
          {validId ? (
            <Button
              title="Lihat riwayat transaksi ini"
              variant="secondary"
              icon="time-outline"
              onPress={handleOpenHistory}
            />
          ) : null}
        </View>
      ) : null}

      {loading && !transaction ? (
        <View style={styles.loadingBlock}>
          <SkeletonRows count={5} />
        </View>
      ) : null}

      {transaction ? (
        <>
          <FadeIn>
            <View style={styles.heroBlock}>
              <View style={styles.badgeRow}>
                <View style={[styles.typeBadge, { backgroundColor: meta.tint }]}>
                  <Ionicons name={meta.icon} size={14} color={meta.color} />
                  <Text style={[styles.typeBadgeText, { color: meta.color }]}>
                    {transactionTypeLabel(transaction.type).toUpperCase()}
                  </Text>
                </View>
                <Text style={styles.ImmutableHint}>Jenis tetap</Text>
              </View>

              <Amount
                value={transaction.amount}
                tone={meta.tone}
                style={[
                  styles.heroAmount,
                  { fontSize: heroSize, lineHeight: heroSize + 4 },
                ]}
              />

              <View style={styles.heroMetaRow}>
                <Text style={styles.heroMetaLabel}>
                  {transaction.category_name || 'Tanpa kategori'}
                </Text>
                <Text style={styles.heroMetaDate}>
                  {formatDateIndo(transaction.transaction_date)}
                </Text>
              </View>
            </View>
          </FadeIn>

          {!editable && !deletable ? (
            <FadeIn delay={60}>
              <View style={styles.lockedBlock}>
                <View style={styles.lockedHeader}>
                  <Ionicons name="swap-horizontal-outline" size={18} color={Colors.debt} />
                  <Text style={styles.lockedTitle}>Terkait Hutang & Piutang</Text>
                </View>
                <Text style={styles.lockedBody}>
                  Transaksi kas ini dibuat otomatis dari pencatatan atau pembayaran hutang/piutang.
                  Untuk mengubah nominal atau menghapus catatan, kelola langsung melalui menu Hutang & Piutang.
                </Text>

                <View style={styles.readOnlyList}>
                  <ReadOnlyRow
                    label="Kategori"
                    value={transaction.category_name || 'Tanpa kategori'}
                  />
                  <ReadOnlyRow
                    label="Tanggal"
                    value={formatDateIndo(transaction.transaction_date)}
                  />
                  {transaction.asset_name ? (
                    <ReadOnlyRow label="Nama aset" value={transaction.asset_name} />
                  ) : null}
                  <ReadOnlyRow
                    label="Catatan"
                    value={transaction.note || 'Tidak ada catatan'}
                    last
                  />
                </View>

                <Button
                  title="Buka Hutang & Piutang"
                  variant="secondary"
                  icon="open-outline"
                  onPress={() => router.push('/debts')}
                />
              </View>
            </FadeIn>
          ) : (
            <FadeIn delay={60}>
              {formError ? (
                <Text style={styles.formError} accessibilityLiveRegion="polite">
                  {formError}
                </Text>
              ) : null}

              <Input
                label="Nominal"
                placeholder="0"
                value={amount}
                onChangeText={setAmount}
                keyboardType="numeric"
                leading="Rp"
                editable={editable && !busy}
                fieldStyle={styles.amountField}
              />

              <Input
                label="Tanggal transaksi"
                placeholder="YYYY-MM-DD"
                value={transactionDate}
                onChangeText={setTransactionDate}
                keyboardType="numbers-and-punctuation"
                autoCapitalize="none"
                editable={editable && !busy}
                hint="Format YYYY-MM-DD, misalnya 2026-11-09."
              />

              <View style={styles.categorySection}>
                <View style={styles.categoryHeader}>
                  <Text style={styles.fieldLabel}>Kategori</Text>
                  {selectedCategoryId !== null ? (
                    <Pressable
                      onPress={() => { if (!busy) setSelectedCategoryId(null); }}
                      disabled={busy}
                      hitSlop={8}
                      accessibilityRole="button"
                      accessibilityLabel="Kosongkan kategori"
                    >
                      <Text style={styles.clearLink}>Tanpa kategori</Text>
                    </Pressable>
                  ) : null}
                </View>

                {categoryError ? (
                  <ErrorState
                    message={categoryError}
                    onRetry={() => loadCategories(transaction.type)}
                  />
                ) : loadingCategories ? (
                  <View style={styles.chips}>
                    {[88, 108, 76].map((width) => (
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
                    <Chip
                      label="Tanpa kategori"
                      selected={selectedCategoryId === null}
                      onPress={() => setSelectedCategoryId(null)}
                    />
                    {categories.map((cat) => (
                      <Chip
                        key={cat.id}
                        label={cat.name}
                        selected={selectedCategoryId === cat.id}
                        onPress={() => { if (!busy) setSelectedCategoryId(cat.id); }}
                      />
                    ))}
                  </ScrollView>
                )}
              </View>

              {transaction.type === 'investment' ? (
                <View>
                  <Input
                    label="Nama aset (opsional)"
                    placeholder="BTC, BBCA, Emas Antam"
                    value={assetName}
                    onChangeText={setAssetName}
                    maxLength={MAX_ASSET_NAME_LENGTH}
                    editable={editable && !busy}
                    hint="Kosongkan untuk menghapus nama aset."
                  />
                  {assetName.trim().length > 0 ? (
                    <Pressable
                      onPress={() => setAssetName('')}
                      disabled={busy}
                      hitSlop={8}
                      style={styles.inlineClear}
                      accessibilityRole="button"
                      accessibilityLabel="Hapus nama aset"
                    >
                      <Text style={styles.clearLink}>Kosongkan nama aset</Text>
                    </Pressable>
                  ) : null}
                </View>
              ) : null}

              <View>
                <Input
                  label="Catatan (opsional)"
                  placeholder="Catatan tambahan"
                  value={note}
                  onChangeText={setNote}
                  maxLength={MAX_TRANSACTION_NOTE_LENGTH}
                  editable={editable && !busy}
                  returnKeyType="done"
                  hint="Kosongkan untuk menghapus catatan."
                />
                {note.trim().length > 0 ? (
                  <Pressable
                    onPress={() => setNote('')}
                    disabled={busy}
                    hitSlop={8}
                    style={styles.inlineClear}
                    accessibilityRole="button"
                    accessibilityLabel="Hapus catatan"
                  >
                    <Text style={styles.clearLink}>Kosongkan catatan</Text>
                  </Pressable>
                ) : null}
              </View>

              {deletable ? (
                <View style={styles.deleteSection}>
                  <Button
                    title="Hapus transaksi"
                    variant="danger"
                    icon="trash-outline"
                    loading={deleting}
                    disabled={busy}
                    onPress={handleConfirmDelete}
                  />
                </View>
              ) : null}
            </FadeIn>
          )}
        </>
      ) : null}
    </Screen>
  );
}

function ReadOnlyRow({
  label,
  value,
  last = false,
}: {
  label: string;
  value: string;
  last?: boolean;
}) {
  return (
    <View style={[styles.readOnlyRow, last && styles.readOnlyRowLast]}>
      <Text style={styles.readOnlyLabel}>{label}</Text>
      <Text style={styles.readOnlyValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginBottom: Space.md,
  },
  back: {
    width: 44,
    height: 44,
    alignItems: 'flex-start',
    justifyContent: 'center',
    marginLeft: -Space.sm,
  },
  title: {
    ...Type.h2,
    flex: 1,
  },
  historyAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.xs,
    minHeight: 44,
    paddingHorizontal: Space.sm,
  },
  historyActionText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.inkSoft,
  },
  pressed: {
    opacity: 0.75,
  },
  errorWrap: {
    gap: Space.sm,
    marginBottom: Space.lg,
  },
  loadingBlock: {
    paddingTop: Space.lg,
  },
  heroBlock: {
    paddingBottom: Space.lg,
    marginBottom: Space.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Space.sm,
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.xs,
    paddingHorizontal: Space.sm,
    paddingVertical: 4,
    borderRadius: Radius.control,
  },
  typeBadgeText: {
    fontFamily: Fonts.semibold,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.06,
  },
  ImmutableHint: {
    ...Type.micro,
  },
  heroAmount: {
    fontFamily: Fonts.serif,
    letterSpacing: -0.5,
  },
  heroMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
    marginTop: Space.sm,
  },
  heroMetaLabel: {
    ...Type.bodyStrong,
    color: Colors.inkSoft,
    flex: 1,
  },
  heroMetaDate: {
    ...Type.caption,
  },
  formError: {
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
    marginBottom: Space.md,
  },
  amountField: {
    fontFamily: Fonts.serif,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.4,
  },
  categorySection: {
    marginBottom: Space.lg,
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Space.xs,
  },
  fieldLabel: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
  },
  clearLink: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
    textDecorationLine: 'underline',
  },
  inlineClear: {
    alignSelf: 'flex-end',
    marginTop: -Space.sm,
    marginBottom: Space.md,
    minHeight: 32,
    justifyContent: 'center',
  },
  chips: {
    flexDirection: 'row',
    gap: Space.sm,
    paddingVertical: Space.xs,
  },
  deleteSection: {
    marginTop: Space.md,
    paddingTop: Space.lg,
    borderTopWidth: 1,
    borderTopColor: Colors.line,
  },
  lockedBlock: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.block,
    padding: Space.lg,
    gap: Space.md,
  },
  lockedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
  },
  lockedTitle: {
    ...Type.title,
  },
  lockedBody: {
    ...Type.body,
    color: Colors.inkSoft,
  },
  readOnlyList: {
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    marginTop: Space.xs,
  },
  readOnlyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
    paddingVertical: Space.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
  },
  readOnlyRowLast: {
    borderBottomWidth: 0,
  },
  readOnlyLabel: {
    ...Type.caption,
    color: Colors.inkSoft,
  },
  readOnlyValue: {
    ...Type.bodyStrong,
    flexShrink: 1,
    textAlign: 'right',
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

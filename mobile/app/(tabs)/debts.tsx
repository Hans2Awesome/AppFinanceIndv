import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
  RefreshControl,
  Modal,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../utils/colors';
import { Debt, DebtSummary, DebtType, DebtStatus, DebtPayment } from '../../types';
import { DebtCard } from '../../components/DebtCard';
import { DebtSummaryCard } from '../../components/DebtSummaryCard';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { debtApi } from '../../services/debts';
import { formatRupiah, formatDateIndo } from '../../utils/formatRupiah';

type FilterTab = 'all' | 'debt' | 'receivable' | 'settled';

export default function DebtsScreen() {
  const [filter, setFilter] = useState<FilterTab>('all');
  const [debts, setDebts] = useState<Debt[]>([]);
  const [summary, setSummary] = useState<DebtSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createType, setCreateType] = useState<DebtType>('debt');
  const [personName, setPersonName] = useState('');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Detail modal state
  const [selectedDebt, setSelectedDebt] = useState<Debt | null>(null);
  const [payments, setPayments] = useState<DebtPayment[]>([]);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showPaymentInput, setShowPaymentInput] = useState(false);
  const [payAmount, setPayAmount] = useState('');
  const [payNote, setPayNote] = useState('');
  const [payLoading, setPayLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const filterParams: { type?: DebtType; status?: DebtStatus } = {};
      if (filter === 'debt') filterParams.type = 'debt';
      if (filter === 'receivable') filterParams.type = 'receivable';
      if (filter === 'settled') filterParams.status = 'settled';

      const [debtData, summaryData] = await Promise.all([
        debtApi.getDebts(filterParams).catch(() => []),
        debtApi.getSummary().catch(() => null),
      ]);
      setDebts(debtData);
      setSummary(summaryData);
    } catch {
      // Handle silently
    }
  }, [filter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleCreate = async () => {
    const parsedAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10);
    if (!personName.trim()) {
      setCreateError('Nama orang harus diisi.');
      return;
    }
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setCreateError('Nominal harus lebih dari 0.');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);

    try {
      await debtApi.createDebt({
        type: createType,
        person_name: personName.trim(),
        total_amount: parsedAmount,
        note: note.trim() || undefined,
        due_date: dueDate.trim() || undefined,
      });

      setShowCreateModal(false);
      setPersonName('');
      setAmount('');
      setNote('');
      setDueDate('');
      await loadData();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || 'Gagal membuat hutang/piutang.');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleOpenDetail = async (debt: Debt) => {
    setSelectedDebt(debt);
    setShowDetailModal(true);
    setShowPaymentInput(false);
    setPayAmount('');
    setPayNote('');

    try {
      const paymentList = await debtApi.getPayments(debt.id);
      setPayments(paymentList);
    } catch {
      setPayments([]);
    }
  };

  const handleAddPayment = async () => {
    if (!selectedDebt) return;
    const parsedAmount = parseInt(payAmount.replace(/[^0-9]/g, ''), 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      Alert.alert('Error', 'Nominal pembayaran harus lebih dari 0.');
      return;
    }

    setPayLoading(true);
    try {
      const todayStr = new Date().toISOString().split('T')[0];
      await debtApi.addPayment(selectedDebt.id, {
        amount: parsedAmount,
        note: payNote.trim() || undefined,
        payment_date: todayStr,
      });

      // Refresh detail
      const [updatedDebt, updatedPayments] = await Promise.all([
        debtApi.getDebt(selectedDebt.id),
        debtApi.getPayments(selectedDebt.id),
      ]);
      setSelectedDebt(updatedDebt);
      setPayments(updatedPayments);
      setShowPaymentInput(false);
      setPayAmount('');
      setPayNote('');
      await loadData();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Gagal mencatat pembayaran.');
    } finally {
      setPayLoading(false);
    }
  };

  const handleMarkSettled = async () => {
    if (!selectedDebt) return;
    Alert.alert(
      'Tandai Lunas',
      `Apakah kamu yakin ingin menandai ${selectedDebt.type === 'debt' ? 'hutang' : 'piutang'} kepada ${selectedDebt.person_name} sebagai lunas?`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Lunas',
          onPress: async () => {
            try {
              const updated = await debtApi.updateDebt(selectedDebt.id, { status: 'settled' });
              setSelectedDebt(updated);
              await loadData();
            } catch {
              Alert.alert('Error', 'Gagal memperbarui status.');
            }
          },
        },
      ]
    );
  };

  const handleDelete = async () => {
    if (!selectedDebt) return;
    Alert.alert(
      'Hapus',
      `Hapus ${selectedDebt.type === 'debt' ? 'hutang' : 'piutang'} kepada ${selectedDebt.person_name}?`,
      [
        { text: 'Batal', style: 'cancel' },
        {
          text: 'Hapus',
          style: 'destructive',
          onPress: async () => {
            try {
              await debtApi.deleteDebt(selectedDebt.id);
              setShowDetailModal(false);
              setSelectedDebt(null);
              await loadData();
            } catch {
              Alert.alert('Error', 'Gagal menghapus.');
            }
          },
        },
      ]
    );
  };

  const filterTabs: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'Semua' },
    { key: 'debt', label: 'Hutang' },
    { key: 'receivable', label: 'Piutang' },
    { key: 'settled', label: 'Lunas' },
  ];

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
          />
        }
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={Colors.text} />
          </TouchableOpacity>
          <Text style={styles.pageTitle}>Hutang & Piutang</Text>
          <View style={{ width: 36 }} />
        </View>

        {/* Summary */}
        <DebtSummaryCard summary={summary} />

        {/* Filter Tabs */}
        <View style={styles.filterTabs}>
          {filterTabs.map((tab) => (
            <TouchableOpacity
              key={tab.key}
              style={[styles.filterTab, filter === tab.key && styles.filterTabActive]}
              onPress={() => setFilter(tab.key)}
            >
              <Text
                style={[
                  styles.filterTabText,
                  filter === tab.key && styles.filterTabTextActive,
                ]}
              >
                {tab.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Debt List */}
        {debts.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyIcon}>📋</Text>
            <Text style={styles.emptyText}>Belum ada data hutang/piutang.</Text>
            <Text style={styles.emptySubText}>
              Tekan tombol + di bawah untuk menambahkan.
            </Text>
          </View>
        ) : (
          debts.map((debt) => (
            <DebtCard
              key={debt.id}
              debt={debt}
              onPress={() => handleOpenDetail(debt)}
            />
          ))
        )}

        {/* Spacer for FAB */}
        <View style={{ height: 80 }} />
      </ScrollView>

      {/* Floating Action Button */}
      <TouchableOpacity
        style={styles.fab}
        activeOpacity={0.85}
        onPress={() => {
          setCreateError(null);
          setShowCreateModal(true);
        }}
      >
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>

      {/* ==================== CREATE MODAL ==================== */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCreateModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Tambah Hutang / Piutang</Text>
              <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                <Ionicons name="close" size={24} color={Colors.textSecondary} />
              </TouchableOpacity>
            </View>

            {/* Type selector */}
            <View style={styles.typeSelector}>
              <TouchableOpacity
                style={[
                  styles.typeTab,
                  createType === 'debt' && { backgroundColor: Colors.debt },
                ]}
                onPress={() => setCreateType('debt')}
              >
                <Text
                  style={[
                    styles.typeTabText,
                    createType === 'debt' && styles.typeTabTextActive,
                  ]}
                >
                  Hutang
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.typeTab,
                  createType === 'receivable' && { backgroundColor: Colors.receivable },
                ]}
                onPress={() => setCreateType('receivable')}
              >
                <Text
                  style={[
                    styles.typeTabText,
                    createType === 'receivable' && styles.typeTabTextActive,
                  ]}
                >
                  Piutang
                </Text>
              </TouchableOpacity>
            </View>

            {createError && <Text style={styles.errorText}>{createError}</Text>}

            <Input
              label="Nama Orang"
              placeholder={createType === 'debt' ? 'Siapa yang kamu hutangi?' : 'Siapa yang berhutang?'}
              value={personName}
              onChangeText={setPersonName}
            />

            <Input
              label="Nominal (Rp)"
              placeholder="Contoh: 500000"
              value={amount}
              onChangeText={setAmount}
              keyboardType="numeric"
            />

            <Input
              label="Jatuh Tempo (Opsional)"
              placeholder="Format: YYYY-MM-DD (cth: 2026-12-31)"
              value={dueDate}
              onChangeText={setDueDate}
            />

            <Input
              label="Catatan (Opsional)"
              placeholder="Catatan tambahan..."
              value={note}
              onChangeText={setNote}
            />

            <Button
              title="Simpan"
              loading={createLoading}
              onPress={handleCreate}
              style={styles.submitBtn}
            />
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ==================== DETAIL MODAL ==================== */}
      <Modal
        visible={showDetailModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowDetailModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.modalOverlay}
        >
          <View style={styles.detailModalContent}>
            <ScrollView showsVerticalScrollIndicator={false}>
              {/* Header */}
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Detail</Text>
                <TouchableOpacity onPress={() => setShowDetailModal(false)}>
                  <Ionicons name="close" size={24} color={Colors.textSecondary} />
                </TouchableOpacity>
              </View>

              {selectedDebt && (
                <>
                  {/* Info Card */}
                  <Card style={styles.detailCard}>
                    <View style={styles.detailHeaderRow}>
                      <View
                        style={[
                          styles.detailBadge,
                          {
                            backgroundColor:
                              selectedDebt.type === 'debt'
                                ? Colors.debtBg
                                : Colors.receivableBg,
                          },
                        ]}
                      >
                        <Text
                          style={[
                            styles.detailBadgeText,
                            {
                              color:
                                selectedDebt.type === 'debt'
                                  ? Colors.debt
                                  : Colors.receivable,
                            },
                          ]}
                        >
                          {selectedDebt.type === 'debt' ? 'HUTANG' : 'PIUTANG'}
                        </Text>
                      </View>
                      {selectedDebt.status === 'settled' && (
                        <View style={styles.settledTag}>
                          <Text style={styles.settledTagText}>✓ Lunas</Text>
                        </View>
                      )}
                    </View>

                    <Text style={styles.detailPerson}>{selectedDebt.person_name}</Text>

                    <Text
                      style={[
                        styles.detailAmount,
                        {
                          color:
                            selectedDebt.type === 'debt'
                              ? Colors.debt
                              : Colors.receivable,
                        },
                      ]}
                    >
                      {formatRupiah(selectedDebt.total_amount)}
                    </Text>

                    {/* Progress */}
                    <View style={styles.detailProgressSection}>
                      <View style={styles.detailProgressRow}>
                        <Text style={styles.detailProgressLabel}>Progress</Text>
                        <Text style={styles.detailProgressPct}>
                          {selectedDebt.total_amount > 0
                            ? Math.round(
                                (selectedDebt.paid_amount / selectedDebt.total_amount) *
                                  100
                              )
                            : 0}
                          %
                        </Text>
                      </View>
                      <View style={styles.detailProgressBg}>
                        <View
                          style={[
                            styles.detailProgressFill,
                            {
                              width: `${Math.min(
                                selectedDebt.total_amount > 0
                                  ? (selectedDebt.paid_amount /
                                      selectedDebt.total_amount) *
                                      100
                                  : 0,
                                100
                              )}%`,
                              backgroundColor:
                                selectedDebt.status === 'settled'
                                  ? Colors.success
                                  : selectedDebt.type === 'debt'
                                  ? Colors.debt
                                  : Colors.receivable,
                            },
                          ]}
                        />
                      </View>
                      <View style={styles.detailAmountSplitRow}>
                        <Text style={styles.detailAmountSplit}>
                          Dibayar: {formatRupiah(selectedDebt.paid_amount)}
                        </Text>
                        <Text style={styles.detailAmountSplit}>
                          Sisa:{' '}
                          {formatRupiah(
                            selectedDebt.total_amount - selectedDebt.paid_amount
                          )}
                        </Text>
                      </View>
                    </View>

                    {selectedDebt.due_date && (
                      <View style={styles.detailInfoRow}>
                        <Ionicons
                          name="calendar-outline"
                          size={14}
                          color={Colors.textMuted}
                        />
                        <Text style={styles.detailInfoText}>
                          Jatuh tempo: {formatDateIndo(selectedDebt.due_date)}
                        </Text>
                      </View>
                    )}

                    {selectedDebt.note && (
                      <View style={styles.detailInfoRow}>
                        <Ionicons
                          name="document-text-outline"
                          size={14}
                          color={Colors.textMuted}
                        />
                        <Text style={styles.detailInfoText}>{selectedDebt.note}</Text>
                      </View>
                    )}
                  </Card>

                  {/* Action Buttons */}
                  {selectedDebt.status === 'active' && (
                    <View style={styles.actionRow}>
                      <Button
                        title={
                          selectedDebt.type === 'debt'
                            ? '💰 Bayar Cicilan'
                            : '💰 Terima Pembayaran'
                        }
                        onPress={() => setShowPaymentInput(!showPaymentInput)}
                        style={{ flex: 1, marginRight: 8 }}
                      />
                      <Button
                        title="✓ Lunas"
                        variant="secondary"
                        onPress={handleMarkSettled}
                        style={{ flex: 0.6 }}
                      />
                    </View>
                  )}

                  {/* Payment Input */}
                  {showPaymentInput && selectedDebt.status === 'active' && (
                    <Card style={styles.paymentInputCard}>
                      <Text style={styles.paymentInputTitle}>Catat Pembayaran</Text>
                      <Input
                        label="Nominal Bayar (Rp)"
                        placeholder="Contoh: 100000"
                        value={payAmount}
                        onChangeText={setPayAmount}
                        keyboardType="numeric"
                      />
                      <Input
                        label="Catatan (Opsional)"
                        placeholder="Keterangan pembayaran..."
                        value={payNote}
                        onChangeText={setPayNote}
                      />
                      <Button
                        title="Simpan Pembayaran"
                        loading={payLoading}
                        onPress={handleAddPayment}
                      />
                    </Card>
                  )}

                  {/* Payment History */}
                  <Text style={styles.sectionTitle}>
                    Riwayat Pembayaran ({payments.length})
                  </Text>

                  {payments.length === 0 ? (
                    <View style={styles.emptyPayments}>
                      <Text style={styles.emptyPaymentsText}>
                        Belum ada pembayaran tercatat.
                      </Text>
                    </View>
                  ) : (
                    payments.map((p) => (
                      <View key={p.id} style={styles.paymentItem}>
                        <View style={styles.paymentDot} />
                        <View style={styles.paymentContent}>
                          <View style={styles.paymentTopRow}>
                            <Text style={styles.paymentAmount}>
                              {formatRupiah(p.amount)}
                            </Text>
                            <Text style={styles.paymentDate}>
                              {formatDateIndo(p.payment_date)}
                            </Text>
                          </View>
                          {p.note && (
                            <Text style={styles.paymentNote}>{p.note}</Text>
                          )}
                        </View>
                      </View>
                    ))
                  )}

                  {/* Delete Button */}
                  <Button
                    title="Hapus Hutang/Piutang"
                    variant="danger"
                    onPress={handleDelete}
                    style={styles.deleteBtn}
                  />
                </>
              )}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
    marginTop: 8,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  pageTitle: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
  },
  filterTabs: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    padding: 4,
    borderRadius: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  filterTab: {
    flex: 1,
    paddingVertical: 9,
    alignItems: 'center',
    borderRadius: 10,
  },
  filterTabActive: {
    backgroundColor: Colors.primary,
  },
  filterTabText: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  filterTabTextActive: {
    color: '#fff',
    fontWeight: '700',
  },
  emptyCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 14,
    padding: 32,
    alignItems: 'center',
    marginTop: 8,
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 12,
  },
  emptyText: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  emptySubText: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },

  // Create Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: Colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  typeSelector: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    padding: 4,
    borderRadius: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
  },
  typeTab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 10,
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
  errorText: {
    color: Colors.danger,
    fontSize: 13,
    marginBottom: 16,
    textAlign: 'center',
  },
  submitBtn: {
    marginTop: 8,
  },

  // Detail Modal
  detailModalContent: {
    backgroundColor: Colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
    maxHeight: '92%',
  },
  detailCard: {
    padding: 18,
    marginBottom: 16,
  },
  detailHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  detailBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  detailBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  settledTag: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  settledTagText: {
    color: Colors.success,
    fontSize: 11,
    fontWeight: '700',
  },
  detailPerson: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    marginBottom: 6,
  },
  detailAmount: {
    fontSize: 28,
    fontWeight: '800',
    letterSpacing: -0.5,
    marginBottom: 16,
  },
  detailProgressSection: {
    marginBottom: 14,
  },
  detailProgressRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  detailProgressLabel: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '500',
  },
  detailProgressPct: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  detailProgressBg: {
    height: 8,
    backgroundColor: Colors.surfaceLight,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 6,
  },
  detailProgressFill: {
    height: '100%',
    borderRadius: 4,
  },
  detailAmountSplitRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  detailAmountSplit: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  detailInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  detailInfoText: {
    color: Colors.textSecondary,
    fontSize: 13,
  },
  actionRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  paymentInputCard: {
    padding: 16,
    marginBottom: 16,
  },
  paymentInputTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 12,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyPayments: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyPaymentsText: {
    color: Colors.textSecondary,
    fontSize: 13,
  },
  paymentItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
    paddingLeft: 4,
  },
  paymentDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary,
    marginTop: 6,
    marginRight: 12,
  },
  paymentContent: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    borderRadius: 10,
    padding: 12,
  },
  paymentTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  paymentAmount: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  paymentDate: {
    color: Colors.textMuted,
    fontSize: 11,
  },
  paymentNote: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: 4,
  },
  deleteBtn: {
    marginTop: 16,
    marginBottom: 20,
  },
});

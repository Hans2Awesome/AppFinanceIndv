import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space, Type } from '../utils/theme';
import { TransactionHistoryEntry, TransactionType } from '../types';
import { transactionApi } from '../services/transactions';
import { authApi, describeApiError } from '../services/auth';
import { formatDateIndo } from '../utils/formatRupiah';
import {
  describeHistoryChanges,
  formatAuditTimestamp,
  historyActionLabel,
  historyReasonLabel,
  historySourceLabel,
  mergeHistoryPages,
  snapshotPrimaryTitle,
  transactionTypeLabel,
} from '../utils/transactions';
import { Screen } from '../components/ui/Screen';
import { Amount } from '../components/ui/Amount';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { SkeletonRows } from '../components/ui/Skeleton';
import { FadeIn } from '../components/ui/FadeIn';

const PAGE_LIMIT = 50;

const TYPE_TONE: Record<TransactionType, 'income' | 'expense' | 'investment'> = {
  income: 'income',
  expense: 'expense',
  investment: 'investment',
};

export default function TransactionHistoryScreen() {
  const params = useLocalSearchParams<{ transaction_id?: string | string[] }>();
  const rawTxId = Array.isArray(params.transaction_id)
    ? params.transaction_id[0]
    : params.transaction_id;
  const parsedTxId = Number.parseInt(String(rawTxId ?? ''), 10);
  const filterTransactionId =
    Number.isSafeInteger(parsedTxId) && parsedTxId > 0 ? parsedTxId : undefined;

  const [entries, setEntries] = useState<TransactionHistoryEntry[] | null>(null);
  const [userTimezone, setUserTimezone] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const requestSeqRef = useRef(0);
  const loadingMoreRef = useRef(false);
  const loadingInitialRef = useRef(false);
  const nextOffsetRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadInitial = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    loadingInitialRef.current = true;
    loadingMoreRef.current = false;
    setLoadingMore(false);
    setLoadMoreError(null);

    const [historyResult, profileResult] = await Promise.allSettled([
      transactionApi.getTransactionHistory({
        transaction_id: filterTransactionId,
        limit: PAGE_LIMIT,
        offset: 0,
      }),
      authApi.getProfile(),
    ]);

    if (!mountedRef.current || seq !== requestSeqRef.current) {
      return;
    }
    loadingInitialRef.current = false;

    if (profileResult.status === 'fulfilled' && profileResult.value?.timezone) {
      setUserTimezone(profileResult.value.timezone);
    }

    if (historyResult.status === 'fulfilled') {
      const page = historyResult.value;
      const deduped = mergeHistoryPages([], page);
      setEntries(deduped);
      nextOffsetRef.current = page.length;
      setHasMore(page.length >= PAGE_LIMIT);
      setError(null);
    } else {
      setError(
        describeApiError(
          historyResult.reason,
          'Gagal memuat riwayat perubahan transaksi.'
        )
      );
    }
  }, [filterTransactionId]);

  useFocusEffect(
    useCallback(() => {
      loadInitial();
    }, [loadInitial])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await loadInitial();
    if (mountedRef.current) {
      setRefreshing(false);
    }
  };

  const handleLoadMore = async () => {
    if (loadingInitialRef.current || loadingMoreRef.current || !hasMore || entries === null) {
      return;
    }

    loadingMoreRef.current = true;
    setLoadingMore(true);
    setLoadMoreError(null);
    const seq = requestSeqRef.current;
    const requestedOffset = nextOffsetRef.current;

    try {
      const nextPage = await transactionApi.getTransactionHistory({
        transaction_id: filterTransactionId,
        limit: PAGE_LIMIT,
        offset: requestedOffset,
      });

      if (!mountedRef.current || seq !== requestSeqRef.current) {
        return;
      }

      setEntries((prev) => mergeHistoryPages(prev ?? [], nextPage));
      nextOffsetRef.current = requestedOffset + nextPage.length;
      setHasMore(nextPage.length >= PAGE_LIMIT);
    } catch (err) {
      if (!mountedRef.current || seq !== requestSeqRef.current) {
        return;
      }
      setLoadMoreError(describeApiError(err, 'Gagal memuat halaman berikutnya.'));
    } finally {
      if (mountedRef.current && seq === requestSeqRef.current) {
        loadingMoreRef.current = false;
        setLoadingMore(false);
      }
    }
  };

  const deletedTransactionIds = new Set<number>();
  if (entries) {
    for (const item of entries) {
      if (item.action === 'delete') {
        deletedTransactionIds.add(item.transaction_id);
      }
    }
  }

  return (
    <Screen bottomInset refreshing={refreshing} onRefresh={onRefresh}>
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
        <View style={styles.headerTitles}>
          <Text style={styles.title} numberOfLines={1}>
            Riwayat perubahan
          </Text>
          {filterTransactionId ? (
            <Text style={styles.subtitle}>Transaksi #{filterTransactionId}</Text>
          ) : null}
        </View>
        {filterTransactionId ? (
          <Pressable
            onPress={() => router.replace('/transaction-history')}
            hitSlop={8}
            style={styles.allAction}
            accessibilityRole="button"
            accessibilityLabel="Lihat semua riwayat perubahan"
          >
            <Text style={styles.allActionText}>Semua</Text>
          </Pressable>
        ) : null}
      </View>

      <FadeIn>
        <Text style={styles.intro}>
          Catatan perubahan dan penghapusan transaksi tersimpan secara berurutan. Catatan yang
          sudah dihapus tetap tampil di sini sebagai jejak buku kas.
        </Text>
      </FadeIn>

      {error ? <ErrorState message={error} onRetry={loadInitial} /> : null}

      {entries === null && !error ? (
        <View style={styles.loadingBlock}>
          <SkeletonRows count={5} />
        </View>
      ) : entries && entries.length === 0 ? (
        <EmptyState
          icon="time-outline"
          title="Belum ada riwayat perubahan"
          message={
            filterTransactionId
              ? 'Transaksi ini belum pernah diubah atau dihapus.'
              : 'Perubahan atau penghapusan transaksi akan tercatat otomatis di halaman ini.'
          }
        />
      ) : entries ? (
        <View style={styles.list}>
          {entries.map((entry) => {
            const isDeletedNow =
              entry.action === 'delete' || deletedTransactionIds.has(entry.transaction_id);
            const canOpenDetail = !filterTransactionId && !isDeletedNow;

            return (
              <HistoryRow
                key={entry.id}
                entry={entry}
                userTimezone={userTimezone}
                onOpenTransaction={
                  canOpenDetail
                    ? () => router.push(`/transaction/${entry.transaction_id}`)
                    : undefined
                }
              />
            );
          })}

          {loadMoreError ? (
            <View style={styles.loadMoreErrorWrap}>
              <ErrorState message={loadMoreError} onRetry={handleLoadMore} />
            </View>
          ) : null}

          {hasMore ? (
            <View style={styles.moreWrap}>
              <Button
                title="Muat lagi"
                variant="secondary"
                loading={loadingMore}
                disabled={loadingMore}
                onPress={handleLoadMore}
              />
            </View>
          ) : null}
        </View>
      ) : null}
    </Screen>
  );
}

function HistoryRow({
  entry,
  userTimezone,
  onOpenTransaction,
}: {
  entry: TransactionHistoryEntry;
  userTimezone: string | null;
  onOpenTransaction?: () => void;
}) {
  const snapshot = entry.after ?? entry.before;
  const isDelete = entry.action === 'delete';
  const changes = describeHistoryChanges(entry);
  const title = snapshotPrimaryTitle(snapshot);
  const tone = TYPE_TONE[snapshot.type] ?? 'expense';
  const sign = snapshot.type === 'income' ? 1 : snapshot.type === 'expense' ? -1 : 1;

  return (
    <View style={styles.row}>
      <View style={styles.rowTop}>
        <View style={styles.badgeGroup}>
          <View
            style={[
              styles.actionBadge,
              { backgroundColor: isDelete ? Colors.dangerTint : Colors.inkTint },
            ]}
          >
            <Text
              style={[
                styles.actionBadgeText,
                { color: isDelete ? Colors.danger : Colors.ink },
              ]}
            >
              {historyActionLabel(entry.action).toUpperCase()}
            </Text>
          </View>
          <Text style={styles.sourceMeta}>
            {historySourceLabel(entry.source)} · {historyReasonLabel(entry.reason)}
          </Text>
        </View>
        <Text style={styles.timestamp}>
          {formatAuditTimestamp(entry.created_at, userTimezone)}
        </Text>
      </View>

      <View style={styles.summaryRow}>
        <View style={styles.summaryMain}>
          <Text style={styles.rowTitle} numberOfLines={1}>
            {title}
          </Text>
          <Text style={styles.rowSub}>
            {transactionTypeLabel(snapshot.type)} · {formatDateIndo(snapshot.transaction_date)}
          </Text>
        </View>
        <Amount value={sign * snapshot.amount} tone={tone} signed />
      </View>

      {isDelete ? (
        <View style={styles.snapshotBox}>
          <Text style={styles.snapshotHeading}>Data terakhir sebelum dihapus</Text>
          <SnapshotDetailLine
            label="Kategori"
            value={entry.before.category_name?.trim() || 'Tanpa kategori'}
          />
          <SnapshotDetailLine
            label="Tanggal"
            value={formatDateIndo(entry.before.transaction_date)}
          />
          {entry.before.asset_name ? (
            <SnapshotDetailLine label="Aset" value={entry.before.asset_name} />
          ) : null}
          {entry.before.note ? (
            <SnapshotDetailLine label="Catatan" value={entry.before.note} />
          ) : null}
        </View>
      ) : changes.length > 0 ? (
        <View style={styles.diffBox}>
          {changes.map((change) => (
            <View key={change.field} style={styles.diffLine}>
              <Text style={styles.diffLabel}>{change.label}</Text>
              <Text style={styles.diffValues}>
                <Text style={styles.diffBefore}>{change.before}</Text>
                <Text style={styles.diffArrow}> ke </Text>
                <Text style={styles.diffAfter}>{change.after}</Text>
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {onOpenTransaction ? (
        <Pressable
          onPress={onOpenTransaction}
          hitSlop={6}
          style={({ pressed }) => [styles.openLink, pressed ? styles.pressed : null]}
          accessibilityRole="button"
          accessibilityLabel={`Buka detail transaksi ${title}`}
        >
          <Text style={styles.openLinkText}>Buka transaksi</Text>
          <Ionicons name="chevron-forward" size={14} color={Colors.inkSoft} />
        </Pressable>
      ) : null}
    </View>
  );
}

function SnapshotDetailLine({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.snapshotLine}>
      <Text style={styles.snapshotLabel}>{label}</Text>
      <Text style={styles.snapshotValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginBottom: Space.sm,
  },
  back: {
    width: 44,
    height: 44,
    alignItems: 'flex-start',
    justifyContent: 'center',
    marginLeft: -Space.sm,
  },
  headerTitles: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    ...Type.h2,
  },
  subtitle: {
    ...Type.caption,
    marginTop: 2,
  },
  allAction: {
    minHeight: 44,
    paddingHorizontal: Space.sm,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  allActionText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.inkSoft,
  },
  intro: {
    ...Type.caption,
    marginBottom: Space.lg,
  },
  loadingBlock: {
    paddingTop: Space.lg,
  },
  list: {
    gap: 0,
  },
  row: {
    paddingVertical: Space.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
    gap: Space.sm,
  },
  rowTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: Space.sm,
    flexWrap: 'wrap',
  },
  badgeGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    flexShrink: 1,
    flexWrap: 'wrap',
  },
  actionBadge: {
    paddingHorizontal: Space.sm,
    paddingVertical: 2,
    borderRadius: Radius.control,
  },
  actionBadgeText: {
    fontFamily: Fonts.semibold,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 0.06,
  },
  sourceMeta: {
    ...Type.caption,
    color: Colors.inkSoft,
  },
  timestamp: {
    ...Type.micro,
    letterSpacing: 0,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
  },
  summaryMain: {
    flex: 1,
    minWidth: 0,
  },
  rowTitle: {
    ...Type.bodyStrong,
  },
  rowSub: {
    ...Type.caption,
    marginTop: 2,
  },
  diffBox: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.control,
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
    gap: Space.xs,
  },
  diffLine: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: Space.md,
  },
  diffLabel: {
    ...Type.caption,
    color: Colors.inkSoft,
    minWidth: 68,
  },
  diffValues: {
    ...Type.caption,
    color: Colors.ink,
    flex: 1,
    textAlign: 'right',
  },
  diffBefore: {
    color: Colors.inkMuted,
  },
  diffArrow: {
    color: Colors.inkMuted,
  },
  diffAfter: {
    fontFamily: Fonts.medium,
    color: Colors.ink,
  },
  snapshotBox: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.line,
    borderRadius: Radius.control,
    paddingHorizontal: Space.md,
    paddingVertical: Space.sm,
    gap: Space.xs,
  },
  snapshotHeading: {
    ...Type.micro,
    letterSpacing: 0.04,
    marginBottom: 2,
  },
  snapshotLine: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: Space.md,
  },
  snapshotLabel: {
    ...Type.caption,
    color: Colors.inkSoft,
  },
  snapshotValue: {
    ...Type.caption,
    color: Colors.ink,
    flex: 1,
    textAlign: 'right',
  },
  openLink: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    minHeight: 36,
    paddingVertical: Space.xs,
  },
  openLinkText: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
  },
  pressed: {
    opacity: 0.7,
  },
  loadMoreErrorWrap: {
    marginTop: Space.md,
  },
  moreWrap: {
    paddingTop: Space.lg,
    paddingBottom: Space.md,
  },
});

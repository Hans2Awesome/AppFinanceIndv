import React from 'react';
import { Colors } from '../../utils/theme';
import { Segmented, SegmentedItem } from '../ui/Segmented';

export type DebtFilter = 'all' | 'debt' | 'receivable' | 'settled';

const FILTER_ITEMS: ReadonlyArray<SegmentedItem<DebtFilter>> = [
  { key: 'all', label: 'Semua' },
  { key: 'debt', label: 'Hutang', dotColor: Colors.debt },
  { key: 'receivable', label: 'Piutang', dotColor: Colors.receivable },
  { key: 'settled', label: 'Lunas' },
];

interface DebtFilterTabsProps {
  value: DebtFilter;
  onChange: (value: DebtFilter) => void;
}

export function DebtFilterTabs({ value, onChange }: DebtFilterTabsProps) {
  return (
    <Segmented items={FILTER_ITEMS} value={value} onChange={onChange} label="Filter hutang dan piutang" />
  );
}
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Colors, Fonts, Space } from '../../utils/theme';

export interface SegmentedItem<K extends string> {
  key: K;
  label: string;
  /** Optional semantic dot, e.g. hutang / piutang. */
  dotColor?: string;
}

interface SegmentedProps<K extends string> {
  items: ReadonlyArray<SegmentedItem<K>>;
  value: K;
  onChange: (key: K) => void;
  /** Accessible name for the group. */
  label: string;
}

/**
 * Underlined ledger tabs. Not pills: the active tab is marked by an ink rule
 * under the label, which keeps the paper quiet.
 */
export function Segmented<K extends string>({ items, value, onChange, label }: SegmentedProps<K>) {
  return (
    <View style={styles.container} accessibilityRole="tablist" accessibilityLabel={label}>
      {items.map((item) => {
        const active = item.key === value;
        return (
          <Pressable
            key={item.key}
            onPress={() => onChange(item.key)}
            style={styles.tab}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={item.label}
          >
            <View style={styles.labelRow}>
              {item.dotColor ? (
                <View style={[styles.dot, { backgroundColor: item.dotColor }]} />
              ) : null}
              <Text style={[styles.text, active && styles.textActive]}>{item.label}</Text>
            </View>
            <View style={[styles.rule, active && styles.ruleActive]} />
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: Colors.line,
    marginBottom: Space.lg,
  },
  tab: {
    flex: 1,
    minHeight: 44,
    justifyContent: 'flex-end',
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingBottom: Space.sm,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  text: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.inkMuted,
  },
  textActive: {
    fontFamily: Fonts.semibold,
    color: Colors.ink,
  },
  rule: {
    height: 2,
    backgroundColor: 'transparent',
  },
  ruleActive: {
    backgroundColor: Colors.ink,
  },
});
import React from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import { Colors } from '../../utils/theme';

interface ProgressProps {
  /** 0-100. Clamped. */
  value: number;
  color?: string;
  height?: number;
  style?: ViewStyle;
}

/** Hairline-height progress rule, sized for dense ledger rows. */
export function Progress({ value, color = Colors.ink, height = 4, style }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));

  return (
    <View
      style={[styles.track, { height }, style]}
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped) }}
    >
      <View style={[styles.fill, { width: `${clamped}%`, backgroundColor: color, height }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 999,
    overflow: 'hidden',
  },
  fill: {
    borderRadius: 999,
  },
});
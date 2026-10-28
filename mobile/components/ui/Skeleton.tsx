import React, { useEffect, useRef } from 'react';
import { Animated, View, ViewStyle } from 'react-native';
import { useReducedMotion } from '../../utils/motion';
import { Colors, Radius, Space } from '../../utils/theme';

interface SkeletonProps {
  width?: number | `${number}%`;
  height?: number;
  radius?: number;
  style?: ViewStyle;
}

/** Quiet placeholder block with a soft pulse. Static under reduce-motion. */
export function Skeleton({ width = '100%', height = 12, radius = Radius.control, style }: SkeletonProps) {
  const reduced = useReducedMotion();
  const pulse = useRef(new Animated.Value(0.55)).current;

  useEffect(() => {
    if (reduced) {
      pulse.setValue(0.8);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.55, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reduced]);

  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        { width, height, borderRadius: radius, backgroundColor: Colors.surfaceAlt, opacity: pulse },
        style,
      ]}
    />
  );
}

/** Three rule-separated skeleton rows, shaped like a ledger list. */
export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <View style={{ gap: Space.lg }}>
      {Array.from({ length: count }).map((_, index) => (
        <View key={index} style={{ gap: Space.sm }}>
          <Skeleton width="42%" height={13} />
          <Skeleton width="24%" height={11} />
        </View>
      ))}
    </View>
  );
}
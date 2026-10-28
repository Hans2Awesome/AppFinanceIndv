import React from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';
import { Colors, Radius, Shadow, Space } from '../../utils/theme';

type Variant = 'surface' | 'inset' | 'plain';

interface CardProps extends ViewProps {
  variant?: Variant;
  /** Padding override; defaults to Space.lg. */
  padded?: boolean;
  children: React.ReactNode;
}

/** A raised paper block. Used sparingly: sheets, hero blocks, forms. */
export function Card({ variant = 'surface', padded = true, style, children, ...props }: CardProps) {
  return (
    <View
      style={[
        styles.base,
        padded && styles.padded,
        variant === 'surface' && styles.surface,
        variant === 'inset' && styles.inset,
        variant === 'plain' && styles.plain,
        style,
      ]}
      {...props}
    >
      {children}
    </View>
  );
}

/** 1px ledger rule. */
export function Rule({ style }: { style?: ViewProps['style'] }) {
  return <View style={[styles.rule, style]} />;
}

const styles = StyleSheet.create({
  base: {
    borderRadius: Radius.block,
  },
  padded: {
    padding: Space.lg,
  },
  surface: {
    backgroundColor: Colors.surface,
    ...Shadow.raised,
  },
  inset: {
    backgroundColor: Colors.surfaceAlt,
  },
  plain: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: Colors.line,
  },
  rule: {
    height: StyleSheet.hairlineWidth * 2,
    backgroundColor: Colors.line,
  },
});
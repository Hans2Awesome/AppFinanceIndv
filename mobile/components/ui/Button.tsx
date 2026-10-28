import React, { useRef } from 'react';
import {
  ActivityIndicator,
  Animated,
  Pressable,
  StyleSheet,
  Text,
  ViewStyle,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space } from '../../utils/theme';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'md' | 'lg';

interface ButtonProps {
  title: string;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  fullWidth?: boolean;
  style?: ViewStyle | ViewStyle[];
  accessibilityHint?: string;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon,
  fullWidth = true,
  style,
  accessibilityHint,
}: ButtonProps) {
  const scale = useRef(new Animated.Value(1)).current;
  const inactive = disabled || loading;

  const press = (to: number) =>
    Animated.spring(scale, {
      toValue: to,
      useNativeDriver: true,
      speed: 40,
      bounciness: 0,
    }).start();

  const palette = {
    primary: { bg: Colors.ink, fg: Colors.onInk, border: Colors.ink },
    secondary: { bg: Colors.surface, fg: Colors.ink, border: Colors.line },
    ghost: { bg: 'transparent', fg: Colors.ink, border: 'transparent' },
    danger: { bg: Colors.dangerTint, fg: Colors.danger, border: 'rgba(163, 43, 43, 0.28)' },
  }[variant];

  return (
    <Animated.View style={[{ transform: [{ scale }] }, fullWidth && styles.fullWidth, style]}>
      <Pressable
        onPress={onPress}
        onPressIn={() => press(0.98)}
        onPressOut={() => press(1)}
        disabled={inactive}
        accessibilityRole="button"
        accessibilityLabel={title}
        accessibilityHint={accessibilityHint}
        accessibilityState={{ disabled: inactive, busy: loading }}
        style={[
          styles.base,
          size === 'lg' && styles.lg,
          { backgroundColor: palette.bg, borderColor: palette.border },
          inactive && styles.inactive,
        ]}
      >
        {loading ? (
          <ActivityIndicator size="small" color={palette.fg} />
        ) : (
          <>
            {icon && <Ionicons name={icon} size={18} color={palette.fg} style={styles.icon} />}
            <Text style={[styles.label, size === 'lg' && styles.labelLg, { color: palette.fg }]}>
              {title}
            </Text>
          </>
        )}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  fullWidth: {
    alignSelf: 'stretch',
  },
  base: {
    minHeight: Space.xxxl,
    borderRadius: Radius.control,
    borderWidth: 1,
    paddingHorizontal: Space.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
  },
  lg: {
    minHeight: 52,
  },
  inactive: {
    opacity: 0.45,
  },
  icon: {
    marginTop: -1,
  },
  label: {
    fontFamily: Fonts.semibold,
    fontSize: 15,
    lineHeight: 20,
  },
  labelLg: {
    fontSize: 16,
  },
});
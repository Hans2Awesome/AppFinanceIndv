import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { Colors, Fonts, Space } from '../../utils/theme';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string | null;
  hint?: string;
  /** Fixed prefix inside the field, e.g. "Rp". */
  leading?: string;
  /** Text style override for the field itself (e.g. large amounts). */
  fieldStyle?: TextInputProps['style'];
}

/**
 * Ledger-style field: no box, a single rule that turns ink on focus.
 */
export function Input({
  label,
  error,
  hint,
  leading,
  fieldStyle,
  style,
  onFocus,
  onBlur,
  ...props
}: InputProps) {
  const [focused, setFocused] = useState(false);

  const ruleColor = error ? Colors.danger : focused ? Colors.ink : Colors.lineStrong;

  return (
    <View style={styles.wrap}>
      {label ? (
        <Text style={styles.label} allowFontScaling>
          {label}
        </Text>
      ) : null}

      <View style={[styles.field, { borderBottomColor: ruleColor }]}>
        {leading ? <Text style={styles.leading}>{leading}</Text> : null}
        <TextInput
          placeholderTextColor={Colors.inkMuted}
          selectionColor={Colors.ink}
          style={[styles.input, fieldStyle, style]}
          onFocus={(event) => {
            setFocused(true);
            onFocus?.(event);
          }}
          onBlur={(event) => {
            setFocused(false);
            onBlur?.(event);
          }}
          accessibilityLabel={props.accessibilityLabel ?? label}
          allowFontScaling
          {...props}
        />
      </View>

      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : hint ? (
        <Text style={styles.hint}>{hint}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: Space.lg,
  },
  label: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
    marginBottom: Space.xs,
  },
  field: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 46,
    borderBottomWidth: 1,
    gap: Space.sm,
  },
  leading: {
    fontFamily: Fonts.medium,
    fontSize: 15,
    color: Colors.inkMuted,
  },
  input: {
    flex: 1,
    minHeight: 46,
    paddingVertical: Space.sm,
    fontFamily: Fonts.regular,
    fontSize: 15,
    color: Colors.ink,
  },
  error: {
    marginTop: Space.xs,
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.danger,
  },
  hint: {
    marginTop: Space.xs,
    fontFamily: Fonts.regular,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkMuted,
  },
});
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Radius, Space } from '../../utils/theme';
import { Button } from './Button';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

/** Inline error panel: cause on one line, retry as the next action. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <View style={styles.container} accessibilityLiveRegion="polite">
      <Ionicons name="alert-circle-outline" size={18} color={Colors.danger} />
      <Text style={styles.message}>{message}</Text>
      {onRetry ? (
        <Button
          title="Coba lagi"
          variant="secondary"
          onPress={onRetry}
          fullWidth={false}
          style={styles.action}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Colors.dangerTint,
    borderWidth: 1,
    borderColor: 'rgba(163, 43, 43, 0.22)',
    borderRadius: Radius.block,
    paddingVertical: Space.md,
    paddingHorizontal: Space.md,
    marginBottom: Space.lg,
  },
  message: {
    flex: 1,
    fontFamily: Fonts.regular,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.danger,
  },
  action: {
    paddingHorizontal: Space.md,
    minHeight: 36,
  },
});
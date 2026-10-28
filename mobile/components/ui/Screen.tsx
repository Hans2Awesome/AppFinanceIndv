import React from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Space } from '../../utils/theme';

interface ScreenProps {
  children: React.ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  /** Sticky block rendered after the scroll area (FAB, CTA bar). */
  footer?: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
  /** Include the bottom safe-area inset (stack screens). Tabs handle it. */
  bottomInset?: boolean;
}

/** Paper background + safe area + optional pull-to-refresh. */
export function Screen({
  children,
  scroll = true,
  refreshing = false,
  onRefresh,
  footer,
  contentStyle,
  bottomInset = false,
}: ScreenProps) {
  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.content, contentStyle]}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.ink}
            colors={[Colors.ink]}
            progressBackgroundColor={Colors.surface}
          />
        ) : undefined
      }
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.content, styles.flex, contentStyle]}>{children}</View>
  );

  return (
    <SafeAreaView style={styles.safe} edges={bottomInset ? ['top', 'left', 'right', 'bottom'] : ['top', 'left', 'right']}>
      {body}
      {footer}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.paper,
  },
  content: {
    paddingHorizontal: Space.gutter,
    paddingTop: Space.md,
    paddingBottom: Space.xxl,
  },
  flex: {
    flex: 1,
  },
});
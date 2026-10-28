import React, { useEffect, useRef } from 'react';
import {
  Animated,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Fonts, Motion, Radius, Shadow, Space } from '../../utils/theme';
import { useReducedMotion } from '../../utils/motion';

interface SheetProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  /** Sticky action area under the scroll body. */
  footer?: React.ReactNode;
  /** Accessibility label for the close control. */
  closeLabel?: string;
}

/** Bottom sheet on paper: drag handle, ink title, optional sticky footer. */
export function Sheet({ visible, onClose, title, children, footer, closeLabel = 'Tutup' }: SheetProps) {
  const reduced = useReducedMotion();
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) {
      enter.setValue(0);
      return;
    }
    if (reduced) {
      enter.setValue(1);
      return;
    }
    Animated.timing(enter, {
      toValue: 1,
      duration: Motion.base,
      useNativeDriver: true,
    }).start();
  }, [enter, reduced, visible]);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={styles.root}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Tutup panel"
        />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          pointerEvents="box-none"
          style={styles.dock}
        >
          <Animated.View
            style={[
              styles.panel,
              {
                transform: [
                  {
                    translateY: enter.interpolate({ inputRange: [0, 1], outputRange: [24, 0] }),
                  },
                ],
                opacity: enter,
              },
            ]}
          >
            <View style={styles.handle} />
            <View style={styles.header}>
              <Text style={styles.title} accessibilityRole="header">
                {title}
              </Text>
              <Pressable
                onPress={onClose}
                hitSlop={12}
                style={styles.close}
                accessibilityRole="button"
                accessibilityLabel={closeLabel}
              >
                <Ionicons name="close" size={20} color={Colors.inkSoft} />
              </Pressable>
            </View>
            <View style={styles.body}>{children}</View>
            {footer ? <View style={styles.footer}>{footer}</View> : null}
          </Animated.View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: Colors.scrim,
    justifyContent: 'flex-end',
  },
  dock: {
    justifyContent: 'flex-end',
  },
  panel: {
    backgroundColor: Colors.paper,
    borderTopLeftRadius: Radius.sheet,
    borderTopRightRadius: Radius.sheet,
    paddingHorizontal: Space.gutter,
    paddingBottom: Space.lg,
    maxHeight: '92%',
    ...Shadow.sheet,
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.lineStrong,
    marginTop: Space.sm,
    marginBottom: Space.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 44,
  },
  title: {
    fontFamily: Fonts.serif,
    fontSize: 24,
    lineHeight: 29,
    color: Colors.ink,
    flex: 1,
  },
  close: {
    width: 44,
    height: 44,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  body: {
    flexShrink: 1,
    paddingBottom: Space.sm,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: Colors.line,
    paddingTop: Space.md,
    gap: Space.sm,
  },
});
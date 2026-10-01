import React from 'react';
import { View, StyleSheet, ViewProps } from 'react-native';
import { Colors } from '../../utils/colors';

interface CardProps extends ViewProps {
  variant?: 'surface' | 'surfaceLight';
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  variant = 'surface',
  style,
  children,
  ...props
}) => {
  return (
    <View
      style={[
        styles.card,
        variant === 'surfaceLight' ? styles.surfaceLight : styles.surface,
        style,
      ]}
      {...props}
    >
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.surfaceBorder,
    shadowColor: Colors.cardShadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  surface: {
    backgroundColor: Colors.surface,
  },
  surfaceLight: {
    backgroundColor: Colors.surfaceLight,
  },
});

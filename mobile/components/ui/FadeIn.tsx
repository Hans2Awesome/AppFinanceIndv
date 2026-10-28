import React, { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { useReducedMotion } from '../../utils/motion';
import { Motion } from '../../utils/theme';

interface FadeInProps {
  children: React.ReactNode;
  /** Stagger in ms. */
  delay?: number;
  /** Travel distance in px. */
  distance?: number;
  style?: object;
}

/** One-shot fade-up used on mount. Skipped when reduce-motion is on. */
export function FadeIn({ children, delay = 0, distance = 8, style }: FadeInProps) {
  const reduced = useReducedMotion();
  const progress = useRef(new Animated.Value(reduced ? 1 : 0)).current;

  useEffect(() => {
    if (reduced) {
      progress.setValue(1);
      return;
    }
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: Motion.base,
      delay,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [delay, progress, reduced]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [
            {
              translateY: progress.interpolate({
                inputRange: [0, 1],
                outputRange: [distance, 0],
              }),
            },
          ],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}
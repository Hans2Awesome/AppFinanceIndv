import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { ActivityIndicator, AppState, BackHandler, Platform, StyleSheet, Text, View } from 'react-native';
import { Colors, Fonts } from '../utils/theme';
import { clearSession, hydrateSession, isAuthenticated, subscribeSession } from '../services/session';
import {
  getAppLockState, handleAppLockState, hydrateAppLock, subscribeAppLock,
} from '../services/appLock';
import { AppLockView } from '../components/security/AppLockView';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppAlertHost } from '../components/security/AppAlertHost';

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [fontsLoaded, fontError] = useFonts({
    InstrumentSerif: require('../assets/fonts/InstrumentSerif-Regular.ttf'),
    PlexRegular: require('../assets/fonts/IBMPlexSans-Regular.ttf'),
    PlexMedium: require('../assets/fonts/IBMPlexSans-Medium.ttf'),
    PlexSemiBold: require('../assets/fonts/IBMPlexSans-SemiBold.ttf'),
  });
  const router = useRouter();
  const segments = useSegments();
  const appLock = useSyncExternalStore(subscribeAppLock, getAppLockState, getAppLockState);
  const gated = authed && (!appLock.ready || appLock.locked || appLock.covered);

  useEffect(() => {
    if (!gated) return;
    const listener = BackHandler.addEventListener('hardwareBackPress', () => true);
    return () => listener.remove();
  }, [gated]);

  useEffect(() => {
    let mounted = true;

    handleAppLockState(AppState.currentState || 'active');
    hydrateSession().then(() => hydrateAppLock()).finally(() => {
      if (mounted) {
        setAuthed(isAuthenticated());
        setReady(true);
      }
    });

    const unsubscribe = subscribeSession(() => {
      if (mounted) {
        setAuthed(isAuthenticated());
      }
    });
    const lifecycle = AppState.addEventListener('change', handleAppLockState);

    return () => {
      mounted = false;
      unsubscribe();
      lifecycle.remove();
    };
  }, []);

  useEffect(() => {
    if (!authed || !appLock.enabled || Platform.OS === 'web') return;
    let capture: typeof import('expo-screen-capture') | undefined;
    let disposed = false;
    try {
      capture = require('expo-screen-capture');
      capture!.preventScreenCaptureAsync('app-lock').then(async () => {
        if (disposed) await capture!.allowScreenCaptureAsync('app-lock');
      }).catch(() => {});
    } catch {
      // Older installed binaries still use the opaque JS privacy gate.
    }
    return () => {
      disposed = true;
      capture?.allowScreenCaptureAsync('app-lock').catch(() => {});
    };
  }, [authed, appLock.enabled]);

  useEffect(() => {
    if (!ready) {
      return;
    }
    const inAuthGroup = segments[0] === '(auth)';
    if (!authed && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (authed && inAuthGroup) {
      router.replace('/(tabs)');
    }
  }, [authed, ready, router, segments]);

  const booting = !ready || (!fontsLoaded && !fontError);

  if (booting) {
    return (
      <View style={styles.loading}>
        <Text style={styles.wordmark}>Bot04</Text>
        <ActivityIndicator size="small" color={Colors.inkMuted} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="dark" />
      <View
        style={styles.navigator}
        pointerEvents={gated ? 'none' : 'auto'}
        accessibilityElementsHidden={gated}
        importantForAccessibility={gated ? 'no-hide-descendants' : 'auto'}
      >
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: Colors.paper },
          animation: 'fade',
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="debts" options={{ headerShown: false }} />
        <Stack.Screen name="recurring" options={{ headerShown: false }} />
        <Stack.Screen name="transaction/[id]" options={{ headerShown: false }} />
        <Stack.Screen name="transaction-history" options={{ headerShown: false }} />
        <Stack.Screen name="change-password" options={{ headerShown: false }} />
        <Stack.Screen name="delete-account" options={{ headerShown: false }} />
        <Stack.Screen name="app-lock" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/register" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/forgot-password" options={{ headerShown: false }} />
      </Stack>
      </View>
      {gated ? (
        <View style={styles.lockCover} accessibilityViewIsModal>
          <SafeAreaProvider>
            <AppLockView onSignOut={async () => {
              await clearSession();
              router.replace('/(auth)/login');
            }} />
          </SafeAreaProvider>
        </View>
      ) : null}
      <AppAlertHost host="root" />
    </>
  );
}

const styles = StyleSheet.create({
  navigator: { flex: 1 },
  lockCover: { ...StyleSheet.absoluteFill, zIndex: 100, backgroundColor: Colors.paper },
  loading: {
    flex: 1,
    backgroundColor: Colors.paper,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
  },
  wordmark: {
    fontFamily: Fonts.serif,
    fontSize: 40,
    color: Colors.ink,
  },
});

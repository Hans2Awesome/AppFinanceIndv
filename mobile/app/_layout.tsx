import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Colors, Fonts } from '../utils/theme';
import { hydrateSession, isAuthenticated, subscribeSession } from '../services/session';

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

  useEffect(() => {
    let mounted = true;

    hydrateSession().finally(() => {
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

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

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
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: Colors.paper },
          animation: 'fade',
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="debts" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/register" options={{ headerShown: false }} />
      </Stack>
    </>
  );
}

const styles = StyleSheet.create({
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
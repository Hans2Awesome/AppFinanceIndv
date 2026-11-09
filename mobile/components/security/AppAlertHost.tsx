import React, { useEffect, useSyncExternalStore } from 'react';
import { BackHandler, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button } from '../ui/Button';
import { Colors, Space, Type } from '../../utils/theme';
import {
  dismissAppAlert, getAppAlert, pressAppAlert, registerAppAlertHost, subscribeAppAlert,
} from '../../services/appAlert';

export function AppAlertHost({ host, active = true }: { host: string; active?: boolean }) {
  const dialog = useSyncExternalStore(subscribeAppAlert, getAppAlert, getAppAlert);
  useEffect(() => active ? registerAppAlertHost(host) : undefined, [host, active]);
  useEffect(() => {
    if (!active || dialog?.host !== host) return;
    const back = BackHandler.addEventListener('hardwareBackPress', () => {
      dismissAppAlert();
      return true;
    });
    return () => back.remove();
  }, [host, active, dialog]);
  if (!active || dialog?.host !== host) return null;
  return (
    <View style={styles.cover} accessibilityViewIsModal>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.panel}>
          <Text style={styles.title} accessibilityRole="header">{dialog.title}</Text>
          {dialog.message ? <Text style={styles.body}>{dialog.message}</Text> : null}
          {dialog.buttons.map((button, index) => (
            <Button key={index} title={button.text || 'OK'}
              variant={button.style === 'destructive' ? 'danger' : button.style === 'cancel' ? 'secondary' : 'primary'}
              onPress={() => pressAppAlert(index)} />
          ))}
        </View>
      </ScrollView>
    </View>
  );
}
const styles = StyleSheet.create({
  cover: { ...StyleSheet.absoluteFill, zIndex: 200, backgroundColor: Colors.scrim },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: Space.lg },
  panel: { padding: Space.lg, backgroundColor: Colors.paper, borderRadius: 10, gap: Space.md },
  title: { ...Type.h2 },
  body: { ...Type.body },
});

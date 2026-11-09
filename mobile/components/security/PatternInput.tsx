import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  GestureResponderEvent,
  LayoutChangeEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Colors, Fonts, Radius, Space, Type } from '../../utils/theme';
import { appendPatternNode } from '../../utils/lockPattern';

export interface PatternInputProps {
  value: number[];
  onChange: (value: number[]) => void;
  disabled?: boolean;
  label?: string;
  hint?: string;
  accessibilityLabel?: string;
}

type InputMode = 'draw' | 'tap';

const NODES = [0, 1, 2, 3, 4, 5, 6, 7, 8] as const;

const NODE_POSITION_LABELS: Record<number, string> = {
  0: 'baris 1 kolom 1 (kiri atas)',
  1: 'baris 1 kolom 2 (tengah atas)',
  2: 'baris 1 kolom 3 (kanan atas)',
  3: 'baris 2 kolom 1 (kiri tengah)',
  4: 'baris 2 kolom 2 (tengah)',
  5: 'baris 2 kolom 3 (kanan tengah)',
  6: 'baris 3 kolom 1 (kiri bawah)',
  7: 'baris 3 kolom 2 (tengah bawah)',
  8: 'baris 3 kolom 3 (kanan bawah)',
};

const DEFAULT_BOARD_SIZE = 240;
const NODE_HIT_RATIO = 0.38;

function resolveHitNode(x: number, y: number, boardSize: number): number | null {
  if (!Number.isFinite(x) || !Number.isFinite(y) || boardSize <= 0) {
    return null;
  }
  if (x < 0 || y < 0 || x > boardSize || y > boardSize) {
    return null;
  }

  const cellSize = boardSize / 3;
  const maxDistance = cellSize * NODE_HIT_RATIO;

  for (let index = 0; index < NODES.length; index += 1) {
    const row = Math.floor(index / 3);
    const col = index % 3;
    const centerX = (col + 0.5) * cellSize;
    const centerY = (row + 0.5) * cellSize;
    const distance = Math.hypot(x - centerX, y - centerY);
    if (distance <= maxDistance) {
      return index;
    }
  }

  return null;
}

function getNodeCenter(node: number, boardSize: number): { x: number; y: number } {
  const cellSize = boardSize / 3;
  const row = Math.floor(node / 3);
  const col = node % 3;
  return {
    x: (col + 0.5) * cellSize,
    y: (row + 0.5) * cellSize,
  };
}

function samePattern(left: readonly number[], right: readonly number[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) {
      return false;
    }
  }
  return true;
}

export function PatternInput({
  value,
  onChange,
  disabled = false,
  label,
  hint,
  accessibilityLabel = 'Pola kunci 3x3',
}: PatternInputProps) {
  const [mode, setMode] = useState<InputMode>('draw');
  const [boardSize, setBoardSize] = useState(DEFAULT_BOARD_SIZE);
  const activePatternRef = useRef<number[]>(value);
  const drawingRef = useRef(false);

  activePatternRef.current = value;

  useEffect(() => () => {
    activePatternRef.current = [];
    drawingRef.current = false;
  }, []);

  useEffect(() => {
    if (disabled || value.length === 0) drawingRef.current = false;
  }, [disabled, value.length]);

  const handleBoardLayout = useCallback((event: LayoutChangeEvent) => {
    const width = event.nativeEvent.layout.width;
    if (width > 0) {
      setBoardSize(width);
    }
  }, []);

  const appendAtCoordinates = useCallback(
    (x: number, y: number, basePattern: readonly number[]) => {
      const hit = resolveHitNode(x, y, boardSize);
      if (hit === null) {
        return;
      }
      const next = appendPatternNode(basePattern, hit);
      if (!samePattern(basePattern, next)) {
        activePatternRef.current = next;
        onChange(next);
      }
    },
    [boardSize, onChange]
  );

  const handleResponderGrant = useCallback(
    (event: GestureResponderEvent) => {
      if (disabled || mode !== 'draw') {
        return;
      }
      const { locationX, locationY } = event.nativeEvent;
      const hit = resolveHitNode(locationX, locationY, boardSize);
      if (hit !== null) {
        drawingRef.current = true;
        const next = appendPatternNode([], hit);
        activePatternRef.current = next;
        onChange(next);
      }
    },
    [boardSize, disabled, mode, onChange]
  );

  const handleResponderMove = useCallback(
    (event: GestureResponderEvent) => {
      if (disabled || mode !== 'draw' || !drawingRef.current) {
        return;
      }
      const { locationX, locationY } = event.nativeEvent;
      appendAtCoordinates(locationX, locationY, activePatternRef.current);
    },
    [appendAtCoordinates, disabled, mode]
  );

  const handleResponderRelease = useCallback(() => {
    drawingRef.current = false;
  }, []);

  const handleResponderTerminate = useCallback(() => {
    if (!drawingRef.current) {
      return;
    }
    drawingRef.current = false;
    if (activePatternRef.current.length > 0) {
      activePatternRef.current = [];
      onChange([]);
    }
  }, [onChange]);

  const handleTapNode = useCallback(
    (node: number) => {
      if (disabled) {
        return;
      }
      const next = appendPatternNode(activePatternRef.current, node);
      if (!samePattern(activePatternRef.current, next)) {
        activePatternRef.current = next;
        onChange(next);
      }
    },
    [disabled, onChange]
  );

  const handleClear = useCallback(() => {
    if (disabled || value.length === 0) {
      return;
    }
    drawingRef.current = false;
    activePatternRef.current = [];
    onChange([]);
  }, [disabled, onChange, value.length]);

  const selectedSet = new Set(value);

  return (
    <View style={styles.container}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}

      <View style={styles.modeSwitch} accessibilityRole="tablist">
        <Pressable
          onPress={() => {
            drawingRef.current = false;
            setMode('draw');
          }}
          disabled={disabled}
          accessibilityRole="tab"
          accessibilityState={{ selected: mode === 'draw', disabled }}
          accessibilityLabel="Mode garis sentuh"
          style={[
            styles.modeTab,
            mode === 'draw' && styles.modeTabActive,
            disabled && styles.controlDisabled,
          ]}
        >
          <Text style={[styles.modeTabText, mode === 'draw' && styles.modeTabTextActive]}>
            Garis sentuh
          </Text>
        </Pressable>
        <Pressable
          onPress={() => {
            drawingRef.current = false;
            setMode('tap');
          }}
          disabled={disabled}
          accessibilityRole="tab"
          accessibilityState={{ selected: mode === 'tap', disabled }}
          accessibilityLabel="Mode ketuk titik berurutan"
          style={[
            styles.modeTab,
            mode === 'tap' && styles.modeTabActive,
            disabled && styles.controlDisabled,
          ]}
        >
          <Text style={[styles.modeTabText, mode === 'tap' && styles.modeTabTextActive]}>
            Ketuk titik
          </Text>
        </Pressable>
      </View>

      <View style={styles.boardWrap}>
        {mode === 'draw' ? (
          <View
            onLayout={handleBoardLayout}
            accessible
            accessibilityLabel={`${accessibilityLabel}. ${value.length} dari minimal 4 titik dipilih. Gunakan tab Ketuk titik untuk memilih titik secara berurutan dengan pembaca layar.`}
            onStartShouldSetResponder={(event) => !disabled && resolveHitNode(
              event.nativeEvent.locationX, event.nativeEvent.locationY, boardSize
            ) !== null}
            onMoveShouldSetResponder={() => false}
            onResponderTerminationRequest={() => false}
            onResponderGrant={handleResponderGrant}
            onResponderMove={handleResponderMove}
            onResponderRelease={handleResponderRelease}
            onResponderTerminate={handleResponderTerminate}
            style={[
              styles.board,
              { width: boardSize, height: boardSize },
              disabled && styles.boardDisabled,
            ]}
          >
            <View pointerEvents="none" style={StyleSheet.absoluteFill}>
              {value.map((node, index) => {
                if (index === 0) {
                  return null;
                }
                const from = getNodeCenter(value[index - 1], boardSize);
                const to = getNodeCenter(node, boardSize);
                const dx = to.x - from.x;
                const dy = to.y - from.y;
                const length = Math.hypot(dx, dy);
                const angleRad = Math.atan2(dy, dx);
                const midX = (from.x + to.x) / 2;
                const midY = (from.y + to.y) / 2;

                return (
                  <View
                    key={`seg-${value[index - 1]}-${node}`}
                    style={[
                      styles.segment,
                      {
                        width: length,
                        left: midX - length / 2,
                        top: midY - 1.5,
                        transform: [{ rotate: `${angleRad}rad` }],
                      },
                    ]}
                  />
                );
              })}

              {NODES.map((node) => {
                const center = getNodeCenter(node, boardSize);
                const selected = selectedSet.has(node);
                return (
                  <View
                    key={`node-${node}`}
                    style={[
                      styles.drawNodeOuter,
                      {
                        left: center.x - 24,
                        top: center.y - 24,
                      },
                      selected && styles.nodeOuterSelected,
                    ]}
                  >
                    <View style={[styles.nodeDot, selected && styles.nodeDotSelected]} />
                  </View>
                );
              })}
            </View>
          </View>
        ) : (
          <View
            style={[
              styles.tapBoard,
              { width: boardSize, minHeight: boardSize },
              disabled && styles.boardDisabled,
            ]}
          >
            {[0, 1, 2].map((row) => (
              <View key={`row-${row}`} style={styles.tapRow}>
                {[0, 1, 2].map((col) => {
                  const node = row * 3 + col;
                  const selected = selectedSet.has(node);
                  const posLabel = NODE_POSITION_LABELS[node];
                  return (
                    <Pressable
                      key={`tap-${node}`}
                      onPress={() => handleTapNode(node)}
                      disabled={disabled || selected}
                      accessibilityRole="button"
                      accessibilityLabel={`Titik ${posLabel}`}
                      accessibilityHint={
                        selected
                          ? 'Titik ini sudah dipilih dalam urutan pola'
                          : 'Ketuk untuk menambahkan titik ke urutan pola'
                      }
                      accessibilityState={{
                        disabled: disabled || selected,
                        selected,
                      }}
                      style={({ pressed }) => [
                        styles.tapNodeButton,
                        selected && styles.nodeOuterSelected,
                        pressed && !selected && !disabled && styles.tapNodePressed,
                      ]}
                    >
                      <View style={[styles.nodeDot, selected && styles.nodeDotSelected]} />
                    </Pressable>
                  );
                })}
              </View>
            ))}
          </View>
        )}
      </View>

      <View style={styles.footerRow}>
        <Text style={styles.counterText} accessibilityLiveRegion="polite">
          {value.length === 0
            ? 'Belum ada titik dipilih (minimal 4 titik)'
            : value.length < 4
            ? `${value.length} titik dipilih (minimal 4 titik)`
            : `${value.length} titik dipilih`}
        </Text>
        <Pressable
          onPress={handleClear}
          disabled={disabled || value.length === 0}
          accessibilityRole="button"
          accessibilityLabel="Hapus pola"
          accessibilityState={{ disabled: disabled || value.length === 0 }}
          style={({ pressed }) => [
            styles.clearButton,
            (disabled || value.length === 0) && styles.controlDisabled,
            pressed && !disabled && value.length > 0 && styles.clearButtonPressed,
          ]}
        >
          <Text style={styles.clearButtonText}>Ulangi pola</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Space.sm,
  },
  label: {
    fontFamily: Fonts.medium,
    fontSize: 12,
    lineHeight: 16,
    color: Colors.inkSoft,
  },
  hint: {
    ...Type.caption,
    color: Colors.inkMuted,
  },
  modeSwitch: {
    flexDirection: 'row',
    backgroundColor: Colors.surfaceAlt,
    borderRadius: Radius.control,
    borderWidth: 1,
    borderColor: Colors.line,
    padding: 2,
    gap: Space.xs,
  },
  modeTab: {
    flex: 1,
    minHeight: 44,
    borderRadius: Radius.control - 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Space.sm,
  },
  modeTabActive: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
  },
  modeTabText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.inkSoft,
  },
  modeTabTextActive: {
    fontFamily: Fonts.semibold,
    color: Colors.ink,
  },
  boardWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Space.xs,
  },
  board: {
    backgroundColor: Colors.paper,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
    borderRadius: Radius.block,
    position: 'relative',
    overflow: 'hidden',
  },
  tapBoard: {
    backgroundColor: Colors.paper,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
    borderRadius: Radius.block,
    padding: Space.md,
    justifyContent: 'space-between',
    gap: Space.md,
  },
  boardDisabled: {
    opacity: 0.45,
  },
  tapRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: Space.md,
  },
  drawNodeOuter: {
    position: 'absolute',
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tapNodeButton: {
    width: 56,
    height: 56,
    minWidth: 44,
    minHeight: 44,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: Colors.lineStrong,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tapNodePressed: {
    backgroundColor: Colors.surfaceAlt,
  },
  nodeOuterSelected: {
    borderColor: Colors.ink,
    borderWidth: 2,
    backgroundColor: Colors.inkTint,
  },
  nodeDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.inkMuted,
  },
  nodeDotSelected: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: Colors.ink,
  },
  segment: {
    position: 'absolute',
    height: 3,
    borderRadius: 1.5,
    backgroundColor: Colors.ink,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.sm,
  },
  counterText: {
    ...Type.caption,
    color: Colors.inkMuted,
    flex: 1,
    fontVariant: ['tabular-nums'],
  },
  clearButton: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: Space.md,
    borderRadius: Radius.control,
    borderWidth: 1,
    borderColor: Colors.line,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  clearButtonPressed: {
    backgroundColor: Colors.surfaceAlt,
  },
  clearButtonText: {
    fontFamily: Fonts.medium,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.ink,
  },
  controlDisabled: {
    opacity: 0.45,
  },
});

export default PatternInput;

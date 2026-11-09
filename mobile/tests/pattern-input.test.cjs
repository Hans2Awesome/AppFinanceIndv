/**
 * Runtime interaction tests for the 3x3 pattern grid without adding a renderer
 * dependency. The TSX component is transpiled with a tiny JSX factory, React
 * hooks are stubbed with deterministic slots, and React Native host components
 * are plain trees whose event props the test invokes directly.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const COMPONENT_PATH = path.join(root, 'components/security/PatternInput.tsx');
const HELPER_PATH = path.join(root, 'utils/lockPattern.ts');

const NODE_LABELS = {
  0: 'Titik baris 1 kolom 1 (kiri atas)',
  1: 'Titik baris 1 kolom 2 (tengah atas)',
  2: 'Titik baris 1 kolom 3 (kanan atas)',
  3: 'Titik baris 2 kolom 1 (kiri tengah)',
  4: 'Titik baris 2 kolom 2 (tengah)',
  5: 'Titik baris 2 kolom 3 (kanan tengah)',
  6: 'Titik baris 3 kolom 1 (kiri bawah)',
  7: 'Titik baris 3 kolom 2 (tengah bawah)',
  8: 'Titik baris 3 kolom 3 (kanan bawah)',
};

function sameDeps(left, right) {
  if (left === undefined || right === undefined) return false;
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (!Object.is(left[index], right[index])) return false;
  }
  return true;
}

function createHooks() {
  const hooks = [];
  const refs = [];
  const effectSlots = new Set();
  let cursor = 0;
  let dirty = false;
  let unmounted = false;

  function useState(initial) {
    const index = cursor;
    cursor += 1;
    if (!hooks[index]) {
      hooks[index] = {
        kind: 'state',
        value: typeof initial === 'function' ? initial() : initial,
      };
    }
    const slot = hooks[index];
    if (!slot.setter) {
      slot.setter = (next) => {
        if (unmounted) return;
        const value = typeof next === 'function' ? next(slot.value) : next;
        if (Object.is(value, slot.value)) return;
        slot.value = value;
        dirty = true;
      };
    }
    return [slot.value, slot.setter];
  }

  function useRef(initial) {
    const index = cursor;
    cursor += 1;
    if (!hooks[index]) {
      hooks[index] = { kind: 'ref', current: initial };
      refs.push(hooks[index]);
    }
    return hooks[index];
  }

  function useCallback(callback, deps) {
    const index = cursor;
    cursor += 1;
    const slot = hooks[index];
    if (!slot || slot.kind !== 'callback') {
      hooks[index] = { kind: 'callback', callback, deps };
    } else if (!sameDeps(slot.deps, deps)) {
      slot.callback = callback;
      slot.deps = deps;
    }
    return hooks[index].callback;
  }

  function useEffect(effect, deps) {
    const index = cursor;
    cursor += 1;
    const slot = hooks[index];
    if (!slot || slot.kind !== 'effect') {
      hooks[index] = { kind: 'effect', effect, deps, cleanup: null, pending: true };
      effectSlots.add(hooks[index]);
    } else if (!sameDeps(slot.deps, deps)) {
      slot.effect = effect;
      slot.deps = deps;
      slot.pending = true;
    }
  }

  function runEffects() {
    for (const slot of effectSlots) {
      if (!slot.pending) continue;
      slot.pending = false;
      if (typeof slot.cleanup === 'function') slot.cleanup();
      const cleanup = slot.effect();
      slot.cleanup = typeof cleanup === 'function' ? cleanup : null;
    }
  }

  function unmount() {
    if (unmounted) return;
    unmounted = true;
    for (const slot of effectSlots) {
      if (typeof slot.cleanup === 'function') slot.cleanup();
      slot.cleanup = null;
    }
  }

  return {
    hooks,
    refs,
    useState,
    useRef,
    useCallback,
    useEffect,
    get dirty() {
      return dirty;
    },
    markClean() {
      dirty = false;
    },
    resetCursor() {
      cursor = 0;
    },
    runEffects,
    unmount,
    isUnmounted() {
      return unmounted;
    },
  };
}

function createRenderer() {
  const hook = createHooks();
  let props = {};
  let tree = null;
  let Component = null;

  const React = {
    useState: hook.useState,
    useRef: hook.useRef,
    useCallback: hook.useCallback,
    useEffect: hook.useEffect,
    createElement: h,
  };
  React.default = React;

  function h(type, nextProps, ...children) {
    return {
      type,
      props: nextProps || {},
      children: children.flat(Infinity),
    };
  }

  function renderOnce() {
    hook.resetCursor();
    tree = Component(props);
    hook.runEffects();
  }

  function flush() {
    let guard = 0;
    do {
      hook.markClean();
      renderOnce();
    } while (hook.dirty && (guard += 1) < 20);
  }

  function mount(initialProps) {
    props = { ...initialProps };
    flush();
  }

  function setProps(patch) {
    props = { ...props, ...patch };
  }

  function update(patch) {
    setProps(patch);
    flush();
  }

  function act(callback) {
    const result = callback();
    flush();
    return result;
  }

  return {
    React,
    h,
    setComponent(next) {
      Component = next;
    },
    setProps,
    mount,
    update,
    act,
    flush,
    unmount: hook.unmount,
    refs: hook.refs,
    get tree() {
      return tree;
    },
    get props() {
      return props;
    },
  };
}

function elements(rootNode) {
  const found = [];
  function visit(node) {
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    if (!node || typeof node !== 'object') return;
    if (node.type !== undefined) found.push(node);
    (node.children || []).forEach(visit);
  }
  visit(rootNode);
  return found;
}

function byLabel(tree, label) {
  return elements(tree).find((element) => element.props.accessibilityLabel === label);
}

function boardElement(tree) {
  return elements(tree).find(
    (element) => element.props.accessible === true &&
      typeof element.props.onResponderGrant === 'function',
  );
}

function createPatternInput() {
  const renderer = createRenderer();
  const helperModule = loadHelper();
  const componentModule = loadComponent(helperModule, renderer.React);
  renderer.setComponent(componentModule.PatternInput);

  let value = [];
  const changes = [];
  const onChange = (next) => {
    const copy = Array.from(next);
    changes.push(copy);
    value = copy;
    renderer.setProps({ value });
  };

  renderer.mount({ value: [], onChange });
  return {
    renderer,
    changes,
    value: () => value,
    board: () => boardElement(renderer.tree),
    tapNode(node) {
      const button = byLabel(renderer.tree, NODE_LABELS[node]);
      assert.ok(button, `tap node ${node} must be rendered`);
      renderer.act(() => button.props.onPress());
    },
    draw(x, y) {
      const board = boardElement(renderer.tree);
      assert.ok(board, 'draw board must be rendered');
      renderer.act(() => board.props.onResponderGrant({ nativeEvent: { locationX: x, locationY: y } }));
    },
    move(x, y) {
      const board = boardElement(renderer.tree);
      assert.ok(board, 'draw board must be rendered');
      renderer.act(() => board.props.onResponderMove({ nativeEvent: { locationX: x, locationY: y } }));
    },
    release() {
      const board = boardElement(renderer.tree);
      renderer.act(() => board.props.onResponderRelease());
    },
    terminate() {
      const board = boardElement(renderer.tree);
      renderer.act(() => board.props.onResponderTerminate());
    },
    start(x, y) {
      const board = boardElement(renderer.tree);
      assert.ok(board, 'draw board must be rendered');
      return board.props.onStartShouldSetResponder({
        nativeEvent: { locationX: x, locationY: y },
      });
    },
    moveShouldSet() {
      const board = boardElement(renderer.tree);
      assert.ok(board, 'draw board must be rendered');
      return board.props.onMoveShouldSetResponder();
    },
    switchTo(label) {
      const tab = byLabel(renderer.tree, label);
      assert.ok(tab, `mode tab ${label} must be rendered`);
      renderer.act(() => tab.props.onPress());
    },
    clear() {
      const button = byLabel(renderer.tree, 'Hapus pola');
      assert.ok(button, 'clear control must be rendered');
      renderer.act(() => button.props.onPress());
    },
  };
}

function loadTsModule(file, requireFor) {
  const source = fs.readFileSync(file, 'utf8');
  const sandbox = { exports: {}, module: { exports: {} }, console };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.require = requireFor;
  const javascript = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: false,
    },
  }).outputText;
  vm.runInNewContext(javascript, sandbox, { filename: file });
  return Object.keys(sandbox.module.exports).length
    ? sandbox.module.exports
    : sandbox.exports;
}

function loadHelper() {
  return loadTsModule(HELPER_PATH, (name) => {
    throw new Error(`Unexpected module in lock pattern helpers: ${name}`);
  });
}

function loadComponent(helperModule, React) {
  const token = new Proxy({}, {
    get(target, key) {
      if (key === 'toString') return () => 'token';
      if (key === Symbol.toPrimitive) return () => 0;
      return token;
    },
  });
  const theme = {
    Colors: token,
    Fonts: token,
    Radius: token,
    Space: token,
    Type: token,
  };

  const reactNative = {
    View: 'View',
    Text: 'Text',
    Pressable: 'Pressable',
    StyleSheet: {
      create: (styles) => styles,
      absoluteFill: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 },
    },
  };

  const source = fs.readFileSync(COMPONENT_PATH, 'utf8');
  const javascript = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: false,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  }).outputText;

  const sandbox = { exports: {}, module: { exports: {} }, console };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.h = (type, props, ...children) => ({
    type,
    props: props || {},
    children: children.flat(Infinity),
  });
  sandbox.require = (name) => {
    switch (name) {
      case 'react':
        return React;
      case 'react-native':
        return reactNative;
      case '../../utils/theme':
        return theme;
      case '../../utils/lockPattern':
        return helperModule;
      default:
        throw new Error(`Unexpected module in PatternInput: ${name}`);
    }
  };

  vm.runInNewContext(javascript, sandbox, { filename: COMPONENT_PATH });
  return Object.keys(sandbox.module.exports).length
    ? sandbox.module.exports
    : sandbox.exports;
}

test('draw responder appends touched nodes, auto-inserts a midpoint, and stops after release', () => {
  const grid = createPatternInput();

  grid.draw(40, 40);
  assert.deepEqual(grid.value(), [0]);

  grid.move(200, 40);
  assert.deepEqual(grid.value(), [0, 1, 2], 'straight jump must visit its midpoint');

  grid.move(200, 120);
  assert.deepEqual(grid.value(), [0, 1, 2, 5]);

  grid.release();
  grid.move(200, 200);
  assert.deepEqual(grid.value(), [0, 1, 2, 5], 'moves after release must be ignored');

  grid.terminate();
  assert.deepEqual(grid.value(), [0, 1, 2, 5], 'terminate after release must be a no-op');
});

test('board misses preserve the draft, reject responder claims, and leave scrolling available', () => {
  const grid = createPatternInput();
  grid.draw(40, 40);
  grid.move(200, 40);
  assert.deepEqual(grid.value(), [0, 1, 2]);
  grid.release();

  assert.equal(grid.start(10, 10), false, 'empty board space must not claim the gesture');
  assert.equal(grid.moveShouldSet(), false, 'moves must not hijack an existing scroll');

  const before = grid.changes.length;
  grid.draw(10, 10);
  assert.deepEqual(grid.value(), [0, 1, 2], 'a miss must not clear an existing draft');
  assert.equal(grid.changes.length, before, 'a miss must not emit a pattern change');
  assert.equal(grid.renderer.refs[1].current, false, 'a miss must not start drawing');

  grid.move(200, 120);
  assert.deepEqual(grid.value(), [0, 1, 2], 'a miss must not resume drawing');

  const empty = createPatternInput();
  assert.equal(empty.start(10, 10), false);
  assert.equal(empty.moveShouldSet(), false);
  assert.equal(empty.start(40, 40), true, 'a hit node must claim the gesture');
  empty.draw(40, 40);
  assert.deepEqual(empty.value(), [0]);

  empty.renderer.update({ disabled: true });
  assert.equal(empty.start(40, 40), false, 'disabled input must not claim the gesture');
});

test('responder terminate clears the partially drawn pattern', () => {
  const grid = createPatternInput();

  grid.draw(40, 40);
  grid.move(120, 120);
  assert.deepEqual(grid.value(), [0, 4]);

  grid.terminate();
  assert.deepEqual(grid.value(), []);

  grid.move(120, 40);
  assert.deepEqual(grid.value(), [], 'a terminated gesture must not resume');
});

test('tap mode selects accessible nodes sequentially and preserves midpoint rules', () => {
  const grid = createPatternInput();

  grid.switchTo('Mode ketuk titik berurutan');
  grid.tapNode(0);
  assert.deepEqual(grid.value(), [0]);

  grid.tapNode(2);
  assert.deepEqual(grid.value(), [0, 1, 2], 'tap mode must append the skipped midpoint too');

  grid.tapNode(5);
  assert.deepEqual(grid.value(), [0, 1, 2, 5]);

  const selected = byLabel(grid.renderer.tree, NODE_LABELS[1]);
  assert.equal(selected.props.disabled, true, 'selected tap nodes must be disabled');
  assert.equal(selected.props.accessibilityState.selected, true);

  grid.switchTo('Mode garis sentuh');
  assert.ok(grid.board(), 'switching back must restore the draw board');
});

test('the grid exposes no submit control or auto-submit callback', () => {
  const grid = createPatternInput();
  const all = elements(grid.renderer.tree);

  assert.equal(all.some((element) => element.props.onSubmit), false);
  assert.equal(all.some((element) => element.props.onComplete), false);
  assert.equal(
    all.some((element) => /simpan|kirim|lanjut|submit/i.test(String(element.props.accessibilityLabel || ''))),
    false,
  );
});

test('clear resets the pattern, disables itself when empty, and empties the active drawing', () => {
  const grid = createPatternInput();

  grid.draw(40, 40);
  grid.move(120, 120);
  assert.deepEqual(grid.value(), [0, 4]);

  grid.clear();
  assert.deepEqual(grid.value(), []);
  const clearButton = byLabel(grid.renderer.tree, 'Hapus pola');
  assert.equal(clearButton.props.disabled, true);
  assert.equal(clearButton.props.accessibilityState.disabled, true);

  const before = grid.changes.length;
  grid.clear();
  assert.equal(grid.changes.length, before, 'clearing an empty grid must not emit a change');

  grid.move(200, 40);
  assert.deepEqual(grid.value(), [], 'drawing must stay reset after the pattern is emptied');
});

test('disabled and empty values reset the drawing latch, and disabled input is ignored', () => {
  const grid = createPatternInput();

  grid.draw(40, 40);
  assert.deepEqual(grid.value(), [0]);

  grid.renderer.update({ disabled: true });
  assert.equal(grid.renderer.refs[1].current, false, 'disabled must reset the drawing latch');

  const before = grid.changes.length;
  grid.draw(200, 200);
  assert.equal(grid.changes.length, before, 'disabled draw input must be ignored');

  grid.renderer.update({ disabled: false });
  grid.move(120, 120);
  assert.deepEqual(grid.value(), [0], 'a latch reset by disabled must not resume on re-enable');

  grid.clear();
  grid.renderer.update({ disabled: false });
  assert.equal(grid.renderer.refs[1].current, false);
  grid.move(120, 120);
  assert.deepEqual(grid.value(), [], 'an empty pattern must keep the drawing latch reset');
});

test('unmount clears the active pattern and drawing refs', () => {
  const grid = createPatternInput();

  grid.draw(40, 40);
  assert.deepEqual(grid.renderer.refs[0].current, [0]);
  assert.equal(grid.renderer.refs[1].current, true);

  const staleBoard = grid.board();
  const before = grid.changes.length;
  grid.renderer.unmount();

  assert.deepEqual(Array.from(grid.renderer.refs[0].current), []);
  assert.equal(grid.renderer.refs[1].current, false);

  staleBoard.props.onResponderMove({ nativeEvent: { locationX: 120, locationY: 120 } });
  assert.equal(grid.changes.length, before, 'a stale handler after unmount must not emit a change');
});
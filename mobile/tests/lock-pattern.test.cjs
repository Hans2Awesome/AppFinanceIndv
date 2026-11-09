/**
 * Pure tests for the 3x3 pattern helpers used by the optional app-lock pattern.
 *
 * There is no native dependency here: `utils/lockPattern.ts` is transpiled with
 * the repository's TypeScript package and evaluated in a VM context.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const HELPER_PATH = path.join(root, 'utils/lockPattern.ts');

function loadHelpers() {
  const source = fs.readFileSync(HELPER_PATH, 'utf8');
  const sandbox = {
    exports: {},
    module: { exports: {} },
    console,
  };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.require = (name) => {
    throw new Error(`Unexpected module in lock pattern helpers: ${name}`);
  };
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: false },
  }).outputText;
  vm.runInNewContext(javascript, sandbox, { filename: HELPER_PATH });
  const exported = Object.keys(sandbox.module.exports).length
    ? sandbox.module.exports
    : sandbox.exports;
  const append = exported.appendPatternNode;
  return {
    ...exported,
    // Arrays created inside the VM have a different realm prototype. Convert
    // them so Node's deepStrictEqual compares structure, not object identity.
    appendPatternNode: (pattern, node) => Array.from(append(pattern, node)),
  };
}

const helpers = loadHelpers();

test('appendPatternNode adds a node and ignores duplicate or invalid node ids', () => {
  assert.deepEqual(helpers.appendPatternNode([], 0), [0]);
  assert.deepEqual(helpers.appendPatternNode([0], 1), [0, 1]);
  assert.deepEqual(helpers.appendPatternNode([0, 1], 1), [0, 1]);
  assert.deepEqual(helpers.appendPatternNode([4, 0], 0), [4, 0]);

  for (const invalid of [-1, 9, 1.5, NaN, Infinity, '3', null, undefined]) {
    assert.deepEqual(
      helpers.appendPatternNode([0, 1], invalid),
      [0, 1],
      `invalid node id ${String(invalid)} must be ignored`,
    );
  }
});

test('appendPatternNode inserts the unvisited midpoint on all eight two-cell directions', () => {
  const cases = [
    { start: 0, node: 2, expected: [0, 1, 2] },
    { start: 2, node: 0, expected: [2, 1, 0] },
    { start: 0, node: 6, expected: [0, 3, 6] },
    { start: 6, node: 0, expected: [6, 3, 0] },
    { start: 6, node: 8, expected: [6, 7, 8] },
    { start: 8, node: 6, expected: [8, 7, 6] },
    { start: 2, node: 8, expected: [2, 5, 8] },
    { start: 8, node: 2, expected: [8, 5, 2] },
    { start: 0, node: 8, expected: [0, 4, 8] },
    { start: 8, node: 0, expected: [8, 4, 0] },
    { start: 2, node: 6, expected: [2, 4, 6] },
    { start: 6, node: 2, expected: [6, 4, 2] },
  ];

  for (const { start, node, expected } of cases) {
    assert.deepEqual(
      helpers.appendPatternNode([start], node),
      expected,
      `straight jump ${start} -> ${node} must add its midpoint`,
    );
  }
});

test('appendPatternNode does not insert a midpoint that was already visited', () => {
  assert.deepEqual(helpers.appendPatternNode([4, 0], 8), [4, 0, 8]);
  assert.deepEqual(helpers.appendPatternNode([4, 2], 6), [4, 2, 6]);
  assert.deepEqual(helpers.appendPatternNode([1, 0], 2), [1, 0, 2]);
  assert.deepEqual(helpers.appendPatternNode([3, 6], 0), [3, 6, 0]);
});

test('appendPatternNode leaves non-midpoint jumps unchanged', () => {
  for (const node of [1, 3, 4, 5, 7]) {
    assert.deepEqual(helpers.appendPatternNode([0], node), [0, node]);
  }

  assert.deepEqual(helpers.appendPatternNode([1], 6), [1, 6]);
  assert.deepEqual(helpers.appendPatternNode([8], 3), [8, 3]);
  assert.deepEqual(helpers.appendPatternNode([2], 7), [2, 7]);
});

test('appendPatternNode never mutates the input pattern', () => {
  const pattern = Object.freeze([0, 1]);
  const result = helpers.appendPatternNode(pattern, 2);

  assert.deepEqual(pattern, [0, 1]);
  assert.deepEqual(result, [0, 1, 2]);
  assert.notEqual(result, pattern);
});

test('isValidLockPattern accepts canonical unique patterns of four to nine nodes', () => {
  const valid = [
    [0, 1, 2, 5],
    [6, 3, 0, 1],
    [0, 4, 8, 7],
    [1, 0, 2, 5],
    [4, 0, 8, 5],
    [4, 2, 6, 7],
    [0, 1, 2, 5, 8],
    [0, 1, 2, 5, 8, 7, 6, 3, 4],
  ];

  for (const pattern of valid) {
    assert.equal(helpers.isValidLockPattern(pattern), true, String(pattern));
  }
});

test('isValidLockPattern rejects lengths outside four to nine', () => {
  for (const pattern of [
    [],
    [0],
    [0, 1],
    [0, 1, 2],
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 0],
  ]) {
    assert.equal(helpers.isValidLockPattern(pattern), false, String(pattern));
  }
});

test('isValidLockPattern rejects duplicate nodes and invalid node ids', () => {
  for (const pattern of [
    [0, 1, 2, 1],
    [0, 1, 2, 2],
    [4, 4, 5, 6],
    [0, 1, 2, 9],
    [-1, 0, 1, 2],
    [0, 1, 2, 1.5],
    [0, 1, 2, NaN],
    [0, 1, 2, Infinity],
    ['0', 1, 2, 3],
  ]) {
    assert.equal(helpers.isValidLockPattern(pattern), false, String(pattern));
  }
});

test('isValidLockPattern rejects straight jumps whose midpoint was skipped', () => {
  const skipped = [
    [0, 2, 5, 8],
    [2, 0, 7, 6],
    [0, 6, 7, 8],
    [6, 0, 1, 2],
    [2, 8, 7, 6],
    [8, 2, 1, 0],
    [0, 8, 7, 6],
    [8, 0, 1, 2],
    [2, 6, 3, 0],
    [6, 2, 1, 0],
  ];

  for (const pattern of skipped) {
    assert.equal(helpers.isValidLockPattern(pattern), false, String(pattern));
  }
});

test('isValidLockPattern fails safe for malformed runtime values', () => {
  for (const value of [null, undefined, '0125', 5, {}, { length: 4 }]) {
    assert.equal(helpers.isValidLockPattern(value), false);
  }
});
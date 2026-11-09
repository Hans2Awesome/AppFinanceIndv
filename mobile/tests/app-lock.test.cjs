/**
 * Dependency-free security boundary tests for the device-local app lock.
 *
 * The native modules are replaced with deterministic in-memory fakes before
 * `services/appLock.ts` is transpiled into a vm context, so no real SecureStore,
 * biometric prompt, network, or timer is ever touched.
 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const SERVICE_PATH = path.join(root, 'services/appLock.ts');
const PIN = '246813';
const NEXT_PIN = '135792';
const PATTERN = Object.freeze([0, 1, 2, 5]);
const NEXT_PATTERN = Object.freeze([6, 3, 0, 1, 2]);
const WRONG_PATTERN = Object.freeze([0, 4, 8, 7]);

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

async function waitFor(predicate, label) {
  for (let tick = 0; tick < 20; tick += 1) {
    if (predicate()) return;
    await flush();
  }
  assert.fail(label || 'condition was not reached');
}

async function settle(promise) {
  try {
    return { ok: true, value: await promise };
  } catch (error) {
    return { ok: false, error };
  }
}

async function expectRejects(promise, label) {
  const result = await settle(promise);
  assert.equal(result.ok, false, label || 'expected the operation to reject');
  assert.ok(result.error && typeof result.error.message === 'string');
  return result.error;
}

function createClock(start = 1760000000000) {
  let current = start;
  class FakeDate extends Date {
    constructor(...args) {
      if (args.length === 0) {
        super(current);
      } else {
        super(...args);
      }
    }
    static now() {
      return current;
    }
  }
  return {
    Date: FakeDate,
    now: () => current,
    advance(ms) {
      current += ms;
    },
    set(value) {
      current = value;
    },
  };
}

function createSecureStore() {
  const data = new Map();
  const fail = { available: false, get: false, set: false, delete: false };
  const calls = { get: 0, set: 0, delete: 0 };
  let gate = null;
  let readGate = null;
  let deleteGate = null;

  const module = {
    WHEN_UNLOCKED_THIS_DEVICE_ONLY: 'WHEN_UNLOCKED_THIS_DEVICE_ONLY',
    async isAvailableAsync() {
      return !fail.available;
    },
    async getItemAsync(key) {
      calls.get += 1;
      if (readGate) await readGate.promise;
      if (fail.get) throw new Error('secure store read failed');
      const value = data.get(key);
      return value === undefined ? null : value;
    },
    async setItemAsync(key, value) {
      calls.set += 1;
      if (gate) await gate.promise;
      if (fail.set) throw new Error('secure store write failed');
      data.set(String(key), String(value));
    },
    async deleteItemAsync(key) {
      calls.delete += 1;
      if (gate) await gate.promise;
      if (deleteGate) await deleteGate.promise;
      if (fail.delete) throw new Error('secure store delete failed');
      data.delete(String(key));
    },
    async getItem(key) {
      return this.getItemAsync(key);
    },
    async setItem(key, value) {
      return this.setItemAsync(key, value);
    },
    async deleteItem(key) {
      return this.deleteItemAsync(key);
    },
  };

  return {
    data,
    fail,
    calls,
    module,
    holdWrites() {
      gate = deferred();
      return () => {
        const pending = gate;
        gate = null;
        pending.resolve();
      };
    },
    holdReads() {
      readGate = deferred();
      return () => {
        const pending = readGate;
        readGate = null;
        pending.resolve();
      };
    },
    holdDeletes() {
      deleteGate = deferred();
      return () => {
        const pending = deleteGate;
        deleteGate = null;
        pending.resolve();
      };
    },
    values() {
      return [...data.entries()];
    },
  };
}

function createLocalAuth(config = {}) {
  const state = {
    hardware: config.hardware ?? true,
    enrolled: config.enrolled ?? true,
    level: config.level ?? 3,
    result: config.result ?? { success: true },
    pending: null,
    calls: 0,
    options: null,
  };

  const module = {
    SecurityLevel: { NONE: 0, SECRET: 1, BIOMETRIC: 2, BIOMETRIC_WEAK: 2, BIOMETRIC_STRONG: 3 },
    AuthenticationType: { FINGERPRINT: 1, FACIAL_RECOGNITION: 2, IRIS: 3 },
    async hasHardwareAsync() {
      return state.hardware;
    },
    async isEnrolledAsync() {
      return state.enrolled;
    },
    async getEnrolledLevelAsync() {
      return state.level;
    },
    async supportedAuthenticationTypesAsync() {
      return state.hardware ? [1, 2] : [];
    },
    async authenticateAsync(options) {
      state.calls += 1;
      state.options = options;
      if (state.pending) return state.pending.promise;
      return state.result;
    },
    async cancelAuthenticate() {},
  };

  return { state, module };
}

function createCrypto(context) {
  const U8 = context.Uint8Array || Uint8Array;
  const algorithms = {
    'SHA-1': 'sha1',
    'SHA-256': 'sha256',
    'SHA-384': 'sha384',
    'SHA-512': 'sha512',
  };
  const calls = { random: [], digest: [], digestData: [] };
  let digestGate = null;

  function randomBytes(size) {
    calls.random.push(size);
    return new U8(crypto.randomBytes(size));
  }

  function hash(algorithm, data) {
    const name = algorithms[algorithm] || 'sha256';
    return crypto.createHash(name).update(data);
  }

  async function waitForDigest() {
    if (digestGate) await digestGate.promise;
  }

  const module = {
    CryptoDigestAlgorithm: {
      SHA1: 'SHA-1',
      SHA256: 'SHA-256',
      SHA384: 'SHA-384',
      SHA512: 'SHA-512',
    },
    CryptoEncoding: { HEX: 'hex', BASE64: 'base64' },
    getRandomBytes(size) {
      return randomBytes(size);
    },
    async getRandomBytesAsync(size) {
      return randomBytes(size);
    },
    randomUUID() {
      return crypto.randomUUID();
    },
    getRandomValues(array) {
      array.set(crypto.randomBytes(array.length));
      return array;
    },
    async digestStringAsync(algorithm, data, options) {
      calls.digest.push(algorithm);
      calls.digestData.push(typeof data === 'string' ? data : Buffer.from(data).toString());
      await waitForDigest();
      const buffer = hash(algorithm, typeof data === 'string' ? data : Buffer.from(data)).digest();
      return options?.encoding === 'base64' ? buffer.toString('base64') : buffer.toString('hex');
    },
    async digest(algorithm, data) {
      calls.digest.push(algorithm);
      await waitForDigest();
      const buffer = hash(algorithm, Buffer.from(data)).digest();
      return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    },
  };

  return {
    module,
    calls,
    holdDigest() {
      digestGate = deferred();
      return () => {
        const pending = digestGate;
        digestGate = null;
        pending.resolve();
      };
    },
  };
}

function resolveLocalModule(fromFile, request) {
  const base = path.resolve(path.dirname(fromFile), request);
  const candidates = [
    base,
    `${base}.ts`,
    `${base}.tsx`,
    `${base}.js`,
    `${base}.cjs`,
    path.join(base, 'index.ts'),
    path.join(base, 'index.tsx'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
  }
  throw new Error(`Cannot resolve local module '${request}' from ${fromFile}`);
}

function loadService({ store, clock, localAuth, missing, os = 'android' }) {
  const logs = [];
  const required = [];
  const moduleCache = new Map();

  const cryptoApi = createCrypto({ Uint8Array });
  const screenCapture = {
    async preventScreenCaptureAsync() {},
    async allowScreenCaptureAsync() {},
    async isAvailableAsync() {
      return true;
    },
  };

  function nativeRequire(name) {
    switch (name) {
      case 'react-native':
        return {
          Platform: {
            OS: os,
            select: (choices) => choices[choices.os ?? os] ?? choices.default,
          },
        };
      case 'expo-secure-store':
        if (missing === 'secure-store') throw new Error("Cannot find module 'expo-secure-store'");
        return store.module;
      case 'expo-crypto':
        if (missing === 'crypto') throw new Error("Cannot find module 'expo-crypto'");
        return cryptoApi.module;
      case 'expo-local-authentication':
        if (missing === 'local-auth') {
          throw new Error("Cannot find module 'expo-local-authentication'");
        }
        return localAuth.module;
      case 'expo-screen-capture':
        return screenCapture;
      default:
        throw new Error(`Unexpected module in app lock service: ${name}`);
    }
  }

  function evaluate(file) {
    if (moduleCache.has(file)) return moduleCache.get(file);

    const sandbox = {
      exports: {},
      module: { exports: {} },
      __DEV__: false,
      process: { env: {} },
      console: {
        log: (...args) => logs.push(args),
        info: (...args) => logs.push(args),
        warn: (...args) => logs.push(args),
        error: (...args) => logs.push(args),
        debug: (...args) => logs.push(args),
      },
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
      setImmediate,
      Date: clock.Date,
    };
    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.require = (name) => {
      required.push(name);
      // The pattern helpers live in a local TypeScript module. Transpile it on
      // demand with the same native fakes instead of teaching the test a copy.
      if (name.startsWith('.')) {
        return evaluate(resolveLocalModule(file, name));
      }
      return nativeRequire(name);
    };

    const source = fs.readFileSync(file, 'utf8');
    const javascript = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: false },
    }).outputText;
    vm.runInNewContext(javascript, sandbox, { filename: file });
    const exported = Object.keys(sandbox.module.exports).length
      ? sandbox.module.exports
      : sandbox.exports;
    moduleCache.set(file, exported);
    return exported;
  }

  return { module: evaluate(SERVICE_PATH), crypto: cryptoApi, logs, required };
}

function createHarness(options = {}) {
  const store = options.store || createSecureStore();
  const clock = options.clock || createClock(options.now);
  const localAuth = options.localAuth || createLocalAuth(options.localAuthConfig);
  const service = loadService({ store, clock, localAuth, missing: options.missing, os: options.os });
  // A real app restores its signed-in session before hydrating the lock.
  if (options.authenticated !== false) service.module.setAppLockSession(true);
  return {
    ...service,
    store,
    clock,
    localAuth,
    state: () => service.module.getAppLockState(),
  };
}

function reload(harness) {
  return createHarness({
    store: harness.store,
    clock: harness.clock,
    localAuth: harness.localAuth,
  });
}

function loadSessionModule({ store, os = 'android' }) {
  const appLockCalls = [];
  const sandbox = {
    exports: {},
    module: { exports: {} },
    process: { env: {} },
    console,
    Date,
    setTimeout,
    clearTimeout,
    setImmediate,
  };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.require = (name) => {
    if (name === 'expo-secure-store') return store.module;
    if (name === 'react-native') return { Platform: { OS: os } };
    if (name === './appLock') {
      return {
        setAppLockSession(value) {
          appLockCalls.push(value);
        },
      };
    }
    throw new Error(`Unexpected module in session service: ${name}`);
  };
  const source = fs.readFileSync(path.join(root, 'services/session.ts'), 'utf8');
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: false },
  }).outputText;
  vm.runInNewContext(javascript, sandbox, { filename: 'session.ts' });
  const exported = Object.keys(sandbox.module.exports).length
    ? sandbox.module.exports
    : sandbox.exports;
  return { module: exported, appLockCalls };
}

function loadAlertModule() {
  const lockListeners = new Set();
  const sessionListeners = new Set();
  const lock = { ready: true, enabled: true, locked: false, covered: false };
  let authenticated = true;

  const sandbox = {
    exports: {},
    module: { exports: {} },
    console,
    Date,
    setTimeout,
    clearTimeout,
    setImmediate,
  };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.require = (name) => {
    if (name === './appLock') {
      return {
        getAppLockState: () => ({ ...lock }),
        subscribeAppLock: (listener) => {
          lockListeners.add(listener);
          return () => lockListeners.delete(listener);
        },
      };
    }
    if (name === './session') {
      return {
        isAuthenticated: () => authenticated,
        subscribeSession: (listener) => {
          sessionListeners.add(listener);
          return () => sessionListeners.delete(listener);
        },
      };
    }
    throw new Error(`Unexpected module in app alert service: ${name}`);
  };

  const source = fs.readFileSync(path.join(root, 'services/appAlert.ts'), 'utf8');
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: false },
  }).outputText;
  vm.runInNewContext(javascript, sandbox, { filename: 'appAlert.ts' });
  const exported = Object.keys(sandbox.module.exports).length
    ? sandbox.module.exports
    : sandbox.exports;

  return {
    module: exported,
    setLock(patch) {
      Object.assign(lock, patch);
      lockListeners.forEach((listener) => listener());
    },
    setAuthenticated(value) {
      authenticated = value;
      sessionListeners.forEach((listener) => listener());
    },
  };
}

function methodsCalling(relativePath, callee) {
  const tree = ts.createSourceFile(
    relativePath,
    fs.readFileSync(path.join(root, relativePath), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const owners = [];
  function visit(node) {
    if (ts.isMethodDeclaration(node) && ts.isIdentifier(node.name) && node.body) {
      let calls = 0;
      function scan(child) {
        if (ts.isCallExpression(child) && ts.isIdentifier(child.expression) &&
            child.expression.text === callee) {
          calls += 1;
        }
        ts.forEachChild(child, scan);
      }
      scan(node.body);
      if (calls > 0) owners.push([node.name.text, calls]);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return owners;
}

function assertLockViewVisible(state) {
  assert.ok(
    !state.ready || state.locked || state.covered || state.error,
    'lock view must stay visible on failures',
  );
}

async function prepareUnlocked(harness, pin = PIN) {
  await harness.module.hydrateAppLock();
  await harness.module.enableAppLock(pin);
  if (harness.state().locked) {
    assert.equal(await harness.module.unlockWithPin(pin), true);
  }
  assert.equal(harness.state().locked, false);
}

async function lock(harness) {
  harness.module.handleAppLockState('background');
  harness.module.handleAppLockState('active');
  await flush();
  assert.equal(harness.state().locked, true);
}

function storedRecord(harness) {
  const raw = harness.store.data.get('finance.appLock.v1');
  return raw === undefined ? null : JSON.parse(raw);
}

async function preparePattern(harness, pattern = PATTERN, pin = PIN) {
  await prepareUnlocked(harness, pin);
  await harness.module.setAppLockPattern(pin, pattern);
  assert.equal(harness.state().patternEnabled, true);
  return storedRecord(harness);
}

test('enable accepts only exactly six ASCII digits', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();

  for (const invalid of [
    '',
    '12345',
    '1234567',
    'abcdef',
    '12345a',
    ' 123456',
    '123456 ',
    '123 456',
    '１２３４５６',
    '١٢٣٤٥٦',
  ]) {
    await expectRejects(harness.module.enableAppLock(invalid), invalid);
  }

  assert.equal(harness.state().enabled, false);
  assert.equal(harness.store.values().length, 0, 'invalid PINs must not be persisted');

  await harness.module.enableAppLock(PIN);
  assert.equal(harness.state().enabled, true);
});

test('setup stores a versioned SHA-256 verifier with a 256-bit random pepper and no plaintext PIN', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();
  await harness.module.enableAppLock(PIN);

  const stored = JSON.stringify(harness.store.values());
  assert.equal(stored.includes(PIN), false, 'PIN must never be stored or logged');
  assert.equal(harness.logs.flat().join(' ').includes(PIN), false);
  assert.ok(harness.store.values().length > 0);

  const record = JSON.parse(
    harness.store.data.get('finance.appLock.v1'),
  );
  assert.ok(record, 'lock state must be stored as a structured record');
  assert.ok('version' in record || 'v' in record, 'stored record must be versioned');

  assert.ok(harness.crypto.calls.random.includes(32), 'pepper must be 256 bits');
  assert.ok(
    harness.crypto.calls.digest.some((algorithm) => ['SHA-256', 'SHA256', 'sha256'].includes(algorithm)),
    'verifier must use SHA-256',
  );
});

test('enable waits for the durable write before reporting success', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();

  const release = harness.store.holdWrites();
  let resolved = false;
  const pending = harness.module.enableAppLock(PIN).then(() => {
    resolved = true;
  });

  await flush();
  assert.equal(resolved, false, 'enable must await SecureStore');
  assert.equal(harness.state().enabled, false, 'state must not flip before the write lands');
  assert.equal(harness.state().busy, true);

  release();
  await pending;
  assert.equal(harness.state().enabled, true);
  assert.equal(harness.state().busy, false);
});

test('enable fails closed when secure storage rejects the write', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();
  harness.store.fail.set = true;

  await expectRejects(harness.module.enableAppLock(PIN));
  assert.equal(harness.state().enabled, false);
  assertLockViewVisible(harness.state());

  harness.store.fail.set = false;
  const reloaded = reload(harness);
  await reloaded.module.hydrateAppLock();
  assert.equal(reloaded.state().enabled, false, 'a failed enable must not leave a lock configured');
});

test('cold start hydrates an enabled installation as locked', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();
  await harness.module.enableAppLock(PIN);

  const cold = reload(harness);
  assertLockViewVisible(cold.state());
  await cold.module.hydrateAppLock();

  const state = cold.state();
  assert.equal(state.ready, true);
  assert.equal(state.enabled, true);
  assert.equal(state.locked, true);
  assert.equal(state.biometricsEnabled, false);
  assert.equal(state.supported, true);
  assert.equal(state.error, null);

  assert.equal(await cold.module.unlockWithPin(PIN), true);
  assert.equal(cold.state().locked, false);
});

test('wrong PINs persist attempts and impose a 30 second cooldown after five errors, including reload', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  for (let attempt = 1; attempt <= 4; attempt += 1) {
    assert.equal(await harness.module.unlockWithPin('000000'), false);
    assert.equal(harness.state().failedAttempts, attempt);
    assert.ok(harness.state().retryAt <= harness.clock.now(), 'no cooldown before five errors');
  }

  assert.equal(await harness.module.unlockWithPin('000000'), false);
  assert.equal(harness.state().failedAttempts, 5);
  const retryAt = harness.state().retryAt;
  assert.ok(retryAt - harness.clock.now() >= 29000, 'cooldown must be about 30 seconds');
  assert.ok(retryAt - harness.clock.now() <= 31000, 'cooldown must be about 30 seconds');

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.ok(cold.state().failedAttempts >= 5, 'attempts must survive a restart');
  assert.ok(cold.state().retryAt > cold.clock.now(), 'cooldown must survive a restart');

  assert.equal(await cold.module.unlockWithPin(PIN), false, 'cooldown must reject the correct PIN');
  assert.equal(cold.state().locked, true);

  cold.clock.advance(cold.state().retryAt - cold.clock.now() + 1);
  assert.equal(await cold.module.unlockWithPin(PIN), true);
  assert.equal(cold.state().locked, false);
  assert.equal(cold.state().failedAttempts, 0);
});

test('failed attempts below the threshold survive reload without a cooldown', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  assert.equal(await harness.module.unlockWithPin('000000'), false);
  assert.equal(await harness.module.unlockWithPin('000001'), false);
  assert.equal(harness.state().failedAttempts, 2);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().failedAttempts, 2);
  assert.ok(cold.state().retryAt <= cold.clock.now());
  assert.equal(await cold.module.unlockWithPin(PIN), true);
});

test('a wrong unlock sets an error and a correct unlock clears it', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  assert.equal(await harness.module.unlockWithPin('000000'), false);
  assert.equal(typeof harness.state().error, 'string');
  assert.ok(harness.state().error.length > 0);

  assert.equal(await harness.module.unlockWithPin(PIN), true);
  assert.equal(harness.state().error, null);
  assert.equal(harness.state().locked, false);
  assert.equal(harness.state().covered, false);
});

test('changing, disabling, or enabling biometrics requires the current PIN', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  await expectRejects(harness.module.changeAppLockPin('000000', NEXT_PIN));
  await expectRejects(harness.module.disableAppLock('000000'));
  await expectRejects(harness.module.setAppLockBiometrics('000000', true));

  assert.equal(harness.state().enabled, true);
  assert.equal(harness.state().biometricsEnabled, false);
  assert.equal(typeof harness.state().error, 'string');

  await lock(harness);
  assert.equal(await harness.module.unlockWithPin(NEXT_PIN), false, 'failed mutation must not change the PIN');
  assert.equal(await harness.module.unlockWithPin(PIN), true);

  await harness.module.changeAppLockPin(PIN, NEXT_PIN);
  await lock(harness);
  assert.equal(await harness.module.unlockWithPin(PIN), false);
  assert.equal(await harness.module.unlockWithPin(NEXT_PIN), true);
});

test('disable removes the lock so the next cold start is open', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  await harness.module.disableAppLock(PIN);
  assert.equal(harness.state().enabled, false);
  assert.equal(harness.state().locked, false);
  assert.equal(harness.store.data.has('finance.appLock.v1'), false);
  assert.equal(harness.store.data.has('finance.appLock.pendingDisable.v1'), false);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, false);
  assert.equal(cold.state().locked, false);
  assert.equal(JSON.stringify(cold.store.values()).includes(PIN), false);
});

test('biometrics unlock only when opted in, with strong enrolled hardware and no device fallback', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  assert.equal(await harness.module.getBiometricAvailability(), true);
  assert.equal(await harness.module.unlockWithBiometrics(), false, 'opt-in is required');
  assert.equal(harness.localAuth.state.calls, 0, 'no prompt before opt-in');

  await harness.module.setAppLockBiometrics(PIN, true);
  assert.equal(harness.state().biometricsEnabled, true);
  harness.localAuth.state.calls = 0;

  await lock(harness);
  assert.equal(await harness.module.unlockWithBiometrics(), true);
  assert.equal(harness.state().locked, false);
  assert.equal(harness.localAuth.state.calls, 1);
  assert.equal(harness.localAuth.state.options.disableDeviceFallback, true);
  assert.equal(harness.localAuth.state.options.biometricsSecurityLevel, 'strong');
});

test('biometrics stay unavailable without strong enrollment and never prompt', async () => {
  const weak = createHarness({ localAuthConfig: { level: 2 } });
  await prepareUnlocked(weak);
  assert.equal(await weak.module.getBiometricAvailability(), false);
  await expectRejects(weak.module.setAppLockBiometrics(PIN, true));
  assert.equal(await weak.module.unlockWithBiometrics(), false);
  assert.equal(weak.localAuth.state.calls, 0);

  const missingHardware = createHarness({ localAuthConfig: { hardware: false, enrolled: false } });
  await prepareUnlocked(missingHardware);
  assert.equal(await missingHardware.module.getBiometricAvailability(), false);
  await expectRejects(missingHardware.module.setAppLockBiometrics(PIN, true));
});

test('biometric cancellation leaves the app locked and the PIN available', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await harness.module.setAppLockBiometrics(PIN, true);
  await lock(harness);
  harness.localAuth.state.result = { success: false, error: 'user_cancel' };

  assert.equal(await harness.module.unlockWithBiometrics(), false);
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());

  assert.equal(await harness.module.unlockWithPin(PIN), true);
});

test('a background transition rejects a biometric result that arrives later', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await harness.module.setAppLockBiometrics(PIN, true);
  await lock(harness);

  harness.localAuth.state.calls = 0;
  harness.localAuth.state.pending = deferred();
  const pending = harness.module.unlockWithBiometrics();
  for (let tick = 0; tick < 10 && harness.localAuth.state.calls === 0; tick += 1) {
    await flush();
  }
  assert.equal(harness.localAuth.state.calls, 1);

  harness.module.handleAppLockState('background');
  harness.localAuth.state.pending.resolve({ success: true });

  assert.equal(await pending, false, 'stale prompt result must not unlock');
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());
});

test('logout keeps the lock configured and re-locks the next authenticated session', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  harness.module.handleAppLockState('active');
  assert.equal(harness.state().locked, false);

  harness.module.setAppLockSession(false);
  await flush();
  const loggedOut = harness.state();
  assert.equal(loggedOut.enabled, true, 'lock preferences may remain after logout');
  assert.equal(loggedOut.biometricsEnabled, false);

  // The session flag is false here, so protected screens render nothing. A
  // restored session must come back locked instead of reusing the old unlock.
  harness.module.setAppLockSession(true);
  await flush();
  assert.equal(harness.state().enabled, true);
  assert.equal(harness.state().locked, true, 'a restored token session must re-lock');
  assertLockViewVisible(harness.state());
});

test('a session change invalidates an in-flight biometric result', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await harness.module.setAppLockBiometrics(PIN, true);
  await lock(harness);

  harness.localAuth.state.calls = 0;
  harness.localAuth.state.pending = deferred();
  const pending = harness.module.unlockWithBiometrics();
  for (let tick = 0; tick < 10 && harness.localAuth.state.calls === 0; tick += 1) {
    await flush();
  }
  assert.equal(harness.localAuth.state.calls, 1);

  harness.module.setAppLockSession(false);
  harness.module.setAppLockSession(true);
  harness.localAuth.state.pending.resolve({ success: true });

  assert.equal(await pending, false);
  assert.equal(harness.state().locked, true);
});

test('fresh sign-in reset clears the lock durably, while a session reassert does not', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  harness.module.setAppLockSession(true);
  assert.equal(harness.state().enabled, true, 'token refresh must not clear lock preferences');

  const previous = harness.store.data.get('finance.appLock.v1');
  const refreshed = reload(harness);
  await refreshed.module.hydrateAppLock();
  assert.equal(refreshed.state().enabled, true, 'token refresh must not clear the stored lock');
  assert.equal(refreshed.state().locked, true);

  refreshed.store.data.set('finance.appLock.pendingDisable.v1', previous);
  await refreshed.module.resetAppLockAfterSignIn();
  assert.equal(refreshed.state().enabled, false);
  assert.equal(refreshed.state().locked, false);
  assert.equal(refreshed.store.data.has('finance.appLock.v1'), false);
  assert.equal(refreshed.store.data.has('finance.appLock.pendingDisable.v1'), false);

  const afterSignIn = reload(refreshed);
  await afterSignIn.module.hydrateAppLock();
  assert.equal(afterSignIn.state().enabled, false);
  assert.equal(await afterSignIn.module.unlockWithBiometrics(), false);
});

test('a failed fresh-sign-in reset aborts and keeps the old lock', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  harness.store.fail.delete = true;

  await expectRejects(harness.module.resetAppLockAfterSignIn());
  assert.equal(harness.state().enabled, true);
  assert.equal(harness.state().locked, true);

  harness.store.fail.delete = false;
  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true, 'an aborted reset must not silently open the app');
});

test('malformed stored records fail closed', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  for (const [key] of harness.store.values()) {
    if (key === 'finance.appLock.v1') {
      harness.store.data.set(key, '{"not":"a valid lock record"');
    }
  }

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  const state = cold.state();
  assertLockViewVisible(state);
  assert.equal(state.locked || state.covered || state.error !== null, true);
  assert.equal(state.locked === false && state.enabled === true && state.error === null, false);

  assert.notEqual(await cold.module.unlockWithPin(PIN), true);
  assertLockViewVisible(cold.state());
});

test('a SecureStore read failure on boot fails closed and can be retried', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  harness.store.fail.get = true;

  const cold = reload(harness);
  const hydrated = await settle(cold.module.hydrateAppLock());
  const state = cold.state();
  assertLockViewVisible(state);
  assert.equal(state.error !== null || hydrated.ok === false, true);
  assert.equal(state.locked === false && state.enabled === true, false);

  harness.store.fail.get = false;
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().error, null);
  assert.equal(cold.state().ready, true);
  assert.equal(cold.state().enabled, true, 'retry must read the persisted lock');
  assert.equal(cold.state().locked, true);
});

test('a storage failure while recording a wrong PIN stays locked', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);
  harness.store.fail.set = true;

  const result = await settle(harness.module.unlockWithPin('000000'));
  assert.notEqual(result.ok && result.value === true, true);
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());

  harness.store.fail.set = false;
  await harness.module.hydrateAppLock();
  assert.equal(await harness.module.unlockWithPin(PIN), true);
});

test('missing native modules fail clearly instead of crashing the service', async () => {
  const noCrypto = createHarness({ missing: 'crypto' });
  await noCrypto.module.hydrateAppLock();
  const cryptoEnable = await settle(noCrypto.module.enableAppLock(PIN));
  assert.equal(cryptoEnable.ok, false);
  assert.ok(cryptoEnable.error && cryptoEnable.error.message.length > 0);
  assert.equal(noCrypto.state().enabled, false);
  assert.equal(noCrypto.store.values().length, 0, 'PIN setup must fail before writing');

  const noAuth = createHarness({ missing: 'local-auth' });
  await prepareUnlocked(noAuth);
  assert.equal(await noAuth.module.getBiometricAvailability(), false);
  await expectRejects(noAuth.module.setAppLockBiometrics(PIN, true));
  assert.equal(noAuth.state().biometricsEnabled, false);
});

test('state snapshots are immutable and subscriptions detach cleanly', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();

  let notifications = 0;
  const unsubscribe = harness.module.subscribeAppLock(() => {
    notifications += 1;
  });

  const before = harness.state();
  await harness.module.enableAppLock(PIN);
  const after = harness.state();
  assert.ok(notifications >= 1);
  assert.notEqual(before, after, 'each update must publish a fresh snapshot');

  const copy = { ...after };
  copy.ready = false;
  copy.busy = true;
  assert.equal(harness.state().ready, after.ready, 'mutating a copy must not corrupt state');
  assert.equal(harness.state().busy, false);

  unsubscribe();
  const count = notifications;
  harness.module.handleAppLockState('background');
  await flush();
  assert.equal(notifications, count, 'unsubscribed listeners must not be called');
});

test('unknown lifecycle events do not unlock a locked app', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  harness.module.handleAppLockState('unknown-future-state');
  harness.module.handleAppLockState('inactive');
  await flush();
  assert.equal(harness.state().locked, true);
  assert.equal(harness.state().covered, true);

  harness.module.handleAppLockState('active');
  await flush();
  assert.equal(harness.state().covered, false);
  assert.equal(harness.state().locked, true, 'inactive must never unlock');
});
test('hydration that starts before the session flag still ends ready and locked', async () => {
  const installed = createHarness();
  await installed.module.hydrateAppLock();
  await installed.module.enableAppLock(PIN);

  const cold = createHarness({
    store: installed.store,
    clock: installed.clock,
    localAuth: installed.localAuth,
    authenticated: false,
  });
  const release = cold.store.holdReads();

  const hydrating = cold.module.hydrateAppLock();
  await flush();
  assert.equal(cold.state().ready, false, 'hydration is still waiting on SecureStore');

  cold.module.setAppLockSession(true);
  assert.equal(cold.state().locked, true);

  release();
  await hydrating;
  assert.equal(cold.state().ready, true, 'a stale hydrate ticket must not abandon the read');
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().locked, true);
});

test('a background transition rejects an in-flight PIN proof', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  const baseline = harness.crypto.calls.digest.length;
  const release = harness.crypto.holdDigest();
  const proof = harness.module.unlockWithPin(PIN);
  await waitFor(
    () => harness.crypto.calls.digest.length > baseline,
    'PIN digest did not start',
  );

  harness.module.handleAppLockState('background');
  release();

  assert.equal(await proof, false, 'a PIN proof finishing in the background must not unlock');
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());

  harness.module.handleAppLockState('active');
  assert.equal(await harness.module.unlockWithPin(PIN), true);
});

test('background during the enable write still leaves the new lock closed', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();

  const release = harness.store.holdWrites();
  const enabling = harness.module.enableAppLock(PIN);
  await flush();
  assert.equal(harness.state().enabled, false);

  harness.module.handleAppLockState('background');
  harness.module.handleAppLockState('active');
  release();
  await enabling;

  assert.equal(harness.state().enabled, true);
  assert.equal(harness.state().locked, true, 'a background transition during the write must keep it locked');
  assertLockViewVisible(harness.state());

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().locked, true);
});

test('the biometric prompt may survive inactive, but stays covered until active', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await harness.module.setAppLockBiometrics(PIN, true);
  await lock(harness);

  harness.localAuth.state.calls = 0;
  harness.localAuth.state.pending = deferred();
  const proof = harness.module.unlockWithBiometrics();
  await waitFor(
    () => harness.localAuth.state.calls === 1,
    'native biometric prompt did not start',
  );

  harness.module.handleAppLockState('inactive');
  assert.equal(harness.state().covered, true);
  assert.equal(harness.state().locked, true);

  harness.localAuth.state.pending.resolve({ success: true });
  assert.equal(await proof, true, 'inactive must not invalidate its own prompt');
  assert.equal(harness.state().locked, false);
  assert.equal(harness.state().covered, true, 'content stays covered until active');

  harness.module.handleAppLockState('active');
  assert.equal(harness.state().covered, false);
  assert.equal(harness.state().locked, false);
});

test('concurrent unlock attempts are single flight', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  await lock(harness);

  const baseline = harness.crypto.calls.digest.length;
  const release = harness.crypto.holdDigest();
  const first = harness.module.unlockWithPin(PIN);
  await waitFor(
    () => harness.crypto.calls.digest.length > baseline,
    'first unlock did not start',
  );

  assert.equal(await harness.module.unlockWithPin(PIN), false, 'second unlock must not race the first');
  assert.equal(harness.crypto.calls.digest.length, baseline + 1);

  release();
  assert.equal(await first, true);
  assert.equal(harness.state().locked, false);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().locked, true, 'the next cold start must lock again after an unlock');
});

test('web is unsupported and never reads, writes, or enables the lock', async () => {
  const harness = createHarness({ os: 'web' });
  assert.equal(harness.state().supported, false);

  await harness.module.hydrateAppLock();
  assert.equal(harness.state().ready, true);
  assert.equal(harness.state().enabled, false);
  assert.equal(harness.state().locked, false);
  assert.equal(harness.store.calls.get, 0, 'web must not touch SecureStore');

  await expectRejects(harness.module.enableAppLock(PIN));
  assert.equal(harness.state().enabled, false);
  assert.equal(await harness.module.getBiometricAvailability(), false);
  assert.equal(await harness.module.unlockWithBiometrics(), false);
  assert.equal(harness.store.calls.set, 0);
  assert.equal(harness.store.calls.delete, 0);
});

test('fresh sign-in reset is wired only to register, login, and Google login', () => {
  const owners = Object.fromEntries(methodsCalling('services/auth.ts', 'resetAppLockAfterSignIn'));
  assert.deepEqual(owners, { register: 1, login: 1, googleLogin: 1 });
  assert.equal('changePassword' in owners, false, 'password change must keep the device lock');

  const authSource = fs.readFileSync(path.join(root, 'services/auth.ts'), 'utf8');
  assert.match(authSource, /import \{ resetAppLockAfterSignIn \} from '\.\/appLock';/);

  const apiSource = fs.readFileSync(path.join(root, 'services/api.ts'), 'utf8');
  assert.doesNotMatch(apiSource, /resetAppLock/);
  assert.doesNotMatch(apiSource, /from ['"]\.\/appLock['"]/);
});

test('root lock cover gates auth, touches, accessibility, and Android back', () => {
  const source = fs.readFileSync(path.join(root, 'app/_layout.tsx'), 'utf8');

  assert.match(
    source,
    /const gated = authed && \(!appLock\.ready \|\| appLock\.locked \|\| appLock\.covered\)/,
  );
  assert.match(source, /pointerEvents=\{gated \? 'none' : 'auto'\}/);
  assert.match(source, /accessibilityElementsHidden=\{gated\}/);
  assert.match(source, /importantForAccessibility=\{gated \? 'no-hide-descendants' : 'auto'\}/);
  assert.match(source, /if \(!gated\) return;/);
  assert.match(source, /BackHandler\.addEventListener\('hardwareBackPress', \(\) => true\)/);
  assert.match(source, /\{gated \? \(?\s*<View style=\{styles\.lockCover\} accessibilityViewIsModal>/);
  assert.match(source, /<AppLockView onSignOut=/);
  assert.match(source, /<AppAlertHost host="root" \/>/);
  assert.match(source, /lockCover: \{ \.\.\.StyleSheet\.absoluteFill, zIndex: 100/);
  assert.doesNotMatch(source, /<Modal\b/, 'root must use an absolute View, not a nested native Modal');

  const stackAt = source.indexOf('<Stack');
  const coverAt = source.indexOf('style={styles.lockCover}');
  assert.ok(stackAt >= 0 && coverAt > stackAt, 'the cover must render above the navigator');
  assert.doesNotMatch(source, /router\.(push|replace)\('\/app-lock'\)/);
});

test('sheet modals independently gate their contents with the same lock cover', () => {
  const source = fs.readFileSync(path.join(root, 'components/ui/Sheet.tsx'), 'utf8');

  assert.match(
    source,
    /const gated = authenticated && \(!lock\.ready \|\| lock\.locked \|\| lock\.covered\)/,
  );
  assert.match(source, /onRequestClose=\{\(\) => \{ if \(!gated\) onClose\(\); \}\}/);
  assert.match(source, /pointerEvents=\{gated \? 'none' : 'auto'\}/);
  assert.match(source, /accessibilityElementsHidden=\{gated\}/);
  assert.match(source, /importantForAccessibility=\{gated \? 'no-hide-descendants' : 'auto'\}/);
  assert.match(source, /\{gated \? \(?\s*<View style=\{styles\.lockCover\} accessibilityViewIsModal>/);
  assert.match(source, /<AppLockView onSignOut=\{clearSession\}/);
  assert.match(source, /<AppAlertHost host=\{host\} active=\{visible\} \/>/);
});

test('storageError drives the boot retry UI regardless of the enabled flag', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();
  assert.equal(harness.state().storageError, false);

  harness.store.fail.set = true;
  await expectRejects(harness.module.enableAppLock(PIN));
  assert.equal(harness.state().storageError, true);
  assert.equal(harness.state().enabled, false);
  assertLockViewVisible(harness.state());

  harness.store.fail.set = false;
  await harness.module.hydrateAppLock();
  assert.equal(harness.state().storageError, false);
  assert.equal(harness.state().ready, true);

  const view = fs.readFileSync(path.join(root, 'components/security/AppLockView.tsx'), 'utf8');
  assert.match(
    view,
    /const isBootOrDisabledError = lockState\.storageError \|\| \(!lockState\.enabled && Boolean\(lockState\.error\)\);/,
  );
  assert.match(view, /hydrateAppLock\(\)/);
});

test('background during a pending disable rejects and restores the previous record', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  const release = harness.store.holdDeletes();
  const disabling = harness.module.disableAppLock(PIN);
  await waitFor(() => harness.store.calls.delete > 0, 'disable delete did not start');

  harness.module.handleAppLockState('background');
  release();

  const result = await settle(disabling);
  assert.equal(result.ok, false, 'a cancelled setting change must reject');
  assert.equal(harness.state().enabled, true, 'the previous record must be restored');
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());
  assert.equal(harness.store.data.has('finance.appLock.v1'), true);
  assert.equal(
    harness.store.data.has('finance.appLock.pendingDisable.v1'),
    false,
    'a successful rollback must delete the pending marker',
  );

  harness.module.handleAppLockState('active');
  assert.equal(await harness.module.unlockWithPin(PIN), true);
  await harness.module.changeAppLockPin(PIN, NEXT_PIN);
  await lock(harness);
  assert.equal(await harness.module.unlockWithPin(PIN), false);
  assert.equal(await harness.module.unlockWithPin(NEXT_PIN), true);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().locked, true);
  assert.equal(cold.store.data.has('finance.appLock.v1'), true);
  assert.equal(cold.store.data.has('finance.appLock.pendingDisable.v1'), false);
  assert.equal(await cold.module.unlockWithPin(PIN), false, 'the old verifier must not come back');
  assert.equal(await cold.module.unlockWithPin(NEXT_PIN), true);
});

test('pending disable with a failed rollback write recovers the lock on cold hydrate', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  const release = harness.store.holdDeletes();
  const disabling = harness.module.disableAppLock(PIN);
  await waitFor(() => harness.store.calls.delete > 0, 'disable delete did not start');

  harness.module.handleAppLockState('background');
  harness.store.fail.set = true;
  release();

  const result = await settle(disabling);
  assert.equal(result.ok, false, 'the failed rollback must reject');
  assert.equal(harness.state().locked, true);
  assert.equal(harness.state().storageError, true);
  assert.equal(harness.store.data.has('finance.appLock.v1'), false);
  assert.equal(harness.store.data.has('finance.appLock.pendingDisable.v1'), true);

  harness.store.fail.set = false;
  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true, 'the pending record must restore the lock, not open the app');
  assert.equal(cold.state().locked, true);
  assert.equal(cold.state().storageError, false);
  assert.equal(cold.store.data.has('finance.appLock.v1'), true);
  assert.equal(cold.store.data.has('finance.appLock.pendingDisable.v1'), false);
});

test('a delayed token write cannot resurrect tokens after clearSession', async () => {
  const store = createSecureStore();
  const session = loadSessionModule({ store });
  const release = store.holdWrites();

  const saving = session.module.saveSession({
    access_token: 'stale-access',
    refresh_token: 'stale-refresh',
  });
  await waitFor(() => store.calls.set > 0, 'save write did not start');

  const clearing = session.module.clearSession();
  await flush();
  assert.equal(session.module.isAuthenticated(), false);

  release();
  await Promise.all([saving, clearing]);

  assert.equal(store.calls.set, 1, 'the stale save must stop after its first write');
  assert.equal(store.data.size, 0);

  await session.module.hydrateSession();
  assert.equal(session.module.getAccessToken(), null);
  assert.equal(session.module.getRefreshToken(), null);

  const cold = loadSessionModule({ store });
  await cold.module.hydrateSession();
  assert.equal(cold.module.getAccessToken(), null, 'a fresh hydrate must not restore deleted tokens');
  assert.equal(cold.module.getRefreshToken(), null);
});

test('clearSession invalidates app-lock proofs before native token deletion finishes', async () => {
  const store = createSecureStore();
  const session = loadSessionModule({ store });
  await session.module.saveSession({ access_token: 'access', refresh_token: 'refresh' });
  assert.equal(session.module.isAuthenticated(), true);
  assert.equal(session.appLockCalls.at(-1), true);

  let notified = 0;
  session.module.subscribeSession(() => {
    notified += 1;
  });

  const release = store.holdWrites();
  const clearing = session.module.clearSession();
  await flush();

  assert.equal(session.module.isAuthenticated(), false);
  assert.equal(notified, 1, 'subscribers must be notified before native I/O');
  assert.equal(session.appLockCalls.at(-1), false, 'lock proofs must be invalidated immediately');
  assert.equal(store.data.has('finance.accessToken'), true, 'native delete is still pending');
  assert.equal(store.data.has('finance.refreshToken'), true);

  release();
  await clearing;
  assert.equal(store.data.size, 0);
});

test('app alert clears and cannot fire its callback when the lock covers the app', () => {
  const alert = loadAlertModule();
  let pressed = 0;

  alert.module.AppAlert.alert('Hapus transaksi?', 'Tindakan ini tidak bisa dibatalkan.', [
    { text: 'Hapus', onPress: () => { pressed += 1; } },
  ]);
  assert.ok(alert.module.getAppAlert());

  alert.setLock({ covered: true });
  assert.equal(alert.module.getAppAlert(), null, 'a cover transition must clear the dialog');
  alert.module.pressAppAlert(0);
  assert.equal(pressed, 0, 'the stale callback must not fire');

  alert.setLock({ covered: false });
  alert.module.AppAlert.alert('Hapus', 'Lagi');
  alert.setAuthenticated(false);
  assert.equal(alert.module.getAppAlert(), null, 'logout must clear the dialog');
  alert.module.pressAppAlert(0);
  assert.equal(pressed, 0);
});

test('disabled app lock still allows dialogs for an authenticated active session', () => {
  const alert = loadAlertModule();
  alert.setLock({ enabled: false, ready: true, locked: false, covered: false });
  let pressed = 0;

  alert.module.AppAlert.alert('Tersimpan', 'Transaksi berhasil dicatat.', [
    { text: 'OK', onPress: () => { pressed += 1; } },
  ]);
  assert.ok(alert.module.getAppAlert());
  alert.module.pressAppAlert(0);
  assert.equal(pressed, 1);
  assert.equal(alert.module.getAppAlert(), null);
});

test('unregistering the alert host invalidates its dialog and callback', () => {
  const alert = loadAlertModule();
  let pressed = 0;
  const unregister = alert.module.registerAppAlertHost('sheet');

  alert.module.AppAlert.alert('Hapus', 'Data', [
    { text: 'Hapus', onPress: () => { pressed += 1; } },
  ]);
  assert.equal(alert.module.getAppAlert().host, 'sheet');

  unregister();
  assert.equal(alert.module.getAppAlert(), null, 'host cleanup must invalidate its dialog');
  alert.module.pressAppAlert(0);
  assert.equal(pressed, 0);
});

test('pattern setup requires the current PIN and rejects malformed or noncanonical patterns', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  await expectRejects(harness.module.setAppLockPattern('000000', PATTERN));
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);

  const invalid = [
    [],
    [0, 1, 2],
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 0],
    [0, 1, 2, 2],
    [4, 4, 5, 6],
    [0, 2, 5, 8],
    [0, 1, 2, 9],
    [0, 1, 2, -1],
    [0, 1, 2, 1.5],
    [0, 1, 2, NaN],
  ];
  for (const pattern of invalid) {
    await expectRejects(
      harness.module.setAppLockPattern(PIN, pattern),
      `pattern ${String(pattern)} must be rejected`,
    );
  }
  await expectRejects(harness.module.setAppLockPattern(PIN, undefined));

  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);

  await harness.module.setAppLockPattern(PIN, PATTERN);
  assert.equal(harness.state().patternEnabled, true);
  const record = storedRecord(harness);
  assert.ok(record.pattern, 'a valid pattern must be persisted');
  assert.equal(Object.keys(record.pattern).sort().join(','), 'secret,verifier');
});

test('a valid pattern stores an independent 256-bit secret and hashed verifier with no plaintext nodes', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  const randomBefore = harness.crypto.calls.random.filter((size) => size === 32).length;

  await harness.module.setAppLockPattern(PIN, PATTERN);
  assert.equal(harness.state().patternEnabled, true);
  const record = storedRecord(harness);

  assert.match(record.pattern.secret, /^[0-9a-f]{64}$/);
  assert.match(record.pattern.verifier, /^[0-9a-f]{64}$/);
  assert.notEqual(record.pattern.secret, record.secret, 'pattern must use its own random secret');
  assert.notEqual(record.pattern.verifier, record.verifier);
  assert.equal(
    harness.crypto.calls.random.filter((size) => size === 32).length,
    randomBefore + 1,
    'pattern setup must draw a fresh 256-bit secret',
  );
  assert.deepEqual(Object.keys(record.pattern).sort(), ['secret', 'verifier']);
  assert.equal(
    JSON.stringify(record.pattern).includes(JSON.stringify(PATTERN)),
    false,
    'plain pattern nodes must never be persisted',
  );

  const source = fs.readFileSync(SERVICE_PATH, 'utf8');
  assert.match(source, /finance\.appLock\.pattern\.v1/, 'pattern hashing needs its own domain');
  assert.ok(
    harness.crypto.calls.digestData.includes(
      `finance.appLock.pattern.v1:${record.pattern.secret}:${PATTERN.join('')}`,
    ),
    'pattern verifier must hash the exact domain-separated canonical pattern',
  );
});

test('cold start hydrates patternEnabled and unlocks with the canonical pattern', async () => {
  const harness = createHarness();
  await preparePattern(harness);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().ready, true);
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().patternEnabled, true);
  assert.equal(cold.state().locked, true);

  assert.equal(await cold.module.unlockWithPattern(PATTERN), true);
  assert.equal(cold.state().locked, false);
  assert.equal(cold.state().error, null);

  const nextCold = reload(cold);
  await nextCold.module.hydrateAppLock();
  assert.equal(nextCold.state().locked, true, 'pattern unlock must not persist an open gate');
});

test('wrong pattern attempts share the PIN five-error cooldown, including after restart', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);

  assert.equal(await harness.module.unlockWithPin('000000'), false);
  assert.equal(harness.state().failedAttempts, 1);
  assert.equal(await harness.module.unlockWithPin('000001'), false);
  assert.equal(harness.state().failedAttempts, 2);

  assert.equal(await harness.module.unlockWithPattern(WRONG_PATTERN), false);
  assert.equal(harness.state().failedAttempts, 3);
  assert.equal(await harness.module.unlockWithPattern([7, 6, 3, 0]), false);
  assert.equal(harness.state().failedAttempts, 4);
  assert.equal(await harness.module.unlockWithPattern([8, 7, 6, 3]), false);
  assert.equal(harness.state().failedAttempts, 5);

  const retryAt = harness.state().retryAt;
  assert.ok(retryAt - harness.clock.now() >= 29000, 'pattern errors must trigger the 30 second cooldown');
  assert.ok(retryAt - harness.clock.now() <= 31000);

  assert.equal(await harness.module.unlockWithPattern(PATTERN), false);
  assert.equal(await harness.module.unlockWithPin(PIN), false);
  assert.equal(harness.state().locked, true);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.ok(cold.state().failedAttempts >= 5);
  assert.ok(cold.state().retryAt > cold.clock.now());
  assert.equal(await cold.module.unlockWithPattern(PATTERN), false);

  cold.clock.advance(cold.state().retryAt - cold.clock.now() + 1);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), true);
  assert.equal(cold.state().locked, false);
  assert.equal(cold.state().failedAttempts, 0);
});

test('a wrong pattern keeps the gate closed while a correct pattern clears the error', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);

  assert.equal(await harness.module.unlockWithPattern(WRONG_PATTERN), false);
  assert.equal(harness.state().locked, true);
  assert.equal(typeof harness.state().error, 'string');
  assert.ok(harness.state().error.length > 0);

  assert.equal(await harness.module.unlockWithPattern([0, 2, 5, 8]), false, 'noncanonical patterns must fail');
  assert.equal(harness.state().locked, true);

  assert.equal(await harness.module.unlockWithPattern(PATTERN), true);
  assert.equal(harness.state().locked, false);
  assert.equal(harness.state().error, null);
  assert.equal(harness.state().failedAttempts, 0);
});

test('unlockWithPattern fails safely for malformed runtime patterns', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);

  for (const value of [null, undefined, [], [0, 1, 2], [0, 1, 2, 9], [0, 2, 5, 8], '0125']) {
    assert.equal(
      await harness.module.unlockWithPattern(value),
      false,
      `malformed pattern ${String(value)} must not unlock`,
    );
    assert.equal(harness.state().locked, true);
  }

  assert.equal(await harness.module.unlockWithPattern(PATTERN), true);
});

test('removing the pattern requires the current PIN and leaves PIN unlock intact', async () => {
  const harness = createHarness();
  await preparePattern(harness);

  await expectRejects(harness.module.setAppLockPattern('000000', null));
  assert.equal(harness.state().patternEnabled, true);
  assert.ok(storedRecord(harness).pattern);

  await harness.module.setAppLockPattern(PIN, null);
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);

  await lock(harness);
  assert.equal(await harness.module.unlockWithPattern(PATTERN), false);
  assert.equal(await harness.module.unlockWithPin(PIN), true);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().patternEnabled, false);
  assert.equal(cold.state().locked, true);
  assert.equal(await cold.module.unlockWithPin(PIN), true);
});

test('changing the PIN preserves the pattern verifier and its independent secret', async () => {
  const harness = createHarness();
  const before = await preparePattern(harness);
  const patternBefore = { ...before.pattern };

  await harness.module.changeAppLockPin(PIN, NEXT_PIN);

  const after = storedRecord(harness);
  assert.equal(harness.state().patternEnabled, true);
  assert.deepEqual(after.pattern, patternBefore, 'PIN changes must not rotate the pattern secret');

  await lock(harness);
  assert.equal(await harness.module.unlockWithPattern(PATTERN), true);

  await lock(harness);
  assert.equal(await harness.module.unlockWithPin(PIN), false);
  assert.equal(await harness.module.unlockWithPin(NEXT_PIN), true);
});

test('a legacy PIN-only record hydrates without a pattern and keeps pattern unlock disabled', async () => {
  const harness = createHarness();
  await harness.module.hydrateAppLock();
  await harness.module.enableAppLock(PIN);
  assert.equal(storedRecord(harness).pattern, undefined);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().patternEnabled, false);
  assert.equal(cold.state().locked, true);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), false);
  assert.equal(cold.state().locked, true);
  assert.equal(await cold.module.unlockWithPin(PIN), true);
});

test('a corrupt stored pattern blocks hydration instead of silently dropping it', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  const valid = storedRecord(harness);

  const corrupt = [
    { secret: 'a'.repeat(64) },
    { verifier: 'b'.repeat(64) },
    { secret: 'g'.repeat(64), verifier: 'b'.repeat(64) },
    { secret: 'a'.repeat(64), verifier: 'b'.repeat(63) },
    { secret: 1, verifier: 2 },
    'not-an-object',
  ];

  for (const pattern of corrupt) {
    harness.store.data.set(
      'finance.appLock.v1',
      JSON.stringify({ ...valid, pattern }),
    );
    const cold = reload(harness);
    await cold.module.hydrateAppLock();
    const state = cold.state();
    assertLockViewVisible(state);
    assert.equal(state.locked, true, 'corrupt pattern must keep the gate closed');
    assert.equal(state.patternEnabled, false);
    assert.equal(state.storageError, true);
    assert.equal(await cold.module.unlockWithPattern(PATTERN), false);
    assert.equal(await cold.module.unlockWithPin(PIN), false);
  }

  harness.store.data.set('finance.appLock.v1', JSON.stringify(valid));
  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().patternEnabled, true);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), true);
});

test('a background transition rejects an in-flight pattern proof', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);

  const baseline = harness.crypto.calls.digest.length;
  const release = harness.crypto.holdDigest();
  const proof = harness.module.unlockWithPattern(PATTERN);
  await waitFor(
    () => harness.crypto.calls.digest.length > baseline,
    'pattern digest did not start',
  );

  harness.module.handleAppLockState('background');
  release();

  assert.equal(await proof, false, 'a pattern proof finishing in the background must not unlock');
  assert.equal(harness.state().locked, true);
  assertLockViewVisible(harness.state());

  harness.module.handleAppLockState('active');
  assert.equal(await harness.module.unlockWithPattern(PATTERN), true);
});

test('a session change invalidates an in-flight pattern proof', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);

  const baseline = harness.crypto.calls.digest.length;
  const release = harness.crypto.holdDigest();
  const proof = harness.module.unlockWithPattern(PATTERN);
  await waitFor(
    () => harness.crypto.calls.digest.length > baseline,
    'pattern digest did not start',
  );

  harness.module.setAppLockSession(false);
  harness.module.setAppLockSession(true);
  release();

  assert.equal(await proof, false);
  assert.equal(harness.state().locked, true);
  assert.equal(await harness.module.unlockWithPattern(PATTERN), true);
});

test('a stale pattern setup proof is rejected before anything is persisted', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  const baseline = harness.crypto.calls.digest.length;
  const release = harness.crypto.holdDigest();
  const setting = harness.module.setAppLockPattern(PIN, PATTERN);
  await waitFor(
    () => harness.crypto.calls.digest.length > baseline,
    'PIN reauthentication digest did not start',
  );

  harness.module.handleAppLockState('background');
  release();

  await expectRejects(setting);
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);
  assert.equal(harness.state().locked, true);

  harness.module.handleAppLockState('active');
  assert.equal(await harness.module.unlockWithPin(PIN), true);
});

test('pattern setup reports success only after the durable write lands', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  const release = harness.store.holdWrites();
  let resolved = false;
  const pending = harness.module.setAppLockPattern(PIN, PATTERN).then(() => {
    resolved = true;
  });
  await flush();

  assert.equal(resolved, false, 'setup must await SecureStore');
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);

  release();
  await pending;
  assert.equal(harness.state().patternEnabled, true);
  assert.ok(storedRecord(harness).pattern);
});

test('a failed pattern write rejects and keeps the previous pattern state', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);
  harness.store.fail.set = true;

  await expectRejects(harness.module.setAppLockPattern(PIN, PATTERN));
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(storedRecord(harness).pattern, undefined);
  assertLockViewVisible(harness.state());

  harness.store.fail.set = false;
  await harness.module.hydrateAppLock();
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(await harness.module.unlockWithPin(PIN), true);
  await harness.module.setAppLockPattern(PIN, PATTERN);
  assert.equal(harness.state().patternEnabled, true);
});

test('a failed durable write during pattern unlock never opens the gate', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  await lock(harness);
  harness.store.fail.set = true;

  const result = await settle(harness.module.unlockWithPattern(PATTERN));
  assert.notEqual(result.ok && result.value === true, true);
  assert.equal(harness.state().locked, true);
  assert.equal(harness.state().storageError, true);
  assertLockViewVisible(harness.state());

  harness.store.fail.set = false;
  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().locked, true);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), true);
});

test('disabling the lock also removes a configured pattern', async () => {
  const harness = createHarness();
  await preparePattern(harness);

  await harness.module.disableAppLock(PIN);
  assert.equal(harness.state().enabled, false);
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(harness.store.data.has('finance.appLock.v1'), false);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, false);
  assert.equal(cold.state().patternEnabled, false);
  assert.equal(cold.state().locked, false);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), false);
});

test('fresh sign-in reset clears the pattern durably', async () => {
  const harness = createHarness();
  await preparePattern(harness);

  await harness.module.resetAppLockAfterSignIn();
  assert.equal(harness.state().enabled, false);
  assert.equal(harness.state().patternEnabled, false);
  assert.equal(harness.store.data.has('finance.appLock.v1'), false);

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, false);
  assert.equal(cold.state().patternEnabled, false);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), false);
});

test('an interrupted disable restores the pattern from the pending record', async () => {
  const harness = createHarness();
  await preparePattern(harness);
  const record = storedRecord(harness);

  harness.store.data.set('finance.appLock.pendingDisable.v1', JSON.stringify(record));
  harness.store.data.delete('finance.appLock.v1');

  const cold = reload(harness);
  await cold.module.hydrateAppLock();
  assert.equal(cold.state().enabled, true);
  assert.equal(cold.state().patternEnabled, true);
  assert.equal(cold.state().locked, true);
  assert.equal(await cold.module.unlockWithPattern(PATTERN), true);
  assert.equal(harness.store.data.has('finance.appLock.pendingDisable.v1'), false);
});

test('pattern settings require and confirm the pattern twice, then clear transient input on privacy transitions', () => {
  const source = fs.readFileSync(path.join(root, 'app/app-lock.tsx'), 'utf8');

  assert.match(
    source,
    /const \[confirmPattern, setConfirmPattern\] = useState<number\[\]>\(\[\]\);/,
    'setup must collect a second pattern entry for confirmation',
  );
  assert.match(source, /patternsMatch\(nextCandidate, confirmCandidate\)/);
  assert.match(source, /setAppLockPattern\(currCandidate, nextCandidate\)/);
  assert.match(source, /setNewPattern\(\[\]\);[\s\S]*setConfirmPattern\(\[\]\);/);
  assert.match(source, /useFocusEffect\([\s\S]*clearAllPinFields\(\)/);
  assert.match(source, /AppState\.addEventListener\('change'[\s\S]*clearAllPinFields\(\)/);
  assert.doesNotMatch(source, /setAppLockPattern\([^)]*newPatternRef\.current\)/);
});

test('the unlock view defaults to PIN, offers a pattern fallback, and clears transient pattern input', () => {
  const view = fs.readFileSync(path.join(root, 'components/security/AppLockView.tsx'), 'utf8');
  const input = fs.readFileSync(path.join(root, 'components/security/PatternInput.tsx'), 'utf8');

  assert.match(view, /useState<UnlockMethod>\('pin'\)/, 'PIN must remain the default unlock method');
  assert.match(view, /unlockWithPattern\(candidate\)/);
  assert.match(view, /'Gunakan pola kunci'/);
  assert.match(view, /'Gunakan PIN 6 digit'/);
  assert.match(view, /patternRef\.current = \[\];[\s\S]*setPattern\(\[\]\);/);
  assert.match(view, /AppState\.addEventListener\('change'[\s\S]*setPattern\(\[\]\)/);

  assert.match(input, /accessibilityRole="button"/);
  assert.match(input, /Mode ketuk titik berurutan/);
  assert.match(input, /Hapus pola/);
  assert.match(input, /const handleClear = useCallback/);
  assert.doesNotMatch(input, /onSubmit|onComplete|autoSubmit/i, 'the grid must not auto-submit');
});

test('pattern setup snapshots the caller input before the first await', async () => {
  const harness = createHarness();
  await prepareUnlocked(harness);

  const input = [...PATTERN];
  const setting = harness.module.setAppLockPattern(PIN, input);
  input.length = 0;
  input.push(8, 8, 8, 8);

  await setting;
  assert.equal(harness.state().patternEnabled, true);

  await lock(harness);
  assert.equal(await harness.module.unlockWithPattern(PATTERN), true, 'the mutated UI array must not change the saved pattern');
});

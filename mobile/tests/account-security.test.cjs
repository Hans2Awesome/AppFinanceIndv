/** Dependency-free boundary tests for the security validation and auth interceptor. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

function loadModule(relativePath, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: false },
  }).outputText;
  const sandbox = { exports: {}, ...globals };
  vm.runInNewContext(javascript, sandbox);
  return sandbox.exports;
}

test('new passwords enforce character and UTF-8 byte limits', () => {
  const { validateNewPassword } = loadModule('utils/password.ts', { TextEncoder });
  assert.notEqual(validateNewPassword('short'), null);
  assert.equal(validateNewPassword('password123'), null);
  assert.equal(validateNewPassword('é'.repeat(36)), null);
  assert.notEqual(validateNewPassword('é'.repeat(37)), null);
});

test('password byte counting works without a native TextEncoder', () => {
  const { utf8ByteLength } = loadModule('utils/password.ts');
  assert.equal(utf8ByteLength('é'.repeat(36)), 72);
  assert.equal(utf8ByteLength('🔐'), 4);
});

async function checkRefresh(url, detail, shouldRefresh) {
  let rejectResponse;
  let refreshes = 0;
  const api = {
    interceptors: {
      request: { use() {} },
      response: { use(_success, failure) { rejectResponse = failure; } },
    },
    request: async () => ({ retried: true }),
  };
  const axios = {
    create: () => api,
    post: async () => {
      refreshes += 1;
      return { data: { access_token: 'replacement', refresh_token: 'replacement-refresh' } };
    },
  };
  const session = {
    getAccessToken: () => 'access',
    getRefreshToken: () => 'refresh',
    saveSession: async () => {},
    clearSession: async () => { throw new Error('Valid session must not be cleared'); },
  };
  loadModule('services/api.ts', {
    process: { env: { EXPO_PUBLIC_API_URL: 'https://example.invalid' } },
    require: (name) => name === 'axios' ? { default: axios } : session,
  });
  const failure = { config: { url }, response: { status: 401, data: { detail } } };
  if (shouldRefresh) {
    const result = await rejectResponse(failure);
    assert.equal(result.retried, true);
  } else {
    await assert.rejects(rejectResponse(failure), (error) => error === failure);
  }
  assert.equal(refreshes, shouldRefresh ? 1 : 0);
}

test('wrong current password does not refresh or retry a credential attempt', async () => {
  await checkRefresh('/api/auth/change-password', 'Current password is incorrect.', false);
});

test('wrong deletion password keeps the session and does not retry deletion', async () => {
  await checkRefresh('/api/auth/account', 'Password is incorrect.', false);
});

test('wrong Google proof does not refresh an otherwise valid app session', async () => {
  await checkRefresh('/api/auth/account', 'Google account does not match this account.', false);
});

test('expired access token on security endpoint still refreshes once', async () => {
  await checkRefresh('/api/auth/change-password', 'Token tidak valid atau sudah kedaluwarsa.', true);
});

test('ordinary authenticated requests retain automatic refresh', async () => {
  await checkRefresh('/api/transactions', 'unauthorized', true);
});

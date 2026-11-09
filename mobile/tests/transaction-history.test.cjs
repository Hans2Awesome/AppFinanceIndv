/** Dependency-free tests for transaction edit and history boundaries. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'utils/transactions.ts'), 'utf8');
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const sandbox = { exports: {} };
vm.runInNewContext(javascript, sandbox);
const helpers = sandbox.exports;
const plain = (value) => JSON.parse(JSON.stringify(value));

test('amount accepts positive safe integers and Indonesian thousands grouping only', () => {
  for (const invalid of ['', '0', '-100', '1e3', 'abc100', '1,5', '1.5', '12.34', '9007199254740992']) {
    assert.notEqual(helpers.validateTransactionAmount(invalid), null, invalid);
  }
  assert.equal(helpers.parseTransactionAmount('12.345.678'), 12345678);
  assert.equal(helpers.parseTransactionAmount(' 100 '), 100);
  assert.equal(helpers.validateTransactionAmount(1.5), 'Nominal harus lebih dari 0.');
  assert.equal(helpers.validateTransactionAmount(100), null);
});

test('date validation rejects invalid dates and accepts leap days', () => {
  for (const invalid of ['2026-02-29', '2026-13-01', '2026-04-31', '2026-1-01', 'invalid']) {
    assert.equal(helpers.isValidIsoDate(invalid), false);
  }
  assert.equal(helpers.isValidIsoDate('2028-02-29'), true);
  assert.equal(helpers.validateTransactionNote('x'.repeat(501)) !== null, true);
  assert.equal(helpers.validateAssetName('x'.repeat(81)) !== null, true);
});

const before = {
  id: 4, type: 'investment', amount: 100, category_id: 9, category_name: 'Emas',
  transaction_date: '2026-11-09', note: 'Savings', asset_name: 'Gold', source_key: 'private-key',
};

test('partial payload omits unchanged fields and explicitly clears nullable fields', () => {
  const draft = {
    amount: '100', categoryId: 9, transactionDate: '2026-11-09', note: 'Savings',
    assetName: 'Gold', type: 'investment',
  };
  assert.deepEqual(plain(helpers.buildTransactionUpdatePayload(before, draft)), {});
  assert.deepEqual(plain(helpers.buildTransactionUpdatePayload(before, {
    ...draft, categoryId: null, note: '', assetName: '',
  })), { category_id: null, note: null, asset_name: null });
});

test('history shows all edited fields without internal source keys', () => {
  const after = { ...before, amount: 200, category_id: null, category_name: null,
    transaction_date: '2026-11-10', note: null, asset_name: null };
  const changes = helpers.describeHistoryChanges({ action: 'update', before, after });
  assert.deepEqual(plain(changes.map((item) => item.field)),
    ['amount', 'category', 'transaction_date', 'note', 'asset_name']);
  assert.equal(JSON.stringify(changes).includes('private-key'), false);
  assert.deepEqual(plain(helpers.describeHistoryChanges({ action: 'delete', before, after: null })), []);
});

test('history pagination deduplicates overlapping IDs', () => {
  const result = helpers.mergeHistoryPages([{ id: 5 }, { id: 4 }], [{ id: 4 }, { id: 3 }]);
  assert.deepEqual(plain(result.map((entry) => entry.id)), [5, 4, 3]);
});

test('history timestamps identify user or device timezone', () => {
  assert.match(helpers.formatAuditTimestamp('2026-11-09T01:00:00+00:00', 'Asia/Jakarta'), /08:00.*WIB/);
  assert.match(helpers.formatAuditTimestamp('2026-11-09T01:00:00Z'), /waktu perangkat/);
});

test('derived transactions remain read-only', () => {
  assert.equal(helpers.canEditTransaction({ can_edit: false }), false);
  assert.equal(helpers.canDeleteTransaction({ can_delete: false }), false);
  assert.equal(helpers.canEditTransaction(null), false);
});

test('detail screen keeps one keyboard owner and prevents duplicate mutations', () => {
  const detail = fs.readFileSync(path.join(root, 'app/transaction/[id].tsx'), 'utf8');
  const tree = ts.createSourceFile('detail.tsx', detail, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let paddingScreen = false;
  function visit(node) {
    if (ts.isJsxOpeningElement(node) && node.tagName.getText(tree) === 'Screen') {
      paddingScreen = node.attributes.properties.some((attribute) =>
        ts.isJsxAttribute(attribute) && attribute.name.text === 'keyboardBehavior' &&
        attribute.initializer?.text === 'padding');
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  assert.equal(paddingScreen, true);
  assert.doesNotMatch(detail, /KeyboardAvoidingView/);
  assert.match(detail, /savingRef\.current \|\| deletingRef\.current/);
});

test('history blocks pagination while refresh replaces the first page', () => {
  const history = fs.readFileSync(path.join(root, 'app/transaction-history.tsx'), 'utf8');
  assert.match(history, /loadingInitialRef\.current = true/);
  assert.match(history, /if \(loadingInitialRef\.current \|\| loadingMoreRef\.current/);
  assert.doesNotMatch(history, /entry\.(before|after)\.source_key/);
});

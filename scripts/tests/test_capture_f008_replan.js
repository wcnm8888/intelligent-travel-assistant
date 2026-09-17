const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../capture_f008_replan.js'), 'utf8');
const job = '11111111-1111-4111-8111-111111111111';
const rid = '22222222-2222-4222-8222-222222222222';
const requestId = '33333333-3333-4333-8333-333333333333';
const plan = '44444444-4444-4444-8444-444444444444';
const origin = 'http://127.0.0.1:18008';
const prefix = `${origin}/api/trip-plans/${job}/replans`;
const result = () => ({job_id: job, replan_id: rid, replan_request_id: requestId, status: 'awaiting_confirmation', errors: []});
function fixture(options = {}) {
  const events = new Map();
  const requests = [];
  let resolve, predicate, reads = 0, now = 0;
  const posted = {url: () => prefix + (options.confirm ? `/${rid}/decision` : ''), method: () => 'POST', postDataJSON: () => ({replan_request_id: requestId})};
  const response = {request: () => posted, status: () => options.http || 202, json: async () => {
    if (options.invalidJson) throw new Error('private body');
    return Object.hasOwn(options, 'body') ? options.body : result();
  }};
  const page = {
    url: () => options.origin || origin,
    evaluate: async () => job,
    on: (name, fn) => events.set(name, fn),
    off: name => events.delete(name),
    waitForResponse: fn => { predicate = fn; return new Promise(r => { resolve = r; }); },
    waitForTimeout: async () => { now += 100001; },
    getByRole: () => ({isVisible: async () => !!options.confirm, click: async () => {
      const unrelated = {request: () => ({...posted, url: () => prefix.replace(job, rid)})};
      assert.equal(predicate(unrelated), false);
      for (const otherOrigin of ['http://127.0.0.1:180080', 'http://127.0.0.1:18008.evil', 'http://127.0.0.1:18008@evil']) {
        assert.equal(predicate({request: () => ({...posted, url: () => posted.url().replace(origin, otherOrigin)})}), false);
      }
      events.get('request')(posted);
      if (options.concurrent) events.get('request')({...posted});
      assert.equal(predicate(response), true);
      resolve(response);
    }}),
    request: {get: async url => {
      requests.push(url);
      if (url.includes('/__r5__/diagnostics')) {
        reads++;
        return {status: () => options.diagnosticHttp || 200, json: async () => ({job_id: options.wrongJob ? rid : job, plan_id: plan, version: 12, fault_remaining: reads === 1 ? 2 : 0, private_key: 'private'})};
      }
      assert.equal(url, `${prefix}/${rid}`);
      return {status: () => options.pollHttp || 200, json: async () => options.polled || {...result(), status: 'completed'}};
    }},
  };
  // CLI loads a function expression, not a complete JavaScript statement.
  // URL is not a standard VM global and is not supplied by the real CLI.
  const capture = vm.runInNewContext('(' + source + '\n)', {Date: {now: () => now}});
  return {run: () => capture(page), events, requests};
}
test('correlates UI request, returns actual counters, and removes raw data', async () => {
  const f = fixture(); const observed = await f.run();
  assert.equal(observed.request_id, requestId); assert.equal(observed.before.fault_remaining, 2);
  assert.equal(observed.after.fault_remaining, 0); assert.equal(observed.before.version, 12);
  assert.equal(observed.old_plan_unchanged, true); assert.equal(f.events.size, 0);
  assert.equal(JSON.stringify(observed).includes('private'), false);
});
test('confirm polls only the correlated replan', async () => {
  const f = fixture({confirm: true, body: {...result(), status: 'replanning'}});
  assert.equal((await f.run()).status, 'completed'); assert.equal(f.requests.length, 3);
});
test('non-2xx records only allowed error fields', async () => {
  const f = fixture({http: 409, body: {error: {code: 'constraint_conflict', diagnostic_code: 'scope_conflict', message: 'private', retryable: false}}});
  const value = await f.run(); assert.equal(value.status, 'HTTP_ERROR');
  assert.equal(value.errors[0].public_code, 'constraint_conflict');
  assert.equal(JSON.stringify(value).includes('private'), false);
});
test('invalid error body stays unknown', async () => {
  const value = await fixture({http: 502, invalidJson: true}).run();
  assert.equal(value.status, 'HTTP_ERROR'); assert.equal(value.replan_id, 'UNKNOWN');
});
test('valid JSON null error body stays unknown', async () => {
  const value = await fixture({http: 502, body: null}).run();
  assert.equal(value.status, 'HTTP_ERROR'); assert.equal(value.errors.length, 0);
});
test('poll non-2xx preserves HTTP failure without accepting a false terminal', async () => {
  const value = await fixture({confirm: true, body: {...result(), status: 'replanning'}, pollHttp: 503, polled: {error: {code: 'provider_unavailable', message: 'private'}}}).run();
  assert.equal(value.status, 'HTTP_ERROR'); assert.equal(value.http_status, 503);
  assert.equal(value.errors[0].public_code, 'provider_unavailable');
  assert.equal(JSON.stringify(value).includes('private'), false);
});
for (const [label, options, error] of [
  ['request ID mismatch', {body: {...result(), replan_request_id: rid}}, 'response_mismatch'],
  ['job mismatch', {body: {...result(), job_id: rid}}, 'response_mismatch'],
  ['concurrent submissions', {concurrent: true}, 'ambiguous_submission'],
  ['poll mismatch', {confirm: true, body: {...result(), status: 'replanning'}, polled: {...result(), replan_id: job}}, 'response_mismatch'],
  ['poll timeout', {body: {...result(), status: 'replanning'}, polled: {...result(), status: 'replanning'}}, 'terminal_timeout'],
  ['diagnostic unavailable', {diagnosticHttp: 403}, 'diagnostics_unavailable'],
  ['diagnostic wrong job', {wrongJob: true}, 'diagnostics_invalid'],
  ['nonlocal origin', {origin: 'https://example.com'}, 'origin_denied'],
  ['lookalike origin', {origin: origin + '.evil/'}, 'origin_denied'],
  ['userinfo origin', {origin: origin + '@evil/'}, 'origin_denied'],
  ['wrong port', {origin: origin + '0/'}, 'origin_denied'],
]) test(label, async () => {
  const f = fixture(options); await assert.rejects(f.run(), new RegExp(error)); assert.equal(f.events.size, 0);
});

const test = require('node:test');
const assert = require('node:assert/strict');

process.env.MODEL_API_KEYS = 'test-api-key';
process.env.MODEL_API_RATE_LIMIT = '60';
const api = require('../../api/_lib/catalog-api');
const modelsHandler = require('../../api/v1/models');
const indexHandler = require('../../api/v1/index');

function request({ method = 'GET', query = {}, headers = {}, url = '/api/v1/models' } = {}) {
  return { method, query, url, headers: { 'x-forwarded-for': '127.0.0.1', ...headers }, socket: { remoteAddress: '127.0.0.1' } };
}
function response() {
  return { statusCode: 200, headers: {}, body: '', setHeader(name, value) { this.headers[name.toLowerCase()] = String(value); }, end(value = '') { this.body = value; this.ended = true; } };
}
function call(handler, options) {
  const req = request(options), res = response();
  handler(req, res);
  return { req, res, json: res.body ? JSON.parse(res.body) : null };
}
const auth = { authorization: 'Bearer test-api-key' };
test.beforeEach(() => api.resetForTests());

test('rejects missing API keys with structured errors', () => {
  const { res, json } = call(modelsHandler);
  assert.equal(res.statusCode, 401); assert.equal(json.error.code, 'invalid_api_key'); assert.ok(json.error.request_id);
});
test('returns versioned, filtered and paginated catalog data', () => {
  const { res, json } = call(modelsHandler, { headers: auth, query: { platform: 'deepseek', status: 'priced', limit: '2' } });
  assert.equal(res.statusCode, 200); assert.equal(json.api_version, '1.0.0'); assert.equal(json.schema_version, '2.0.0'); assert.equal(json.items.length, 2);
  assert.ok(json.items.every((item) => item.platform_id === 'deepseek' && item.price_status === 'priced'));
  assert.match(json.pagination.next_cursor, /^[A-Za-z0-9_-]+$/); assert.match(res.headers.etag, /^"[a-f0-9]{64}"$/); assert.equal(res.headers['x-ratelimit-remaining'], '59'); assert.match(res.headers['cache-control'], /max-age=60/); assert.equal(res.headers['access-control-allow-origin'], undefined);
});
test('honors ETag revalidation', () => {
  const first = call(modelsHandler, { headers: auth, query: { q: 'deepseek-v4', limit: '3' } });
  const second = call(modelsHandler, { headers: { ...auth, 'if-none-match': first.res.headers.etag }, query: { q: 'deepseek-v4', limit: '3' } });
  assert.equal(second.res.statusCode, 304); assert.equal(second.res.body, '');
});
test('validates query and method semantics', () => {
  assert.equal(call(modelsHandler, { headers: auth, query: { limit: '101' } }).json.error.code, 'invalid_limit');
  assert.equal(call(modelsHandler, { headers: auth, query: { cursor: 'broken' } }).json.error.code, 'invalid_cursor');
  assert.equal(call(modelsHandler, { method: 'POST', headers: auth }).res.statusCode, 405);
});
test('enforces fixed-window rate limits and exposes usage headers', () => {
  const original = console.info; console.info = () => {}; let result;
  try { for (let i = 0; i < 61; i += 1) result = call(modelsHandler, { headers: auth, query: { limit: '1' } }); } finally { console.info = original; }
  assert.equal(result.res.statusCode, 429); assert.equal(result.json.error.code, 'rate_limit_exceeded'); assert.equal(result.res.headers['x-ratelimit-remaining'], '0'); assert.ok(Number(result.res.headers['retry-after']) >= 1);
});
test('publishes authenticated API discovery metadata', () => {
  const { res, json } = call(indexHandler, { headers: auth, url: '/api/v1' });
  assert.equal(res.statusCode, 200); assert.equal(json.endpoints.models, '/api/v1/models'); assert.match(json.usage, /X-RateLimit/);
});

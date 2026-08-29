const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const API_VERSION = '1.0.0';
function positiveInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}
const WINDOW_MS = positiveInteger(process.env.MODEL_API_RATE_WINDOW_SECONDS, 60) * 1000;
const LIMIT = positiveInteger(process.env.MODEL_API_RATE_LIMIT, 60);
const usage = new Map();
let catalogCache;

function requestId(req) {
  return String(req.headers['x-vercel-id'] || crypto.randomUUID());
}
function configuredKeys() {
  return String(process.env.MODEL_API_KEYS || '').split(',').map((key) => key.trim()).filter(Boolean);
}
function presentedKey(req) {
  const authorization = String(req.headers.authorization || '');
  if (/^Bearer\s+/i.test(authorization)) return authorization.replace(/^Bearer\s+/i, '').trim();
  return String(req.headers['x-api-key'] || '').trim();
}
function digest(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}
function keyMatches(candidate, expected) {
  const left = Buffer.from(digest(candidate));
  const right = Buffer.from(digest(expected));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}
function send(res, status, body, headers = {}) {
  res.statusCode = status;
  Object.entries(headers).forEach(([name, value]) => res.setHeader(name, String(value)));
  if (body == null) return res.end();
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  return res.end(JSON.stringify(body));
}
function error(res, status, code, message, id, details, headers = {}) {
  return send(res, status, { error: { code, message, request_id: id, ...(details ? { details } : {}) } }, { 'Cache-Control': 'no-store', ...headers });
}
function authorize(req, res, options = {}) {
  const id = requestId(req);
  const keys = configuredKeys();
  if (!keys.length) {
    console.info(JSON.stringify({ event: 'model_api_request', request_id: id, method: req.method, path: String(req.url || '').split('?')[0], status: 503 }));
    error(res, 503, 'api_not_configured', 'API access is temporarily unavailable.', id);
    return null;
  }
  const candidate = presentedKey(req);
  if (!candidate || !keys.some((key) => keyMatches(candidate, key))) {
    console.info(JSON.stringify({ event: 'model_api_request', request_id: id, key_hash: candidate ? digest(candidate).slice(0, 12) : null, method: req.method, path: String(req.url || '').split('?')[0], status: 401 }));
    error(res, 401, 'invalid_api_key', 'A valid Bearer token or X-API-Key header is required.', id);
    return null;
  }
  const keyHash = digest(candidate).slice(0, 12);
  const ip = String(req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown').split(',')[0].trim();
  const bucketKey = `${keyHash}:${digest(ip).slice(0, 12)}`;
  const now = Date.now();
  let bucket = usage.get(bucketKey);
  if (!bucket || now >= bucket.resetAt) bucket = { count: 0, resetAt: now + WINDOW_MS };
  if (options.count !== false) bucket.count += 1;
  usage.set(bucketKey, bucket);
  const remaining = Math.max(0, LIMIT - bucket.count);
  const headers = {
    'X-RateLimit-Limit': LIMIT,
    'X-RateLimit-Remaining': remaining,
    'X-RateLimit-Reset': Math.ceil(bucket.resetAt / 1000),
  };
  if (bucket.count > LIMIT) {
    headers['Retry-After'] = Math.max(1, Math.ceil((bucket.resetAt - now) / 1000));
    console.info(JSON.stringify({ event: 'model_api_request', request_id: id, key_hash: keyHash, method: req.method, path: String(req.url || '').split('?')[0], status: 429 }));
    error(res, 429, 'rate_limit_exceeded', 'Rate limit exceeded. Retry after the current window.', id, { retry_after_seconds: Number(headers['Retry-After']) }, headers);
    return null;
  }
  return { id, keyHash, bucketKey, bucket, headers };
}
function loadCatalog() {
  if (!catalogCache) {
    const candidates = [
      path.join(process.cwd(), 'models_data.json'),
      path.join(__dirname, '..', '..', 'models_data.json'),
      path.join(__dirname, '..', '..', '..', 'models_data.json'),
    ];
    const catalogPath = candidates.find((candidate) => fs.existsSync(candidate));
    if (!catalogPath) throw new Error('models_data.json is unavailable in the function bundle');
    catalogCache = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
  }
  return catalogCache;
}
function parseCursor(value) {
  if (!value) return 0;
  try {
    const parsed = JSON.parse(Buffer.from(String(value), 'base64url').toString('utf8'));
    return Number.isInteger(parsed.offset) && parsed.offset >= 0 ? parsed.offset : null;
  } catch { return null; }
}
function makeCursor(offset) {
  return Buffer.from(JSON.stringify({ offset })).toString('base64url');
}
function etag(body) {
  return `"${digest(JSON.stringify(body))}"`;
}
function logRequest(req, auth, status, extra = {}) {
  console.info(JSON.stringify({ event: 'model_api_request', request_id: auth.id, key_hash: auth.keyHash, method: req.method, path: String(req.url || '').split('?')[0], status, ...extra }));
}
function commonHeaders(auth) {
  return {
    ...auth.headers,
    'Cache-Control': 'private, max-age=60, stale-while-revalidate=300',
    'Vary': 'Authorization, X-API-Key',
    'X-API-Version': API_VERSION,
  };
}
function resetForTests() { usage.clear(); catalogCache = undefined; }

module.exports = { API_VERSION, LIMIT, authorize, commonHeaders, error, etag, loadCatalog, logRequest, makeCursor, parseCursor, resetForTests, send, usage };

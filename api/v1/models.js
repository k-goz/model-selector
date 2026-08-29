const api = require('../_lib/catalog-api');

const PRICE_STATUSES = new Set(['priced', 'free', 'free_tier', 'non_token', 'unknown', 'retiring', 'unavailable']);
const CONFIDENCE = new Set(['high', 'medium', 'low', 'unknown']);

module.exports = function handler(req, res) {
  if (req.method !== 'GET') return api.error(res, 405, 'method_not_allowed', 'Only GET is supported.', String(req.headers['x-vercel-id'] || 'unknown'));
  const auth = api.authorize(req, res);
  if (!auth) return;
  try {
    const reject = (code, errorCode, message) => {
      api.logRequest(req, auth, code);
      return api.error(res, code, errorCode, message, auth.id, undefined, auth.headers);
    };
    const limit = Number(req.query?.limit || 50);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) return reject(400, 'invalid_limit', 'limit must be an integer between 1 and 100.');
    const offset = api.parseCursor(req.query?.cursor);
    if (offset == null) return reject(400, 'invalid_cursor', 'cursor is malformed.');
    const status = String(req.query?.status || '');
    const confidence = String(req.query?.confidence || '');
    if (status && !PRICE_STATUSES.has(status)) return reject(400, 'invalid_status', 'status is not supported.');
    if (confidence && !CONFIDENCE.has(confidence)) return reject(400, 'invalid_confidence', 'confidence is not supported.');
    const platform = String(req.query?.platform || '').toLowerCase();
    const q = String(req.query?.q || '').trim().toLowerCase();
    const catalog = api.loadCatalog();
    const filtered = catalog.models.filter((model) => {
      if (platform && String(model.platform_id).toLowerCase() !== platform) return false;
      if (status && model.price_status !== status) return false;
      if (confidence && (model.confidence?.grade || 'unknown') !== confidence) return false;
      if (q && ![model.name, model.platform_name, model.model_family, ...(model.aliases || [])].join(' ').toLowerCase().includes(q)) return false;
      return true;
    });
    const items = filtered.slice(offset, offset + limit);
    const nextOffset = offset + items.length;
    const body = {
      api_version: api.API_VERSION,
      schema_version: catalog.meta.schema_version,
      data_updated_at: catalog.meta.updated_at,
      license: 'See /docs/API_V1.md; provider terms and source attribution apply.',
      pagination: { limit, returned: items.length, total: filtered.length, next_cursor: nextOffset < filtered.length ? api.makeCursor(nextOffset) : null },
      items,
    };
    const tag = api.etag(body);
    const headers = { ...api.commonHeaders(auth), ETag: tag };
    if (String(req.headers['if-none-match'] || '') === tag) {
      api.logRequest(req, auth, 304, { returned: 0 });
      return api.send(res, 304, null, headers);
    }
    api.logRequest(req, auth, 200, { returned: items.length, total: filtered.length });
    return api.send(res, 200, body, headers);
  } catch (err) {
    console.error(JSON.stringify({ event: 'model_api_error', request_id: auth.id, error: err.message }));
    return api.error(res, 500, 'internal_error', 'The catalog could not be read.', auth.id);
  }
};

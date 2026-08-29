const api = require('../_lib/catalog-api');
module.exports = function handler(req, res) {
  if (req.method !== 'GET') return api.error(res, 405, 'method_not_allowed', 'Only GET is supported.', String(req.headers['x-vercel-id'] || 'unknown'));
  const auth = api.authorize(req, res);
  if (!auth) return;
  api.logRequest(req, auth, 200, { endpoint: 'discovery' });
  return api.send(res, 200, { api_version: api.API_VERSION, endpoints: { models: '/api/v1/models' }, documentation: 'https://model.ai-selector.top/docs/API_V1.md', usage: 'Inspect X-RateLimit-* response headers; aggregate request logs are the MVP usage source.' }, api.commonHeaders(auth));
};

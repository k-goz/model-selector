import { createReadStream, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';
import { createGzip } from 'node:zlib';

const root = resolve(process.cwd());
const port = Number(process.env.PORT || 4173);
const types = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
};
const compressible = new Set(['.css', '.html', '.js', '.json', '.xml']);

createServer((request, response) => {
  const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  let relative = normalize(pathname).replace(/^([/\\])+/, '');
  let file = join(root, relative || 'index.html');
  if (!file.startsWith(root)) {
    response.writeHead(403).end('Forbidden');
    return;
  }
  try {
    if (statSync(file).isDirectory()) file = join(file, 'index.html');
    const extension = extname(file).toLowerCase();
    const headers = {
      'Content-Type': types[extension] || 'application/octet-stream',
      'Cache-Control': 'public, max-age=0, must-revalidate',
      'Vary': 'Accept-Encoding',
    };
    const acceptsGzip = /\bgzip\b/.test(request.headers['accept-encoding'] || '');
    if (acceptsGzip && compressible.has(extension)) {
      headers['Content-Encoding'] = 'gzip';
      response.writeHead(200, headers);
      createReadStream(file).pipe(createGzip()).pipe(response);
    } else {
      headers['Content-Length'] = statSync(file).size;
      response.writeHead(200, headers);
      createReadStream(file).pipe(response);
    }
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
  }
}).listen(port, '127.0.0.1', () => {
  process.stdout.write(`Static test server listening on http://127.0.0.1:${port}\n`);
});

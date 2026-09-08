import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const root = import.meta.dirname;
const port = Number(process.env.PORT || 3000);
const backend = process.env.API_PROXY_TARGET || 'http://localhost:8000';
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };

http.createServer(async (request, response) => {
  if (request.url.startsWith('/api/')) {
    try {
      const target = new URL(request.url.slice(4), backend);
      const upstream = await fetch(target, { headers: { accept: request.headers.accept || 'application/json' }, signal: AbortSignal.timeout(8000) });
      response.writeHead(upstream.status, { 'content-type': upstream.headers.get('content-type') || 'application/json' });
      response.end(Buffer.from(await upstream.arrayBuffer()));
    } catch {
      response.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
      response.end(JSON.stringify({ detail: '백엔드에 연결할 수 없습니다.' }));
    }
    return;
  }
  const pathname = new URL(request.url, 'http://localhost').pathname;
  const relative = pathname === '/' ? 'index.html' : normalize(pathname).replace(/^[/\\]+/, '');
  try {
    const body = await readFile(join(root, relative));
    response.writeHead(200, { 'content-type': types[extname(relative)] || 'application/octet-stream' });
    response.end(body);
  } catch {
    response.writeHead(404).end('Not found');
  }
}).listen(port, () => console.log(`Web frontend: http://localhost:${port}`));

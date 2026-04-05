import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname } from "node:path";

const PORT = 3100;
const STATIC_DIR = "/app/dist";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

const IMMUTABLE_RE = /\.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$/;

async function serveFile(res, filePath, status = 200) {
  try {
    const data = await readFile(filePath);
    const ext = extname(filePath);
    const mime = MIME_TYPES[ext] || "application/octet-stream";
    const headers = { "Content-Type": mime };
    if (IMMUTABLE_RE.test(filePath)) {
      headers["Cache-Control"] = "public, max-age=31536000, immutable";
    }
    res.writeHead(status, headers);
    res.end(data);
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("Not Found");
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = url.pathname;

  // Health check
  if (pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end('{"status":"ok"}');
    return;
  }

  // Try static file
  const filePath = join(STATIC_DIR, pathname);
  try {
    const info = await stat(filePath);
    if (info.isFile()) {
      await serveFile(res, filePath);
      return;
    }
  } catch {
    // Not a static file — fall through to SPA
  }

  // SPA fallback
  await serveFile(res, join(STATIC_DIR, "index.html"));
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`frontend listening on :${PORT}`);
});

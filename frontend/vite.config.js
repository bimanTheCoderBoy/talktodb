import { defineConfig, defaultClientConditions } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';  
import fs from 'fs';
import path from 'path';

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
    // Custom plugin to serve files from absolute paths
    // URL pattern: /serve/<encoded-absolute-path>
    // Example: /serve/C%3A%2FUsers%2Fdata%2Ffile.json -> C:/Users/data/file.json
    {
      name: 'serve-dynamic-path',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // Match /serve/<path> pattern (same as nginx)
          if (!req.url.startsWith('/serve/')) {
            return next();
          }

          try {
            // Extract path after /serve/ and decode URI
            const url = new URL(req.url, 'http://localhost');
            const encodedPath = url.pathname.replace(/^\/serve\//, '');
            const filePath = decodeURIComponent(encodedPath);

            if (!filePath) {
              res.statusCode = 400;
              res.end('Missing file path');
              return;
            }

            console.log('Serving file:', filePath);

            // Handle OPTIONS preflight (CORS)
            if (req.method === 'OPTIONS') {
              res.setHeader('Access-Control-Allow-Origin', '*');
              res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
              res.setHeader('Access-Control-Allow-Headers', 'Range, Content-Type');
              res.setHeader('Access-Control-Expose-Headers', 'Accept-Ranges, Content-Length, Content-Range');
              res.statusCode = 204;
              res.end();
              return;
            }

            if (fs.existsSync(filePath)) {
              const stat = fs.statSync(filePath);
              const fileSize = stat.size;

              const ext = path.extname(filePath).toLowerCase();
              const contentTypes = {
                '.json': 'application/json',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.tif': 'image/tiff',
                '.tiff': 'image/tiff',
                '.xml': 'application/xml',
                '.bil': 'application/octet-stream',
                '.pdf': 'application/pdf',
              };
              
              res.setHeader('Access-Control-Allow-Origin', '*');
              res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
              res.setHeader('Access-Control-Allow-Headers', 'Range, Content-Type');
              res.setHeader('Access-Control-Expose-Headers', 'Accept-Ranges, Content-Length, Content-Range');
              res.setHeader('Content-Type', contentTypes[ext] || 'application/octet-stream');
              res.setHeader('Accept-Ranges', 'bytes');
              res.setHeader('Content-Length', fileSize);

              if (req.method === 'HEAD') {
                res.statusCode = 200;
                res.end();
                return;
              }

              const range = req.headers.range;
              if (range) {
                const parts = range.replace(/bytes=/, '').split('-');
                const start = parseInt(parts[0], 10);
                const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

                if (start >= fileSize || end >= fileSize || start > end) {
                  res.statusCode = 416;
                  res.setHeader('Content-Range', `bytes */${fileSize}`);
                  res.end();
                  return;
                }

                res.statusCode = 206;
                res.setHeader('Content-Range', `bytes ${start}-${end}/${fileSize}`);
                res.setHeader('Content-Length', end - start + 1);
                fs.createReadStream(filePath, { start, end }).pipe(res);
              } else {
                res.setHeader('Content-Length', fileSize);
                fs.createReadStream(filePath).pipe(res);
              }
            } else {
              console.error('File not found:', filePath);
              res.statusCode = 404;
              res.end('File not found: ' + filePath);
            }
          } catch (error) {
            console.error('Error serving file:', error);
            res.statusCode = 500;
            res.end('Server error');
          }
        });
      }
    }
  ],
  resolve: {
    // Ensure packages with conditional exports can select worker-safe builds.
    // (Some deps incorrectly pick DOM-based "browser" entries in Web Workers.)
    conditions: ['worker', ...defaultClientConditions],
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // // Web Workers don't have `document`, but some remark/micromark deps pick
      // // a DOM-based "browser" export by default. Force the worker-safe build.
      "decode-named-character-reference": path.resolve(
        __dirname,
        "./node_modules/decode-named-character-reference/index.js"
      ),
    }
  },
  server: {
    host: true,
    port: 5173
  }
});


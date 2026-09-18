const getEnv = (key, fallback = '') => import.meta.env[key] || fallback;

export const RAG_DOCS_BASE = () => getEnv('VITE_RAG_DOCUMENTATIONS_BASE_URL');
export const RAG_IMAGES_BASE = () => getEnv('VITE_RAG_IMAGES_BASE_URL');

/**
 * Build a /serve/<encoded-path> URL.
 * @param {string} basePath - filesystem base directory (from env)
 * @param {string} filename - relative file name
 */
export function serveFileUrl(basePath, filename) {
  if (!basePath) return `/${filename}`;
  const normalizedBase = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath;
  const fullPath = `${normalizedBase}/${filename}`;
  return `/serve/${encodeURIComponent(fullPath)}`;
}

export function serveDocUrl(filename) {
  return serveFileUrl(RAG_DOCS_BASE(), filename);
}

export function serveImageUrl(filename) {
  return serveFileUrl(RAG_IMAGES_BASE(), filename);
}

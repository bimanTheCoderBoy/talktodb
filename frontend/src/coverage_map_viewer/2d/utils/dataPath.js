/**
 * Data Path Utility
 * 
 * Builds URLs for serving files from any file system path.
 * Works with both Vite dev server and nginx in production.
 * 
 * URL Pattern: /serve/<full-path-to-file>
 * 
 * Usage:
 *   - Navigate to: http://localhost:5173/map/2d/C:/Users/data/coverage
 *   - The map will load manifest.json and PNGs from that path
 */

/**
 * Get the full URL for a data file using the /serve/ endpoint
 * @param {string} basePath - The file system path (e.g., "C:/Users/data/coverage")
 * @param {string} filename - The filename (e.g., 'manifest.json' or 'coverage.png')
 * @returns {string} Full URL to fetch the file via the /serve/ endpoint
 */
export function getDataFileUrl(basePath, filename) {
  // Normalize base path (remove trailing slash)
  const normalizedBase = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath;
  
  // Build full path and encode for URL safety
  const fullPath = `${normalizedBase}/${filename}`;
  const encodedPath = encodeURIComponent(fullPath);
  
  // Use the /serve/ endpoint (matches nginx pattern)
  return `/serve/${encodedPath}`;
}


import { transformExtent } from 'ol/proj';
import proj4 from 'proj4';
import { register } from 'ol/proj/proj4';

const registeredProjections = new Set(['4326', '3857']);

/**
 * Ensure an EPSG projection is registered with OpenLayers via proj4.
 * Fetches the proj4 definition from epsg.io at runtime so unknown CRS works.
 */
export async function ensureProjection(epsgCode) {
  const code = String(epsgCode).replace(/^EPSG:/i, '').trim();
  if (!code || registeredProjections.has(code)) return;

  const resp = await fetch(`https://epsg.io/${code}.proj4`);
  if (!resp.ok) {
    console.warn(`Could not fetch proj4 definition for EPSG:${code}`);
    return;
  }

  const def = await resp.text();
  proj4.defs(`EPSG:${code}`, def);
  register(proj4);
  registeredProjections.add(code);
}

/**
 * Normalize EPSG code to proper format.
 * Handles: 4326, "4326", "EPSG:4326", "epsg:4326".
 */
export function normalizeEpsg(epsg) {
  if (!epsg) return 'EPSG:4326';
  const epsgStr = String(epsg).trim().toUpperCase();
  if (epsgStr.startsWith('EPSG:')) return epsgStr;
  return `EPSG:${epsgStr}`;
}

/**
 * Convert bounds { west, south, east, north } to OL extent in EPSG:3857.
 */
export function boundsToExtent(bounds, sourceEpsg = 'EPSG:4326') {
  const normalizedEpsg = normalizeEpsg(sourceEpsg);
  const extent = [bounds.west, bounds.south, bounds.east, bounds.north];

  if (normalizedEpsg === 'EPSG:3857') return extent;

  return transformExtent(extent, normalizedEpsg, 'EPSG:3857');
}

/**
 * Convert bounds to WGS84 { west, south, east, north }.
 */
export function boundsToWGS84(bounds, sourceEpsg = 'EPSG:4326') {
  const normalizedEpsg = normalizeEpsg(sourceEpsg);
  if (normalizedEpsg === 'EPSG:4326') return bounds;

  const extent = [bounds.west, bounds.south, bounds.east, bounds.north];
  const wgs84 = transformExtent(extent, normalizedEpsg, 'EPSG:4326');

  return {
    west: wgs84[0],
    south: wgs84[1],
    east: wgs84[2],
    north: wgs84[3],
  };
}

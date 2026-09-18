import { fromLonLat, toLonLat } from 'ol/proj';
import OlPolygon from 'ol/geom/Polygon';

/**
 * Convert WGS84 ring [[lon,lat], ...] to an OL Polygon in EPSG:3857.
 */
export function ringToOlPolygon(ring) {
  if (!ring || ring.length < 3) return null;
  const coords = ring.map(c => fromLonLat(c));
  return new OlPolygon([coords]);
}

/**
 * Convert an OL Polygon (EPSG:3857) back to WGS84 ring [[lon,lat], ...].
 */
export function olPolygonToRing(olPoly) {
  if (!olPoly) return null;
  const coords = olPoly.getCoordinates()[0];
  return coords.map(c => toLonLat(c));
}

/**
 * Ensure a coordinate ring is closed (first === last).
 */
export function ensureClosedRing(ring) {
  if (!ring || ring.length < 3) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) {
    return [...ring, first];
  }
  return ring;
}

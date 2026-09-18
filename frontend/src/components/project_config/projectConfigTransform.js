/**
 * Coordinate transform helpers for project config.
 *
 * Backend stores polygon coordinates as List[List[float]]:
 *   [[lon1, lat1], [lon2, lat2], ...]
 *
 * Frontend works with the same ring format:
 *   [[lon1, lat1], [lon2, lat2], ...]
 */

/**
 * Ensure a ring is closed (first point == last point).
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

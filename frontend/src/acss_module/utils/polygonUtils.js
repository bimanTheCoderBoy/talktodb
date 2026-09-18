/**
 * Polygon utility functions for ACSS module
 */

// Land-boundary constraint helpers (disabled for now — re-enable later)
// import GeoJSON from 'ol/format/GeoJSON';
// export function landGeometryFromGeoJSON(geojson) { ... }
// export function isPointOnLand(lon, lat, landGeom) { ... }
// export function isPolygonRingOnLand(ring, landGeom) { ... }

/**
 * Calculate the signed area of a polygon to determine winding order
 * Positive = CCW, Negative = CW
 */
export function getPolygonSignedArea(coords) {
  if (!coords || coords.length < 3) return 0;

  let area = 0;
  const n = coords.length;

  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += coords[i][0] * coords[j][1];
    area -= coords[j][0] * coords[i][1];
  }

  return area / 2;
}

/**
 * Check if polygon is clockwise
 */
export function isClockwise(coords) {
  return getPolygonSignedArea(coords) < 0;
}

/**
 * Expand a polygon outward uniformly by a given distance in kilometers
 * Uses edge offset method - moves each edge outward by the buffer distance
 * and calculates new vertex positions at edge intersections
 *
 * @param {Array} coords - Array of [lon, lat] coordinates
 * @param {number} radiusKm - Buffer distance in kilometers
 * @returns {Array} Expanded polygon coordinates
 */
export function expandPolygon(coords, radiusKm) {
  if (!coords || coords.length < 3) return null;

  // Remove the closing point if it duplicates the first
  let points = [...coords];
  const first = points[0];
  const last = points[points.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) {
    points = points.slice(0, -1);
  }

  if (points.length < 3) return null;

  // Left-hand normals (-dy, dx) are outward only for CW rings.
  // Draw order may be CW or CCW — flip the offset when CCW so the
  // boundary always expands outward (avoids inverted/flipped rings).
  const outwardSign = isClockwise(points) ? 1 : -1;

  // Calculate centroid for latitude-based conversion
  let centroidLat = 0;
  points.forEach(([, lat]) => { centroidLat += lat; });
  centroidLat /= points.length;

  // Convert km to degrees (approximate)
  const kmPerDegreeLat = 111;
  const kmPerDegreeLon = 111 * Math.cos(centroidLat * Math.PI / 180);
  const bufferLat = radiusKm / kmPerDegreeLat;
  const bufferLon = radiusKm / kmPerDegreeLon;

  // Calculate outward normal for each edge and offset the vertices
  const n = points.length;
  const expandedPoints = [];

  for (let i = 0; i < n; i++) {
    const prev = points[(i - 1 + n) % n];
    const curr = points[i];
    const next = points[(i + 1) % n];

    // Vector for previous edge (prev -> curr)
    const dx1 = curr[0] - prev[0];
    const dy1 = curr[1] - prev[1];
    const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1);

    // Vector for next edge (curr -> next)
    const dx2 = next[0] - curr[0];
    const dy2 = next[1] - curr[1];
    const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);

    if (len1 === 0 || len2 === 0) {
      expandedPoints.push([curr[0], curr[1]]);
      continue;
    }

    // Left-hand normals; outwardSign corrects for winding order
    const nx1 = outwardSign * (-dy1 / len1);
    const ny1 = outwardSign * (dx1 / len1);

    const nx2 = outwardSign * (-dy2 / len2);
    const ny2 = outwardSign * (dx2 / len2);

    // Average the normals for the vertex offset direction
    let avgNx = (nx1 + nx2) / 2;
    let avgNy = (ny1 + ny2) / 2;
    const avgLen = Math.sqrt(avgNx * avgNx + avgNy * avgNy);

    if (avgLen > 0) {
      avgNx /= avgLen;
      avgNy /= avgLen;
    }

    // Calculate the angle between edges to adjust buffer distance at corners
    const dot = nx1 * nx2 + ny1 * ny2;
    const angle = Math.acos(Math.max(-1, Math.min(1, dot)));
    const miterScale = angle > 0.01 ? 1 / Math.cos(angle / 2) : 1;

    // Limit miter to prevent extreme spikes at sharp angles
    const limitedMiter = Math.min(miterScale, 3);

    // Offset the vertex
    const newLon = curr[0] + avgNx * bufferLon * limitedMiter;
    const newLat = curr[1] + avgNy * bufferLat * limitedMiter;

    expandedPoints.push([newLon, newLat]);
  }

  // Close the polygon
  if (expandedPoints.length > 0) {
    expandedPoints.push([...expandedPoints[0]]);
  }

  return expandedPoints;
}


/**
 * Calculate the centroid of a polygon
 * @param {Array} coords - Array of [lon, lat] coordinates
 * @returns {Array} [lon, lat] of centroid
 */
export function getPolygonCentroid(coords) {
  if (!coords || coords.length < 3) return null;

  let centroidLon = 0, centroidLat = 0;
  coords.forEach(([lon, lat]) => {
    centroidLon += lon;
    centroidLat += lat;
  });

  return [
    centroidLon / coords.length,
    centroidLat / coords.length
  ];
}

/**
 * Calculate approximate area of a polygon in square kilometers
 * Uses the Shoelace formula with latitude correction
 * @param {Array} coords - Array of [lon, lat] coordinates
 * @returns {number} Area in square kilometers
 */
export function getPolygonAreaKm2(coords) {
  if (!coords || coords.length < 3) return 0;

  // Get centroid for latitude correction
  const centroid = getPolygonCentroid(coords);
  const latRad = centroid[1] * Math.PI / 180;

  // Convert to approximate km coordinates
  const kmPerDegreeLat = 111;
  const kmPerDegreeLon = 111 * Math.cos(latRad);

  // Calculate signed area in km²
  let area = 0;
  const n = coords.length;

  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const xi = coords[i][0] * kmPerDegreeLon;
    const yi = coords[i][1] * kmPerDegreeLat;
    const xj = coords[j][0] * kmPerDegreeLon;
    const yj = coords[j][1] * kmPerDegreeLat;

    area += xi * yj;
    area -= xj * yi;
  }

  return Math.abs(area / 2);
}

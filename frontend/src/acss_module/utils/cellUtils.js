/**
 * Cell/Site Utility Functions for ACSS Module
 * 
 * Handles cell sector geometry creation, band-based coloring and radius calculation,
 * and beamwidth computation based on unique azimuths per site.
 */

// Constants - reasonable sector sizes for map display
export const BASE_RADIUS = 40; // meters - radius for highest frequency (3700MHz)
export const MAX_RADIUS = 80; // meters - radius for lowest frequency (700MHz)
export const MIN_BEAM_WIDTH = 10; // degrees (cap for many azimuths)
export const MAX_BEAM_WIDTH = 65; // degrees (cap for few azimuths)

function parseBandFrequency(band) {
  if (typeof band === 'number') return band;
  const match = String(band).match(/(\d{3,4})/);
  return match ? parseInt(match[1], 10) : 2100;
}

/**
 * Band color mapping - lower frequencies typically shown in warmer colors
 */
const BAND_COLORS = {
  700: '#E53935',   // Red
  800: '#FB8C00',   // Orange
  850: '#F57C00',   // Dark Orange
  900: '#FF9800',   // Amber
  1800: '#FDD835',  // Yellow
  1900: '#FFEB3B',  // Light Yellow
  2100: '#43A047',  // Green
  2250: '#1E88E5',  // Blue
  2300: '#1976D2',  // Dark Blue
  2600: '#8E24AA',  // Purple
  3500: '#7B1FA2',  // Deep Purple
  3700: '#6A1B9A',  // Violet
};

/**
 * Get color for a frequency band
 * @param {number|string} band - Frequency band in MHz
 * @returns {string} Hex color code
 */
export function getBandColor(band) {
  const n = parseBandFrequency(band);
  if (BAND_COLORS[n]) return BAND_COLORS[n];

  const bands = Object.keys(BAND_COLORS).map(Number).sort((a, b) => a - b);
  let closest = bands[0];
  let minDiff = Math.abs(n - closest);

  for (const b of bands) {
    const diff = Math.abs(n - b);
    if (diff < minDiff) {
      minDiff = diff;
      closest = b;
    }
  }

  return BAND_COLORS[closest] || '#757575';
}

/**
 * Get radius based on frequency band using linear interpolation
 * Lower frequencies = larger radius, but with reasonable bounds
 * @param {number|string} band - Frequency band in MHz
 * @returns {number} Calculated radius in meters
 */
export function getBandRadius(band) {
  const n = parseBandFrequency(band);
  const minFreq = 700;
  const maxFreq = 3700;

  const clampedBand = Math.max(minFreq, Math.min(maxFreq, n));
  
  // Linear interpolation: lower freq = larger radius
  const t = (clampedBand - minFreq) / (maxFreq - minFreq);
  
  // Interpolate from MAX_RADIUS (for low freq) to BASE_RADIUS (for high freq)
  const radius = MAX_RADIUS - t * (MAX_RADIUS - BASE_RADIUS);
  
  return radius;
}

/**
 * Calculate beamwidth based on number of unique azimuths at a site
 * @param {Array} cells - Array of cell objects with azimuth property
 * @returns {number} Beamwidth in degrees
 */
export function calculateBeamWidth(cells) {
  const uniqueAzimuths = [...new Set(cells.map(c => c.azimuth))];
  const count = uniqueAzimuths.length;
  
  if (count === 0) return MAX_BEAM_WIDTH;
  
  let beamWidth = 360 / count;
  
  // Clamp to min/max
  beamWidth = Math.max(MIN_BEAM_WIDTH, Math.min(MAX_BEAM_WIDTH, beamWidth));
  
  return beamWidth;
}

/**
 * Group cells by their azimuth angle
 * @param {Array} cells - Array of cell objects
 * @returns {Object} Object with azimuth as key and array of cells as value (sorted by band ascending)
 */
export function groupCellsByAzimuth(cells) {
  const grouped = {};
  
  cells.forEach(cell => {
    const key = cell.azimuth;
    if (!grouped[key]) {
      grouped[key] = [];
    }
    grouped[key].push(cell);
  });
  
  Object.keys(grouped).forEach(key => {
    grouped[key].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  });
  
  return grouped;
}

/**
 * Calculate ring radii for cells at the same azimuth
 * Uses EQUAL-AREA distribution so each cell gets visually similar space
 * Higher frequency cells are closer to center, lower frequency on outside
 * @param {Array} cellsAtAzimuth - Array of cells at the same azimuth
 * @returns {Map} Map of cell_iid to { innerRadius, outerRadius }
 */
export function calculateRingRadii(cellsAtAzimuth) {
  const radiiMap = new Map();
  
  if (cellsAtAzimuth.length === 0) return radiiMap;
  
  const minBand = Math.min(...cellsAtAzimuth.map(c => parseBandFrequency(c.band)));
  const totalRadius = getBandRadius(minBand);
  
  if (cellsAtAzimuth.length === 1) {
    // Single cell - draw from center to its radius
    const cell = cellsAtAzimuth[0];
    radiiMap.set(cell.cell_iid, { innerRadius: 0, outerRadius: totalRadius });
    return radiiMap;
  }
  
  const sorted = [...cellsAtAzimuth].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  const n = sorted.length;
  
  // Use EQUAL-AREA distribution
  sorted.forEach((cell, index) => {
    const innerRadius = totalRadius * Math.sqrt(index / n);
    const outerRadius = totalRadius * Math.sqrt((index + 1) / n);
    
    radiiMap.set(cell.cell_iid, {
      innerRadius,
      outerRadius,
    });
  });
  
  return radiiMap;
}

/**
 * Create sector polygon coordinates (pie slice from center)
 * @param {number} lon - Longitude of site (degrees)
 * @param {number} lat - Latitude of site (degrees)
 * @param {number} azimuth - Azimuth angle in degrees (0=North, 90=East, 180=South, 270=West)
 * @param {number} radius - Outer radius in meters
 * @param {number} beamWidth - Beam width in degrees
 * @returns {Array} Array of [lon, lat] coordinate pairs forming the sector polygon
 */
export function createSectorCoordinates(lon, lat, azimuth, radius, beamWidth) {
  const points = [];
  
  // Start at center (site location)
  points.push([lon, lat]);
  
  const startAngle = azimuth - beamWidth / 2;
  const endAngle = azimuth + beamWidth / 2;
  
  // Create arc points (every 3 degrees for smooth curve)
  const step = 3;
  for (let angle = startAngle; angle <= endAngle; angle += step) {
    const point = calculatePointAtAngle(lon, lat, angle, radius);
    points.push(point);
  }
  
  // Ensure we include the exact end angle
  if ((endAngle - startAngle) % step !== 0) {
    const point = calculatePointAtAngle(lon, lat, endAngle, radius);
    points.push(point);
  }
  
  // Close polygon by returning to center
  points.push([lon, lat]);
  
  return points;
}

/**
 * Create ring sector polygon coordinates (donut slice)
 * Used when multiple cells share the same azimuth
 * @param {number} lon - Longitude of site (degrees)
 * @param {number} lat - Latitude of site (degrees)
 * @param {number} azimuth - Azimuth angle in degrees
 * @param {number} innerRadius - Inner radius in meters
 * @param {number} outerRadius - Outer radius in meters
 * @param {number} beamWidth - Beam width in degrees
 * @returns {Array} Array of [lon, lat] coordinate pairs forming the ring sector polygon
 */
export function createRingSectorCoordinates(lon, lat, azimuth, innerRadius, outerRadius, beamWidth) {
  const points = [];
  
  const startAngle = azimuth - beamWidth / 2;
  const endAngle = azimuth + beamWidth / 2;
  const step = 3;
  
  // If innerRadius is 0, create a regular sector from center
  if (innerRadius === 0) {
    return createSectorCoordinates(lon, lat, azimuth, outerRadius, beamWidth);
  }
  
  // Outer arc (from start to end)
  for (let angle = startAngle; angle <= endAngle; angle += step) {
    const point = calculatePointAtAngle(lon, lat, angle, outerRadius);
    points.push(point);
  }
  // Ensure exact end angle
  if ((endAngle - startAngle) % step !== 0) {
    points.push(calculatePointAtAngle(lon, lat, endAngle, outerRadius));
  }
  
  // Inner arc (from end back to start)
  for (let angle = endAngle; angle >= startAngle; angle -= step) {
    const point = calculatePointAtAngle(lon, lat, angle, innerRadius);
    points.push(point);
  }
  // Ensure exact start angle
  if ((endAngle - startAngle) % step !== 0) {
    points.push(calculatePointAtAngle(lon, lat, startAngle, innerRadius));
  }
  
  // Close the polygon
  points.push(points[0]);
  
  return points;
}

/**
 * Calculate a point at a given angle and distance from origin
 * @param {number} lon - Origin longitude (degrees)
 * @param {number} lat - Origin latitude (degrees)
 * @param {number} azimuth - Azimuth angle in degrees (0=North, clockwise)
 * @param {number} distance - Distance in meters
 * @returns {Array} [longitude, latitude] of the calculated point
 */
export function calculatePointAtAngle(lon, lat, azimuth, distance) {
  // Convert azimuth to mathematical angle (0=East, counter-clockwise)
  const mathAngle = (90 - azimuth) * Math.PI / 180;
  
  // Calculate offsets in meters
  const dx = distance * Math.cos(mathAngle); // East-West offset
  const dy = distance * Math.sin(mathAngle); // North-South offset
  
  // Convert meters to degrees
  const metersPerDegreeLat = 111320;
  const metersPerDegreeLon = 111320 * Math.cos(lat * Math.PI / 180);
  
  const dLon = dx / metersPerDegreeLon;
  const dLat = dy / metersPerDegreeLat;
  
  return [lon + dLon, lat + dLat];
}

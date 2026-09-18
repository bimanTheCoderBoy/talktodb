/**
 * Cell sector geometry utilities.
 * Duplicated from acss_module/utils/cellUtils.js to keep map_primitives_ol
 * self-contained. When a shared lib is created later, both can import from it.
 */

// Constants
const BASE_RADIUS = 40;
const MAX_RADIUS = 80;
const MIN_BEAM_WIDTH = 10;
const MAX_BEAM_WIDTH = 65;

// Band colors
const BAND_COLORS = {
  700: '#E53935', 800: '#FB8C00', 850: '#F57C00', 900: '#FF9800',
  1800: '#FDD835', 1900: '#FFEB3B', 2100: '#43A047', 2250: '#1E88E5',
  2300: '#1976D2', 2600: '#8E24AA', 3500: '#7B1FA2', 3700: '#6A1B9A',
};

function parseBandFrequency(band) {
  if (typeof band === 'number') return band;
  const match = String(band).match(/(\d{3,4})/);
  return match ? parseInt(match[1], 10) : 2100;
}

export function getBandColor(band) {
  const n = parseBandFrequency(band);
  if (BAND_COLORS[n]) return BAND_COLORS[n];
  const bands = Object.keys(BAND_COLORS).map(Number).sort((a, b) => a - b);
  let closest = bands[0], minDiff = Math.abs(n - closest);
  for (const b of bands) {
    const d = Math.abs(n - b);
    if (d < minDiff) { minDiff = d; closest = b; }
  }
  return BAND_COLORS[closest] || '#757575';
}

function getBandRadius(band) {
  const n = parseBandFrequency(band);
  const clamped = Math.max(700, Math.min(3700, n));
  const t = (clamped - 700) / (3700 - 700);
  return MAX_RADIUS - t * (MAX_RADIUS - BASE_RADIUS);
}

export function calculateBeamWidth(cells) {
  const unique = [...new Set(cells.map(c => c.azimuth))];
  if (unique.length === 0) return MAX_BEAM_WIDTH;
  return Math.max(MIN_BEAM_WIDTH, Math.min(MAX_BEAM_WIDTH, 360 / unique.length));
}

export function groupCellsByAzimuth(cells) {
  const grouped = {};
  cells.forEach(cell => {
    const key = cell.azimuth;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(cell);
  });
  Object.keys(grouped).forEach(key => {
    grouped[key].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  });
  return grouped;
}

export function calculateRingRadii(cellsAtAzimuth) {
  const radiiMap = new Map();
  if (cellsAtAzimuth.length === 0) return radiiMap;

  const minBand = Math.min(...cellsAtAzimuth.map(c => parseBandFrequency(c.band)));
  const totalRadius = getBandRadius(minBand);

  if (cellsAtAzimuth.length === 1) {
    radiiMap.set(cellsAtAzimuth[0].cell_iid, { innerRadius: 0, outerRadius: totalRadius });
    return radiiMap;
  }

  const sorted = [...cellsAtAzimuth].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  const n = sorted.length;
  sorted.forEach((cell, i) => {
    radiiMap.set(cell.cell_iid, {
      innerRadius: totalRadius * Math.sqrt(i / n),
      outerRadius: totalRadius * Math.sqrt((i + 1) / n),
    });
  });
  return radiiMap;
}

function calculatePointAtAngle(lon, lat, azimuth, distance) {
  const mathAngle = (90 - azimuth) * Math.PI / 180;
  const dx = distance * Math.cos(mathAngle);
  const dy = distance * Math.sin(mathAngle);
  const mPerDegLat = 111320;
  const mPerDegLon = 111320 * Math.cos(lat * Math.PI / 180);
  return [lon + dx / mPerDegLon, lat + dy / mPerDegLat];
}

function createSectorCoordinates(lon, lat, azimuth, radius, beamWidth, stepDeg = 3) {
  const pts = [[lon, lat]];
  const start = azimuth - beamWidth / 2;
  const end = azimuth + beamWidth / 2;
  const step = stepDeg;
  for (let a = start; a <= end; a += step) pts.push(calculatePointAtAngle(lon, lat, a, radius));
  if ((end - start) % step !== 0) pts.push(calculatePointAtAngle(lon, lat, end, radius));
  pts.push([lon, lat]);
  return pts;
}

export function createRingSectorCoordinates(lon, lat, azimuth, innerRadius, outerRadius, beamWidth, stepDeg = 3) {
  if (innerRadius === 0) return createSectorCoordinates(lon, lat, azimuth, outerRadius, beamWidth, stepDeg);

  const pts = [];
  const start = azimuth - beamWidth / 2;
  const end = azimuth + beamWidth / 2;
  const step = stepDeg;

  for (let a = start; a <= end; a += step) pts.push(calculatePointAtAngle(lon, lat, a, outerRadius));
  if ((end - start) % step !== 0) pts.push(calculatePointAtAngle(lon, lat, end, outerRadius));

  for (let a = end; a >= start; a -= step) pts.push(calculatePointAtAngle(lon, lat, a, innerRadius));
  if ((end - start) % step !== 0) pts.push(calculatePointAtAngle(lon, lat, start, innerRadius));

  pts.push(pts[0]);
  return pts;
}

/**
 * Cell/Site Geometry Utilities
 *
 * Handles cell sector geometry creation, band-based coloring and radius calculation,
 * and beamwidth computation based on unique azimuths per site.
 */

export const BASE_RADIUS = 40;
export const MAX_RADIUS = 80;
export const MIN_BEAM_WIDTH = 10;
export const MAX_BEAM_WIDTH = 65;

const KNOWN_BANDS = [700, 800, 850, 900, 1800, 1900, 2100, 2250, 2300, 2600, 3500, 3700];

export function parseBandFrequency(band) {
  if (typeof band === 'number') return band;
  const match = String(band).match(/(\d{3,4})/);
  return match ? parseInt(match[1], 10) : 2100;
}

const BAND_COLORS = {
  700: '#E53935',
  800: '#FB8C00',
  850: '#F57C00',
  900: '#FF9800',
  1800: '#FDD835',
  1900: '#FFEB3B',
  2100: '#43A047',
  2250: '#1E88E5',
  2300: '#1976D2',
  2600: '#8E24AA',
  3500: '#7B1FA2',
  3700: '#6A1B9A',
};

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

export function getBandRadius(band) {
  const n = parseBandFrequency(band);
  const minFreq = 700;
  const maxFreq = 3700;
  const clampedBand = Math.max(minFreq, Math.min(maxFreq, n));
  const t = (clampedBand - minFreq) / (maxFreq - minFreq);
  return MAX_RADIUS - t * (MAX_RADIUS - BASE_RADIUS);
}

export function calculateBeamWidth(cells) {
  const uniqueAzimuths = [...new Set(cells.map((c) => c.azimuth))];
  const count = uniqueAzimuths.length;
  if (count === 0) return MAX_BEAM_WIDTH;
  return Math.max(MIN_BEAM_WIDTH, Math.min(MAX_BEAM_WIDTH, 360 / count));
}

export function groupCellsByAzimuth(cells) {
  const grouped = {};

  cells.forEach((cell) => {
    const key = cell.azimuth;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(cell);
  });

  Object.keys(grouped).forEach((key) => {
    grouped[key].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  });

  return grouped;
}

export function calculateRingRadii(cellsAtAzimuth) {
  const radiiMap = new Map();
  if (cellsAtAzimuth.length === 0) return radiiMap;

  const minBand = Math.min(...cellsAtAzimuth.map((c) => parseBandFrequency(c.band)));
  const totalRadius = getBandRadius(minBand);

  if (cellsAtAzimuth.length === 1) {
    const cell = cellsAtAzimuth[0];
    radiiMap.set(cell.cell_iid, { innerRadius: 0, outerRadius: totalRadius });
    return radiiMap;
  }

  const sorted = [...cellsAtAzimuth].sort((a, b) => parseBandFrequency(b.band) - parseBandFrequency(a.band));
  const n = sorted.length;

  sorted.forEach((cell, index) => {
    const innerRadius = totalRadius * Math.sqrt(index / n);
    const outerRadius = totalRadius * Math.sqrt((index + 1) / n);
    radiiMap.set(cell.cell_iid, { innerRadius, outerRadius });
  });

  return radiiMap;
}

export function calculatePointAtAngle(lon, lat, azimuth, distance) {
  const mathAngle = ((90 - azimuth) * Math.PI) / 180;
  const dx = distance * Math.cos(mathAngle);
  const dy = distance * Math.sin(mathAngle);

  const metersPerDegreeLat = 111320;
  const metersPerDegreeLon = 111320 * Math.cos((lat * Math.PI) / 180);

  return [lon + dx / metersPerDegreeLon, lat + dy / metersPerDegreeLat];
}

export function createSectorCoordinates(lon, lat, azimuth, radius, beamWidth, stepDeg = 3) {
  const points = [[lon, lat]];
  const startAngle = azimuth - beamWidth / 2;
  const endAngle = azimuth + beamWidth / 2;
  const step = stepDeg;

  for (let angle = startAngle; angle <= endAngle; angle += step) {
    points.push(calculatePointAtAngle(lon, lat, angle, radius));
  }

  if ((endAngle - startAngle) % step !== 0) {
    points.push(calculatePointAtAngle(lon, lat, endAngle, radius));
  }

  points.push([lon, lat]);
  return points;
}

export function createRingSectorCoordinates(lon, lat, azimuth, innerRadius, outerRadius, beamWidth, stepDeg = 3) {
  if (innerRadius === 0) {
    return createSectorCoordinates(lon, lat, azimuth, outerRadius, beamWidth, stepDeg);
  }

  const points = [];
  const startAngle = azimuth - beamWidth / 2;
  const endAngle = azimuth + beamWidth / 2;
  const step = stepDeg;

  for (let angle = startAngle; angle <= endAngle; angle += step) {
    points.push(calculatePointAtAngle(lon, lat, angle, outerRadius));
  }
  if ((endAngle - startAngle) % step !== 0) {
    points.push(calculatePointAtAngle(lon, lat, endAngle, outerRadius));
  }

  for (let angle = endAngle; angle >= startAngle; angle -= step) {
    points.push(calculatePointAtAngle(lon, lat, angle, innerRadius));
  }
  if ((endAngle - startAngle) % step !== 0) {
    points.push(calculatePointAtAngle(lon, lat, startAngle, innerRadius));
  }

  points.push(points[0]);
  return points;
}

export function getUniqueBands(cells) {
  return [...new Set(cells.map((c) => c.band))].sort((a, b) => parseBandFrequency(a) - parseBandFrequency(b));
}

export function getUniqueTechnologies(cells) {
  return [...new Set(cells.map((c) => c.technology))].sort();
}

export function getCellIndexInAzimuthGroup(cell, cellsByAzimuth) {
  const group = cellsByAzimuth[cell.azimuth] || [];
  const index = group.findIndex((c) => c.cell_iid === cell.cell_iid);
  return { index: index >= 0 ? index : 0, total: group.length };
}

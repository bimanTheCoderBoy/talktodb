export function boundsIntersect(bounds1, bounds2) {
  return !(
    bounds1.east < bounds2.west ||
    bounds1.west > bounds2.east ||
    bounds1.north < bounds2.south ||
    bounds1.south > bounds2.north
  );
}

export function getPolygonBounds(polygonCoords) {
  const lons = polygonCoords.map((c) => c[0]);
  const lats = polygonCoords.map((c) => c[1]);
  return {
    west: Math.min(...lons),
    east: Math.max(...lons),
    south: Math.min(...lats),
    north: Math.max(...lats),
  };
}

/**
 * Calculate statistics for an array of decoded values.
 *
 * @param {number[]} values - Decoded sample values
 * @param {Array}    colorBands - [{min, label, color}, ...] sorted high-to-low from registry
 * @returns {Object} Statistics including dynamic qualityDistribution
 */
export function calculateStats(values, colorBands = []) {
  if (!values || values.length === 0) {
    return {
      count: 0,
      min: null, max: null, mean: null, median: null,
      stdDev: null, variance: null,
      percentiles: { p5: null, p25: null, p50: null, p75: null, p95: null },
      qualityDistribution: colorBands.map((b) => ({
        label: b.label, color: b.color, count: 0, percentage: 0,
      })),
    };
  }

  const sorted = [...values].sort((a, b) => a - b);
  const count = sorted.length;

  const min = sorted[0];
  const max = sorted[count - 1];
  const sum = sorted.reduce((acc, val) => acc + val, 0);
  const mean = sum / count;

  const median =
    count % 2 === 0
      ? (sorted[count / 2 - 1] + sorted[count / 2]) / 2
      : sorted[Math.floor(count / 2)];

  const squaredDiffs = sorted.map((val) => Math.pow(val - mean, 2));
  const variance = squaredDiffs.reduce((acc, val) => acc + val, 0) / count;
  const stdDev = Math.sqrt(variance);

  const getPercentile = (arr, p) => {
    if (!arr || arr.length === 0) return null;
    const index = (p / 100) * (arr.length - 1);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    if (lower === upper) return arr[lower];
    return arr[lower] * (upper - index) + arr[upper] * (index - lower);
  };

  const percentiles = {
    p5: getPercentile(sorted, 5),
    p25: getPercentile(sorted, 25),
    p50: getPercentile(sorted, 50),
    p75: getPercentile(sorted, 75),
    p95: getPercentile(sorted, 95),
  };

  const bandCounts = colorBands.map(() => 0);
  sorted.forEach((v) => {
    for (let i = 0; i < colorBands.length; i++) {
      if (v >= colorBands[i].min) {
        bandCounts[i]++;
        return;
      }
    }
    if (colorBands.length > 0) bandCounts[colorBands.length - 1]++;
  });

  const qualityDistribution = colorBands.map((band, i) => ({
    label: band.label,
    color: band.color,
    count: bandCounts[i],
    percentage: (bandCounts[i] / count) * 100,
  }));

  return {
    count, min, max, mean, median,
    stdDev, variance,
    percentiles,
    qualityDistribution,
  };
}

export function pointInPolygon(x, y, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function geoToPixel(lon, lat, bounds, width, height) {
  const x = ((lon - bounds.west) / (bounds.east - bounds.west)) * width;
  const y = ((bounds.north - lat) / (bounds.north - bounds.south)) * height;
  return { x: Math.floor(x), y: Math.floor(y) };
}

export function pixelToGeo(x, y, bounds, width, height) {
  const lon = bounds.west + (x / width) * (bounds.east - bounds.west);
  const lat = bounds.north - (y / height) * (bounds.north - bounds.south);
  return { lon, lat };
}

export function getPixelsInPolygon(decodedValues, imageWidth, imageHeight, imageBounds, polygonCoords) {
  const values = [];

  const polygonBounds = getPolygonBounds(polygonCoords);
  if (!boundsIntersect(polygonBounds, imageBounds)) return values;

  const startPixel = geoToPixel(polygonBounds.west, polygonBounds.north, imageBounds, imageWidth, imageHeight);
  const endPixel = geoToPixel(polygonBounds.east, polygonBounds.south, imageBounds, imageWidth, imageHeight);

  const startX = Math.max(0, Math.floor(startPixel.x));
  const startY = Math.max(0, Math.floor(startPixel.y));
  const endX = Math.min(imageWidth - 1, Math.ceil(endPixel.x));
  const endY = Math.min(imageHeight - 1, Math.ceil(endPixel.y));

  const pixelCount = (endX - startX) * (endY - startY);
  const step = pixelCount > 100000 ? Math.ceil(Math.sqrt(pixelCount / 50000)) : 1;

  for (let y = startY; y <= endY; y += step) {
    for (let x = startX; x <= endX; x += step) {
      const geo = pixelToGeo(x, y, imageBounds, imageWidth, imageHeight);

      if (pointInPolygon(geo.lon, geo.lat, polygonCoords)) {
        const val = decodedValues[y * imageWidth + x];
        if (!isNaN(val)) {
          values.push(val);
        }
      }
    }
  }

  return values;
}

export function calculatePolygonArea(coords) {
  if (coords.length < 3) return 0;
  const R = 6371;
  const toRad = (deg) => (deg * Math.PI) / 180;
  let total = 0;

  for (let i = 0; i < coords.length; i++) {
    const j = (i + 1) % coords.length;
    const lon1 = toRad(coords[i][0]);
    const lat1 = toRad(coords[i][1]);
    const lon2 = toRad(coords[j][0]);
    const lat2 = toRad(coords[j][1]);
    total += (lon2 - lon1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }

  return Math.abs((total * R * R) / 2);
}

export function formatStats(stats, unit = 'dBm') {
  if (!stats || stats.count === 0) {
    return { isEmpty: true };
  }

  return {
    isEmpty: false,
    count: stats.count.toLocaleString(),
    min: `${stats.min.toFixed(2)} ${unit}`,
    max: `${stats.max.toFixed(2)} ${unit}`,
    mean: `${stats.mean.toFixed(2)} ${unit}`,
    median: `${stats.median.toFixed(2)} ${unit}`,
    stdDev: `${stats.stdDev.toFixed(2)} ${unit}`,
    range: `${(stats.max - stats.min).toFixed(2)} ${unit}`,
    percentiles: {
      p5: `${stats.percentiles.p5.toFixed(2)} ${unit}`,
      p25: `${stats.percentiles.p25.toFixed(2)} ${unit}`,
      p50: `${stats.percentiles.p50.toFixed(2)} ${unit}`,
      p75: `${stats.percentiles.p75.toFixed(2)} ${unit}`,
      p95: `${stats.percentiles.p95.toFixed(2)} ${unit}`,
    },
    quality: stats.qualityDistribution.map((entry) => ({
      label: entry.label,
      color: entry.color,
      value: `${entry.percentage.toFixed(1)}%`,
    })),
  };
}

export function countCellsInPolygon(cellsData, polygonCoords) {
  if (!cellsData || !Array.isArray(cellsData) || cellsData.length === 0) {
    return { sites: 0, cells: 0, byBand: {}, byTechnology: {}, cellsList: [] };
  }

  let sitesCount = 0;
  let cellsCount = 0;
  const byBand = {};
  const byTechnology = {};
  const cellsList = [];

  cellsData.forEach((site) => {
    const { longitude, latitude, cells } = site;

    if (pointInPolygon(longitude, latitude, polygonCoords)) {
      sitesCount++;
      if (cells && Array.isArray(cells)) {
        cells.forEach((cell) => {
          cellsCount++;
          cellsList.push({
            cell_iid: cell.cell_iid,
            site_iid: site.site_iid,
            band: cell.band,
            technology: cell.technology,
            azimuth: cell.azimuth,
            pci: cell.pci,
          });
          const bandKey = `${cell.band} MHz`;
          byBand[bandKey] = (byBand[bandKey] || 0) + 1;
          const tech = cell.technology || 'Unknown';
          byTechnology[tech] = (byTechnology[tech] || 0) + 1;
        });
      }
    }
  });

  return { sites: sitesCount, cells: cellsCount, byBand, byTechnology, cellsList };
}

export function statsToCSV(stats, polygonName = 'Polygon', unit = 'dBm') {
  if (!stats || stats.count === 0) return 'No data available';

  const lines = [
    'Metric,Value,Unit',
    `Polygon Name,${polygonName},`,
    `Sample Count,${stats.count},pixels`,
    `Minimum,${stats.min.toFixed(2)},${unit}`,
    `Maximum,${stats.max.toFixed(2)},${unit}`,
    `Mean,${stats.mean.toFixed(2)},${unit}`,
    `Median,${stats.median.toFixed(2)},${unit}`,
    `Standard Deviation,${stats.stdDev.toFixed(2)},${unit}`,
    `5th Percentile,${stats.percentiles.p5.toFixed(2)},${unit}`,
    `25th Percentile,${stats.percentiles.p25.toFixed(2)},${unit}`,
    `75th Percentile,${stats.percentiles.p75.toFixed(2)},${unit}`,
    `95th Percentile,${stats.percentiles.p95.toFixed(2)},${unit}`,
  ];

  if (Array.isArray(stats.qualityDistribution)) {
    stats.qualityDistribution.forEach((entry) => {
      lines.push(`${entry.label},${entry.percentage.toFixed(1)},%`);
    });
  }

  return lines.join('\n');
}

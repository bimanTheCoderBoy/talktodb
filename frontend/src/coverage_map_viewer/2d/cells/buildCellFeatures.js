import Feature from 'ol/Feature';
import Polygon from 'ol/geom/Polygon';
import Point from 'ol/geom/Point';
import { fromLonLat } from 'ol/proj';
import {
  getBandColor,
  calculateBeamWidth,
  groupCellsByAzimuth,
  calculateRingRadii,
  createSectorCoordinates,
  createRingSectorCoordinates,
} from './cellGeometry';

/** Match ACSS MapView: baseline red, ASP-added (saved candidates) green. */
const BASELINE_SITE_COLOR = '#B71C1C';
const CANDIDATE_SITE_COLOR = '#2E7D32';

/**
 * Build OL Features from cells data with active-band filter + zoom LOD mode.
 *
 * @param {Array} cellsData - Array of site objects with { longitude, latitude, cells, is_candidate? }
 * @param {Set|null} activeBands - Set of band strings from visible raster layers.
 * @param {Object} options
 * @param {'site'|'simplified'|'full'} options.renderMode
 * @returns {Feature[]} OL features ready to add to a VectorSource
 */
export function buildCellFeatures(cellsData, activeBands, options = {}) {
  const { renderMode = 'full' } = options;
  const features = [];

  const noFilter = !activeBands || activeBands.size === 0;
  const showAll = noFilter ||[...activeBands].some((b) =>
    String(b).toLowerCase().includes('all carriers')
  );
  const validActiveBands = !showAll
    ? new Set([...activeBands].map((b) => String(b).trim()))
    : null;

  cellsData.forEach((site) => {
    const { longitude, latitude, cells } = site;
    if (!cells || cells.length === 0) return;

    // const filteredCells = showAll
    //   ? cells
    //   : cells.filter((c) => validActiveBands.has(String(c.band).trim()));
    const filteredCells = showAll
    ? cells
    : cells.filter((c) => [...validActiveBands].some((b) => b.includes(String(c.band))));

    if (filteredCells.length === 0) return;

    const fullCellsByAzimuth = groupCellsByAzimuth(filteredCells);

    if (renderMode === 'site') {
      features.push(createSiteFeature(site, fullCellsByAzimuth));
      return;
    }

    const beamWidth = calculateBeamWidth(filteredCells);
    const stepDeg = renderMode === 'simplified' ? 12 : 3;

    Object.entries(fullCellsByAzimuth).forEach(([azimuth, cellsAtAzimuth]) => {
      if (renderMode === 'simplified') {
        const summaryColor = getBandColor(cellsAtAzimuth[0]?.band);
        const totalRadius = getOuterRadiusForAzimuth(cellsAtAzimuth);
        const coords = createSectorCoordinates(
          longitude,
          latitude,
          parseFloat(azimuth),
          totalRadius,
          beamWidth,
          stepDeg
        );

        const feature = new Feature({
          geometry: new Polygon([coords.map((coord) => fromLonLat(coord))]),
          featureType: 'azimuthSummary',
          siteData: site,
          azimuth: parseFloat(azimuth),
          cellsByAzimuth: fullCellsByAzimuth,
          renderColor: summaryColor,
          renderFillColor: withAlpha(summaryColor, 0.35),
          renderStrokeColor: summaryColor,
          renderStrokeWidth: 1.2,
        });

        features.push(feature);
        return;
      }

      const ringRadii = calculateRingRadii(cellsAtAzimuth);

      cellsAtAzimuth.forEach((cell) => {
        const radii = ringRadii.get(cell.cell_iid);
        if (!radii) return;

        const { innerRadius, outerRadius } = radii;

        const coords = createRingSectorCoordinates(
          longitude,
          latitude,
          parseFloat(azimuth),
          innerRadius,
          outerRadius,
          beamWidth,
          stepDeg
        );

        const transformedCoords = coords.map((coord) => fromLonLat(coord));
        const color = getBandColor(cell.band);

        const feature = new Feature({
          geometry: new Polygon([transformedCoords]),
          featureType: 'cell',
          cellData: cell,
          siteData: site,
          cellsByAzimuth: fullCellsByAzimuth,
          renderColor: color,
          renderFillColor: withAlpha(color, 0.44),
          renderStrokeColor: color,
          renderStrokeWidth: 1.5,
        });

        features.push(feature);
      });
    });

    features.push(createSiteFeature(site, fullCellsByAzimuth));
  });

  return features;
}

function createSiteFeature(site, cellsByAzimuth) {
  const siteColor = site.is_candidate ? CANDIDATE_SITE_COLOR : BASELINE_SITE_COLOR;
  return new Feature({
    geometry: new Point(fromLonLat([site.longitude, site.latitude])),
    featureType: 'site',
    siteData: site,
    cellsByAzimuth,
    renderColor: siteColor,
    renderFillColor: siteColor,
    renderStrokeColor: '#FFFFFF',
    renderStrokeWidth: 1.8,
    renderPointRadius: 5,
  });
}

function getOuterRadiusForAzimuth(cellsAtAzimuth) {
  const ringRadii = calculateRingRadii(cellsAtAzimuth);
  let outer = 0;
  ringRadii.forEach((v) => {
    if (v.outerRadius > outer) outer = v.outerRadius;
  });
  return outer || 60;
}

function withAlpha(hexColor, alpha) {
  const hex = String(hexColor || '').replace('#', '');
  if (hex.length !== 6) return hexColor;
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

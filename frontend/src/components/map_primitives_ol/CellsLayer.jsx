import { useEffect, useRef, useState } from 'react';
import WebGLVectorLayer from 'ol/layer/WebGLVector';
import VectorSource from 'ol/source/Vector';
import Feature from 'ol/Feature';
import OlPolygon from 'ol/geom/Polygon';
import Point from 'ol/geom/Point';
import { fromLonLat } from 'ol/proj';
import { useMap } from './MapContext';
import { LAYER_Z_INDEX } from './layerOrder';
import {
  getBandColor,
  calculateBeamWidth,
  createRingSectorCoordinates,
  groupCellsByAzimuth,
  calculateRingRadii,
} from './utils/cellSectors';

const UNSELECTED_COLOR = '#757575';

function getRenderModeFromZoom(zoom) {
  if (zoom < 8) return 'site';
  if (zoom < 12) return 'simplified';
  return 'full';
}

function withAlpha(hexColor, alpha) {
  const hex = String(hexColor || '').replace('#', '');
  if (hex.length !== 6) return hexColor;
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function maxOuterRadius(cellsAtAz) {
  const ringRadii = calculateRingRadii(cellsAtAz);
  let outer = 0;
  ringRadii.forEach((r) => {
    if (r.outerRadius > outer) outer = r.outerRadius;
  });
  return outer || 60;
}

function createSiteMarkerFeature(site, siteMarkerColor) {
  return new Feature({
    geometry: new Point(fromLonLat([site.longitude, site.latitude])),
    featureType: 'site',
    siteData: site,
    renderFillColor: siteMarkerColor,
    renderStrokeColor: '#FFFFFF',
    renderStrokeWidth: 1.8,
    renderPointRadius: 5,
  });
}

function buildSiteFeatures(site, siteMarkerColor, showSelectionState = false, renderMode = 'full') {
  const features = [];
  const { longitude, latitude, cells } = site;
  if (!cells || cells.length === 0 || longitude == null || latitude == null) return features;

  if (renderMode === 'site') {
    features.push(createSiteMarkerFeature(site, siteMarkerColor));
    return features;
  }

  const beamWidth = calculateBeamWidth(cells);
  const cellsByAzimuth = groupCellsByAzimuth(cells);
  const stepDeg = renderMode === 'simplified' ? 12 : 3;

  Object.entries(cellsByAzimuth).forEach(([azimuth, cellsAtAz]) => {
    if (renderMode === 'simplified') {
      const color = getBandColor(cellsAtAz[0]?.band);
      const coords = createRingSectorCoordinates(
        longitude,
        latitude,
        parseFloat(azimuth),
        0,
        maxOuterRadius(cellsAtAz),
        beamWidth,
        stepDeg
      );
      const feature = new Feature({
        geometry: new OlPolygon([coords.map(c => fromLonLat(c))]),
        featureType: 'sectorSummary',
        siteData: site,
        renderFillColor: withAlpha(color, 0.32),
        renderStrokeColor: color,
        renderStrokeWidth: 1.2,
      });
      features.push(feature);
      return;
    }

    const ringRadii = calculateRingRadii(cellsAtAz);

    cellsAtAz.forEach(cell => {
      const radii = ringRadii.get(cell.cell_iid);
      if (!radii) return;

      const coords = createRingSectorCoordinates(
        longitude, latitude,
        parseFloat(azimuth),
        radii.innerRadius, radii.outerRadius,
        beamWidth,
        stepDeg,
      );

      const projected = coords.map(c => fromLonLat(c));
      const feature = new Feature({
        geometry: new OlPolygon([projected]),
        featureType: 'cell',
        cellData: cell,
        siteData: site,
      });
      const selected = showSelectionState ? (cell.selected !== false) : true;
      const color = selected ? getBandColor(cell.band) : UNSELECTED_COLOR;
      feature.set('renderFillColor', withAlpha(color, 0.44));
      feature.set('renderStrokeColor', color);
      feature.set('renderStrokeWidth', 1.5);
      features.push(feature);
    });
  });

  features.push(createSiteMarkerFeature(site, siteMarkerColor));

  return features;
}

/**
 * Renders selected sites/cells as ring sectors + site markers.
 * Updates incrementally: only rebuilds features for sites whose reference changed.
 *
 * Props:
 *  - data     : array of { site_iid, longitude, latitude, cells: [...] }
 *  - visible  : boolean
 *  - opacity  : 0–1
 *  - siteMarkerColor : hex string
 */
function CellsLayer({
  data,
  visible = true,
  opacity = 1,
  siteMarkerColor = '#B71C1C',
  showSelectionState = false,
}) {
  const map = useMap();
  const [renderMode, setRenderMode] = useState('full');
  const layerRef = useRef(null);
  const sourceRef = useRef(null);
  const prevSiteMapRef = useRef(new Map());
  const featuresBySiteRef = useRef(new Map());
  const rafIdRef = useRef(null);
  const buildSignatureRef = useRef('');

  useEffect(() => {
    if (!map) return;
    sourceRef.current = new VectorSource();
    layerRef.current = new WebGLVectorLayer({
      source: sourceRef.current,
      zIndex: LAYER_Z_INDEX.CELLS,
      style: [
        {
          filter: ['==', ['get', 'featureType'], 'cell'],
          style: {
            'fill-color': ['get', 'renderFillColor'],
            'stroke-color': ['get', 'renderStrokeColor'],
            'stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
        {
          filter: ['==', ['get', 'featureType'], 'sectorSummary'],
          style: {
            'fill-color': ['get', 'renderFillColor'],
            'stroke-color': ['get', 'renderStrokeColor'],
            'stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
        {
          filter: ['==', ['get', 'featureType'], 'site'],
          style: {
            'circle-radius': ['get', 'renderPointRadius'],
            'circle-fill-color': ['get', 'renderFillColor'],
            'circle-stroke-color': ['get', 'renderStrokeColor'],
            'circle-stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
      ],
    });
    map.addLayer(layerRef.current);

    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
      if (map && layerRef.current) map.removeLayer(layerRef.current);
      layerRef.current = null;
      sourceRef.current = null;
      prevSiteMapRef.current = new Map();
      featuresBySiteRef.current = new Map();
    };
  }, [map]);

  useEffect(() => {
    if (!map) return undefined;
    const view = map.getView();
    if (!view) return undefined;

    const syncMode = () => {
      const next = getRenderModeFromZoom(view.getZoom() ?? 3);
      setRenderMode((prev) => (prev === next ? prev : next));
    };

    syncMode();
    view.on('change:resolution', syncMode);
    return () => view.un('change:resolution', syncMode);
  }, [map]);

  useEffect(() => {
    if (layerRef.current) layerRef.current.setVisible(visible);
  }, [visible]);
  useEffect(() => {
    if (layerRef.current) layerRef.current.setOpacity(opacity);
  }, [opacity]);

  useEffect(() => {
    if (!sourceRef.current) return;

    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    rafIdRef.current = requestAnimationFrame(() => {
      const source = sourceRef.current;
      if (!source) return;

      const buildSignature = `${renderMode}|${siteMarkerColor}|${showSelectionState}`;
      if (buildSignatureRef.current !== buildSignature) {
        source.clear();
        prevSiteMapRef.current = new Map();
        featuresBySiteRef.current = new Map();
        buildSignatureRef.current = buildSignature;
      }

      const prevMap = prevSiteMapRef.current;
      const featMap = featuresBySiteRef.current;

      const newMap = new Map();
      if (data) {
        for (let i = 0; i < data.length; i++) {
          const site = data[i];
          if (site && site.site_iid != null) {
            newMap.set(site.site_iid, site);
          }
        }
      }

      for (const [siteId] of prevMap) {
        if (!newMap.has(siteId)) {
          const old = featMap.get(siteId);
          if (old) {
            for (let i = 0; i < old.length; i++) source.removeFeature(old[i]);
            featMap.delete(siteId);
          }
        }
      }

      for (const [siteId, site] of newMap) {
        if (prevMap.get(siteId) === site) continue;

        const old = featMap.get(siteId);
        if (old) {
          for (let i = 0; i < old.length; i++) source.removeFeature(old[i]);
        }

        const fresh = buildSiteFeatures(site, siteMarkerColor, showSelectionState, renderMode);
        source.addFeatures(fresh);
        featMap.set(siteId, fresh);
      }

      prevSiteMapRef.current = newMap;
    });
  }, [data, siteMarkerColor, showSelectionState, renderMode]);

  return null;
}

export default CellsLayer;

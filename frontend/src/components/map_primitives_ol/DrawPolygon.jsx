import { useEffect, useRef, useCallback } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Draw from 'ol/interaction/Draw';
import Modify from 'ol/interaction/Modify';
import Feature from 'ol/Feature';
import OlPolygon from 'ol/geom/Polygon';
import { Style, Stroke, Fill } from 'ol/style';
import { fromLonLat, toLonLat } from 'ol/proj';
import { useMap } from './MapContext';
import { LAYER_Z_INDEX } from './layerOrder';
import { ensureClosedRing } from './utils/geom';

const DRAW_STYLE = new Style({
  stroke: new Stroke({ color: '#1d4a91', width: 2 }),
  fill: new Fill({ color: 'rgba(29, 74, 145, 0.2)' }),
});

/**
 * Draw + Modify polygon interaction.
 *
 * Props:
 *  - enabled        : boolean — whether drawing is active
 *  - initialPolygon : [[lon,lat],...] or null — polygon to pre-load for editing
 *  - onChange(ring)  : called with WGS84 ring after draw-end / modify-end
 *  - onDelete()     : called when the polygon is cleared (optional, for parent notification)
 *  - onClear()      : legacy callback (kept for compat)
 */
function DrawPolygon({ enabled = false, initialPolygon = null, onChange, onDelete, onClear }) {
  const map = useMap();
  const sourceRef = useRef(null);
  const layerRef = useRef(null);
  const drawRef = useRef(null);
  const modifyRef = useRef(null);
  const initialAppliedRef = useRef(false);

  /** Extract WGS84 ring from the first feature in source */
  const emitRing = useCallback(() => {
    if (!sourceRef.current || !onChange) return;
    const features = sourceRef.current.getFeatures();
    if (features.length === 0) return;
    const geom = features[0].getGeometry();
    const coords = geom.getCoordinates()[0];
    const ring = ensureClosedRing(coords.map(c => toLonLat(c)));
    onChange(ring);
  }, [onChange]);

  // ── helpers to add/remove Draw ──
  const addDraw = useCallback(() => {
    if (!map || !sourceRef.current || drawRef.current) return;

    const draw = new Draw({
      source: sourceRef.current,
      type: 'Polygon',
      style: DRAW_STYLE,
    });

    draw.on('drawend', () => {
      setTimeout(() => {
        emitRing();
        if (drawRef.current && map) {
          map.removeInteraction(drawRef.current);
          drawRef.current = null;
        }
      }, 50);
    });

    drawRef.current = draw;
    map.addInteraction(draw);
  }, [map, emitRing]);

  const removeDraw = useCallback(() => {
    if (drawRef.current && map) {
      map.removeInteraction(drawRef.current);
      drawRef.current = null;
    }
  }, [map]);

  // ── Create source + layer once ──
  useEffect(() => {
    if (!map) return;

    sourceRef.current = new VectorSource();
    layerRef.current = new VectorLayer({
      source: sourceRef.current,
      style: DRAW_STYLE,
      zIndex: LAYER_Z_INDEX.DRAW,
    });
    map.addLayer(layerRef.current);

    return () => {
      if (map && layerRef.current) {
        map.removeLayer(layerRef.current);
      }
      layerRef.current = null;
      sourceRef.current = null;
    };
  }, [map]);

  // ── Load initial polygon ──
  useEffect(() => {
    if (!sourceRef.current || !initialPolygon || initialPolygon.length < 3) return;
    if (initialAppliedRef.current) return;
    initialAppliedRef.current = true;

    const projected = initialPolygon.map(c => fromLonLat(c));
    const feature = new Feature({ geometry: new OlPolygon([projected]) });
    sourceRef.current.clear();
    sourceRef.current.addFeature(feature);

    removeDraw();
  }, [initialPolygon, removeDraw]);

  // ── Manage Draw interaction ──
  useEffect(() => {
    removeDraw();

    if (!enabled || !sourceRef.current) return;
    if (sourceRef.current.getFeatures().length > 0) return;

    addDraw();

    return () => removeDraw();
  }, [enabled, addDraw, removeDraw, initialPolygon]);

  // ── Manage Modify interaction ──
  useEffect(() => {
    if (!map || !sourceRef.current) return;

    if (modifyRef.current) {
      map.removeInteraction(modifyRef.current);
      modifyRef.current = null;
    }

    if (!enabled) return;

    const modify = new Modify({ source: sourceRef.current });
    modify.on('modifyend', () => emitRing());
    modifyRef.current = modify;
    map.addInteraction(modify);

    return () => {
      if (modifyRef.current && map) {
        map.removeInteraction(modifyRef.current);
        modifyRef.current = null;
      }
    };
  }, [map, enabled, emitRing]);

  // ── Clear when initialPolygon becomes null after being set ──
  useEffect(() => {
    if (initialPolygon === null && initialAppliedRef.current && sourceRef.current) {
      sourceRef.current.clear();
      initialAppliedRef.current = false;
    }
  }, [initialPolygon]);

  return null;
}

export default DrawPolygon;

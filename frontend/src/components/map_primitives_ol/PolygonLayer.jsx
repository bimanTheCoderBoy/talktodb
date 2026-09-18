import { useEffect, useRef } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Feature from 'ol/Feature';
import OlPolygon from 'ol/geom/Polygon';
import { Style, Stroke, Fill } from 'ol/style';
import { fromLonLat } from 'ol/proj';
import { useMap } from './MapContext';
import { LAYER_Z_INDEX } from './layerOrder';

/**
 * Display-only polygon overlay.
 *
 * Props:
 *  - polygonCoords: [[lon,lat], ...] WGS84 ring (or null)
 *  - strokeColor / fillColor: customisation
 *  - lineDash: array like [10, 8] for dashed stroke (null = solid)
 *  - strokeWidth: line width (default 2)
 *  - visible / opacity
 */
function PolygonLayer({
  polygonCoords,
  strokeColor = '#22c55e',
  fillColor = 'rgba(34, 197, 94, 0.20)',
  lineDash = null,
  strokeWidth = 2,
  visible = true,
  opacity = 1,
}) {
  const map = useMap();
  const layerRef = useRef(null);
  const sourceRef = useRef(null);

  // Create layer once
  useEffect(() => {
    if (!map) return;
    sourceRef.current = new VectorSource();
    layerRef.current = new VectorLayer({
      source: sourceRef.current,
      zIndex: LAYER_Z_INDEX.POLYGON,
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

  // Update style when color/dash props change
  useEffect(() => {
    if (!layerRef.current) return;
    const strokeOpts = { color: strokeColor, width: strokeWidth };
    if (lineDash) strokeOpts.lineDash = lineDash;
    layerRef.current.setStyle(
      new Style({
        stroke: new Stroke(strokeOpts),
        fill: new Fill({ color: fillColor }),
      }),
    );
  }, [strokeColor, fillColor, lineDash, strokeWidth]);

  // Visibility / opacity
  useEffect(() => {
    if (layerRef.current) layerRef.current.setVisible(visible);
  }, [visible]);
  useEffect(() => {
    if (layerRef.current) layerRef.current.setOpacity(opacity);
  }, [opacity]);

  // Update features
  useEffect(() => {
    if (!sourceRef.current) return;
    sourceRef.current.clear();

    if (!polygonCoords || polygonCoords.length < 3) return;

    const projected = polygonCoords.map(c => fromLonLat(c));
    const feature = new Feature({ geometry: new OlPolygon([projected]) });
    sourceRef.current.addFeature(feature);
  }, [polygonCoords]);

  return null;
}

export default PolygonLayer;

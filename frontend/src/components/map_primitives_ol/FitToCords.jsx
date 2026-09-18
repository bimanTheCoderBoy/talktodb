import { useEffect, useRef } from 'react';
import OlPolygon from 'ol/geom/Polygon';
import { fromLonLat } from 'ol/proj';
import { useMap } from './MapContext';

const DEFAULT_PADDING = [50, 50, 50, 50];

/**
 * Fits the map view to a polygon described by WGS84 coordinates.
 * Fits only once per unique cords reference (i.e., per project load).
 *
 * Props:
 *  - cords: [[lon, lat], ...] — the polygon ring to fit to
 *  - padding: [top, right, bottom, left] padding in px (default 50 all)
 *  - duration: animation ms (default 800)
 */
function FitToCords({ cords, padding = DEFAULT_PADDING, duration = 800 }) {
  const map = useMap();
  const lastFitCordsRef = useRef(null);

  useEffect(() => {
    if (!map || !cords || cords.length < 3) return;
    if (lastFitCordsRef.current === cords) return;
    lastFitCordsRef.current = cords;

    try {
      const projected = cords.map(c => fromLonLat(c));
      const polygon = new OlPolygon([projected]);
      map.getView().fit(polygon, { padding, duration, maxZoom: 18 });
    } catch (err) {
      console.error('FitToCords error:', err);
    }
  }, [map, cords, padding, duration]);

  return null;
}

export default FitToCords;

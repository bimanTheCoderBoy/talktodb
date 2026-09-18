import { useEffect, useRef } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Feature from 'ol/Feature';
import Polygon from 'ol/geom/Polygon';
import Point from 'ol/geom/Point';
import RegularShape from 'ol/style/RegularShape';
import { Style, Stroke, Fill, Circle as CircleStyle } from 'ol/style';
import { fromLonLat } from 'ol/proj';

import { useMap } from '../context/MapContext';
import { LAYER_Z_INDEX } from '../constants/layerOrder';
import {
  getBandColor,
  calculateBeamWidth,
  createRingSectorCoordinates,
  groupCellsByAzimuth,
  calculateRingRadii,
} from '../../../utils/cellUtils';

/**
 * siteMarkerType:
 *   'circle'  – default filled circle (baseline / saved candidates)
 *   'diamond' – rotated square diamond with glow stroke (GDL preview)
 */
function CellsLayer({ visible = true, opacity = 1, data, enabled = true, siteMarkerColor = '#B71C1C', zIndexKey = 'CELLS', siteMarkerType = 'circle' }) {
  const map = useMap();
  const layerRef = useRef(null);
  const sourceRef = useRef(null);

  // Create layer once on mount
  useEffect(() => {
    if (!map) return;

    sourceRef.current = new VectorSource();
    layerRef.current = new VectorLayer({
      source: sourceRef.current,
      zIndex: LAYER_Z_INDEX[zIndexKey] || LAYER_Z_INDEX.CELLS,
    });
    
    map.addLayer(layerRef.current);

    return () => {
      if (map && layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
        sourceRef.current = null;
      }
    };
  }, [map]);

  // Update visibility without recreating layer
  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.setVisible(visible && enabled);
    }
  }, [visible, enabled]);

  // Update opacity without recreating layer
  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.setOpacity(opacity);
    }
  }, [opacity]);

  // Update features when data changes
  useEffect(() => {
    if (!sourceRef.current) return;

    // Clear existing features
    sourceRef.current.clear();

    // Don't render if not enabled or no data
    if (!enabled || !data || data.length === 0) {
      return;
    }

    // Process each site
    data.forEach(site => {
      const { longitude, latitude, cells } = site;

      if (!cells || cells.length === 0 || longitude == null || latitude == null) return;

      // Calculate beamwidth based on unique azimuths
      const beamWidth = calculateBeamWidth(cells);

      // Group cells by azimuth
      const cellsByAzimuth = groupCellsByAzimuth(cells);

      // Process each azimuth group
      Object.entries(cellsByAzimuth).forEach(([azimuth, cellsAtAzimuth]) => {
        // Calculate ring radii for cells at this azimuth
        const ringRadii = calculateRingRadii(cellsAtAzimuth);

        // Draw each cell as a ring sector
        cellsAtAzimuth.forEach(cell => {
          const radii = ringRadii.get(cell.cell_iid);
          if (!radii) return;

          const { innerRadius, outerRadius } = radii;

          // Create ring sector coordinates
          const coords = createRingSectorCoordinates(
            longitude, latitude,
            parseFloat(azimuth),
            innerRadius,
            outerRadius,
            beamWidth
          );

          // Transform coordinates to map projection
          const transformedCoords = coords.map(coord => fromLonLat(coord));

          // Create polygon feature
          const feature = new Feature({
            geometry: new Polygon([transformedCoords]),
            featureType: 'cell',
            cellData: cell,
            siteData: site,
          });

          // Style based on band color
          const color = getBandColor(cell.band);
          feature.setStyle(new Style({
            fill: new Fill({ color: color + '70' }), // 44% opacity
            stroke: new Stroke({
              color: color,
              width: 2,
            }),
          }));

          sourceRef.current.addFeature(feature);
        });
      });

      // Draw site marker at center
      const siteFeature = new Feature({
        geometry: new Point(fromLonLat([longitude, latitude])),
        featureType: 'site',
        siteData: site,
      });

      // Site marker style — circle (default) or diamond (GDL preview)
      if (siteMarkerType === 'diamond') {
        // Diamond marker: rotated square with bright glow stroke
        siteFeature.setStyle([
          // Outer glow
          new Style({
            image: new RegularShape({
              points: 4,
              radius: 10,
              angle: Math.PI / 4,
              fill: new Fill({ color: siteMarkerColor + '40' }),
              stroke: new Stroke({ color: siteMarkerColor, width: 2 }),
            }),
          }),
          // Inner diamond
          new Style({
            image: new RegularShape({
              points: 4,
              radius: 6,
              angle: Math.PI / 4,
              fill: new Fill({ color: siteMarkerColor }),
              stroke: new Stroke({ color: '#FFFFFF', width: 1.5 }),
            }),
          }),
        ]);
      } else {
        siteFeature.setStyle(new Style({
          image: new CircleStyle({
            radius: 6,
            fill: new Fill({ color: siteMarkerColor }),
            stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
          }),
        }));
      }

      sourceRef.current.addFeature(siteFeature);
    });

  }, [data, enabled]);

  // This component doesn't render any DOM elements
  return null;
}

export default CellsLayer;

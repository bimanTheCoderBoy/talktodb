import { useEffect, useRef } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Feature from 'ol/Feature';
import Polygon from 'ol/geom/Polygon';
import { Style, Stroke, Fill } from 'ol/style';
import { fromLonLat } from 'ol/proj';

import { useMap } from '../context/MapContext';
import { LAYER_Z_INDEX } from '../constants/layerOrder';


function PolygonLayer({ 
  polygonVisible = true, 
  polygonOpacity = 1,
  boundaryVisible = true,
  boundaryOpacity = 0.5,
  polygonCoords,
  boundaryCoords,
  isPolygonDone = false,
}) {
  const map = useMap();
  
  // Polygon layer refs
  const polygonLayerRef = useRef(null);
  const polygonSourceRef = useRef(null);
  
  // Boundary layer refs
  const boundaryLayerRef = useRef(null);
  const boundarySourceRef = useRef(null);

  // Create layers once on mount
  useEffect(() => {
    if (!map) return;

    // Create boundary source and layer
    boundarySourceRef.current = new VectorSource();
    boundaryLayerRef.current = new VectorLayer({
      source: boundarySourceRef.current,
      style: new Style({
        stroke: new Stroke({
          color: '#3b82f6', // Blue
          width: 2,
          lineDash: [8, 4],
        }),
        fill: new Fill({
          color: 'rgba(59, 130, 246, 0.15)', // Light blue fill
        }),
      }),
      zIndex: LAYER_Z_INDEX.BOUNDARY,
    });

    // Create polygon source and layer
    polygonSourceRef.current = new VectorSource();
    polygonLayerRef.current = new VectorLayer({
      source: polygonSourceRef.current,
      style: new Style({
        stroke: new Stroke({
          color: '#6B7280',
          width: 2,
        }),
        fill: new Fill({
          color: 'rgba(156, 163, 175, 0.3)',
        }),
      }),
      zIndex: LAYER_Z_INDEX.POLYGON,
    });

    // Add layers to map
    map.addLayer(boundaryLayerRef.current);
    map.addLayer(polygonLayerRef.current);

    return () => {
      if (map) {
        if (boundaryLayerRef.current) {
          map.removeLayer(boundaryLayerRef.current);
          boundaryLayerRef.current = null;
          boundarySourceRef.current = null;
        }
        if (polygonLayerRef.current) {
          map.removeLayer(polygonLayerRef.current);
          polygonLayerRef.current = null;
          polygonSourceRef.current = null;
        }
      }
    };
  }, [map]);

  // Update polygon visibility
  useEffect(() => {
    if (polygonLayerRef.current) {
      polygonLayerRef.current.setVisible(polygonVisible);
    }
  }, [polygonVisible]);

  // Update polygon opacity
  useEffect(() => {
    if (polygonLayerRef.current) {
      polygonLayerRef.current.setOpacity(polygonOpacity);
    }
  }, [polygonOpacity]);

  // Update boundary visibility
  useEffect(() => {
    if (boundaryLayerRef.current) {
      boundaryLayerRef.current.setVisible(boundaryVisible);
    }
  }, [boundaryVisible]);

  // Update boundary opacity
  useEffect(() => {
    if (boundaryLayerRef.current) {
      boundaryLayerRef.current.setOpacity(boundaryOpacity);
    }
  }, [boundaryOpacity]);

  // Update polygon style when completion status changes
  useEffect(() => {
    if (!polygonLayerRef.current) return;

    polygonLayerRef.current.setStyle(
      new Style({
        stroke: new Stroke({
          color: isPolygonDone ? '#22c55e' : '#6B7280',
          width: isPolygonDone ? 3 : 2,
        }),
        fill: new Fill({
          color: isPolygonDone ? 'rgba(34, 197, 94, 0.25)' : 'rgba(156, 163, 175, 0.3)',
        }),
      })
    );
  }, [isPolygonDone]);

  // Draw boundary polygon when coordinates change
  useEffect(() => {
    if (!boundarySourceRef.current) return;

    // Clear existing boundary
    boundarySourceRef.current.clear();

    // Draw boundary if coords exist
    if (boundaryCoords && boundaryCoords.length > 2) {
      const boundaryFeature = new Feature({
        geometry: new Polygon([boundaryCoords.map(coord => fromLonLat(coord))]),
      });
      boundarySourceRef.current.addFeature(boundaryFeature);
    }
  }, [boundaryCoords]);

  // Draw main polygon when coordinates change
  useEffect(() => {
    if (!polygonSourceRef.current) return;

    // Clear existing polygon
    polygonSourceRef.current.clear();

    // Draw polygon if coords exist
    if (polygonCoords && polygonCoords.length > 2) {
      const polygonFeature = new Feature({
        geometry: new Polygon([polygonCoords.map(coord => fromLonLat(coord))]),
      });
      polygonSourceRef.current.addFeature(polygonFeature);
    }
  }, [polygonCoords]);

  // Expose source refs for drawing interaction (via callback or ref forwarding if needed)
  // For now, this component handles display only

  // This component doesn't render any DOM elements
  return null;
}

export default PolygonLayer;

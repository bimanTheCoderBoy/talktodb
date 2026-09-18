import React, { useEffect, useRef, useState } from 'react';
import OlMap from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import OSM from 'ol/source/OSM';
import MapContext from './MapContext';
import { LAYER_Z_INDEX } from './layerOrder';

/**
 * Generic OpenLayers map shell.
 * Creates an OL Map with an OSM base layer and provides the map instance
 * to children via MapContext.
 *
 * Props:
 *  - className / style: forwarded to the container div
 *  - children: OL child components that consume useMap()
 */
function MapShell({ className = '', style, children }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [mapInstance, setMapInstance] = useState(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const osmLayer = new TileLayer({
      source: new OSM(),
      zIndex: LAYER_Z_INDEX.OSM,
    });

    const map = new OlMap({
      target: containerRef.current,
      layers: [osmLayer],
      view: new View({
        center: [0, 0],
        zoom: 3,
        maxZoom: 19,
        minZoom: 2,
      }),
      controls: [],
    });

    mapRef.current = map;
    setMapInstance(map);

    return () => {
      map.setTarget(null);
      mapRef.current = null;
      setMapInstance(null);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: '100%', height: '100%', ...style }}
    >
      {mapInstance && (
        <MapContext.Provider value={mapInstance}>
          {children}
        </MapContext.Provider>
      )}
    </div>
  );
}

export default MapShell;

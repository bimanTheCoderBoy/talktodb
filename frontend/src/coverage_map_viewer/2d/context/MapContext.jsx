import React, { createContext, useContext, useState, useRef, useCallback, useMemo } from 'react';
import View from 'ol/View';
import VectorSource from 'ol/source/Vector';
import { fromLonLat } from 'ol/proj';

const MapContext = createContext(null);

export function MapProvider({ children, initialDataPath }) {

  // ─── Multi-map support ───
  const [viewMode, setViewMode] = useState('single');

  const sharedViewRef = useRef(new View({
    center: fromLonLat([78.9629, 20.5937]),
    zoom: 5,
    maxZoom: 19,
    minZoom: 2,
  }));

  const mapsByIdRef = useRef(new Map());
  const [activeMapId, setActiveMapId] = useState(null);
  const mapRef = useRef(null);

  const registerMap = useCallback((mapId, map) => {
    mapsByIdRef.current.set(mapId, map);
    if (!mapRef.current) {
      mapRef.current = map;
    }
  }, []);

  const unregisterMap = useCallback((mapId) => {
    const map = mapsByIdRef.current.get(mapId);
    mapsByIdRef.current.delete(mapId);
    if (mapRef.current === map) {
      const iter = mapsByIdRef.current.values().next();
      mapRef.current = iter.done ? null : iter.value;
    }
  }, []);

  // ─── Raster layers ───
  const [rasterLayers, setRasterLayers] = useState([]);
  const [cursorValues, setCursorValues] = useState([]);
  const [coordinates, setCoordinates] = useState({ lat: 0, lon: 0 });

  const [dataPath] = useState(initialDataPath || '/data');
  // Per array-type color theme (e.g. { rsrp: 'grayscale', dl_loss: 'classic' })
  const [colorThemes, setColorThemes] = useState({});

  const getColorTheme = useCallback((arrayTypeId) => {
    return colorThemes[arrayTypeId] || 'classic';
  }, [colorThemes]);

  const setColorTheme = useCallback((arrayTypeId, themeId) => {
    setColorThemes((prev) => {
      if (prev[arrayTypeId] === themeId) return prev;
      return { ...prev, [arrayTypeId]: themeId };
    });
  }, []);

  // Pre-decoded Float16Arrays for cursor sampling (keyed by layer id)
  const rasterDataRef = useRef(new Map());

  // ─── Polygon drawing ───
  const polygonSourceRef = useRef(new VectorSource());
  const polygonLayerRef = useRef(null);
  const drawInteractionRef = useRef(null);
  const [drawnPolygons, setDrawnPolygons] = useState([]);
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [activePolygonId, setActivePolygonId] = useState(null);

  // ─── Cells/Sites ───
  const [cellsData, setCellsData] = useState(null);
  const [cellsLayerVisible, setCellsLayerVisible] = useState(false);
  const cellsVectorSourceRef = useRef(null);
  const [cellsSourceReady, setCellsSourceReady] = useState(false);
  const [selectedCellInfo, setSelectedCellInfo] = useState(null);

  const visibleRasterCount = useMemo(
    () => rasterLayers.filter((l) => l.visible).length,
    [rasterLayers]
  );

  const activeBands = useMemo(() => {
    const bands = new Set();
    rasterLayers.forEach((l) => {
      if (l.visible && l.band) bands.add(l.band);
    });
    return bands;
  }, [rasterLayers]);

  const value = {
    viewMode, setViewMode,
    sharedViewRef,
    mapsByIdRef,
    activeMapId, setActiveMapId,
    registerMap, unregisterMap,
    mapRef,

    rasterLayers, setRasterLayers,
    cursorValues, setCursorValues,
    coordinates, setCoordinates,
    colorThemes, getColorTheme, setColorTheme,
    rasterDataRef,
    dataPath,
    visibleRasterCount,
    activeBands,

    polygonLayerRef,
    polygonSourceRef,
    drawInteractionRef,
    drawnPolygons, setDrawnPolygons,
    isDrawingMode, setIsDrawingMode,
    activePolygonId, setActivePolygonId,

    cellsData, setCellsData,
    cellsLayerVisible, setCellsLayerVisible,
    cellsVectorSourceRef,
    cellsSourceReady, setCellsSourceReady,
    selectedCellInfo, setSelectedCellInfo,
  };

  return (
    <MapContext.Provider value={value}>
      {children}
    </MapContext.Provider>
  );
}

export function useMapContext() {
  const context = useContext(MapContext);
  if (!context) {
    throw new Error('useMapContext must be used within a MapProvider');
  }
  return context;
}

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import Map from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import OSM from 'ol/source/OSM';
import VectorSource from 'ol/source/Vector';
import Draw from 'ol/interaction/Draw';
import { Style, Stroke, Fill } from 'ol/style';
import { fromLonLat, toLonLat } from 'ol/proj';
import Polygon from 'ol/geom/Polygon';

import { useACSSContext } from '../../context/ACSSContext';
import { Trash2, MousePointer2, ExternalLink } from 'lucide-react';
import { expandPolygon } from '../../utils/polygonUtils';
import { setupApi } from '../../api/acssApi';
import { BaselineCellSelectionModal } from '../../components/setup';
import { boundingExtent } from 'ol/extent';
// New modular components
import { MapProvider } from './context/MapContext';
import { DEFAULT_LAYER_SETTINGS, LAYER_Z_INDEX } from './constants/layerOrder';
import CellsLayer from './layers/CellsLayer';
import PolygonLayer from './layers/PolygonLayer';
import EncodedRasterLayers from './layers/EncodedRasterLayers';
import FeaturePopup from './controls/FeaturePopup';
import LayerPanel from './controls/LayerPanel';
import { getColorForValue, getArrayType } from '../../../coverage_map_viewer/2d/registry';





function MapView() {
  const location = useLocation();
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const osmLayerRef = useRef(null);
  const drawInteractionRef = useRef(null);
  const drawSourceRef = useRef(null); // Separate source for draw interaction
  const handoffConsumedRef = useRef(false); // Prevent re-consuming handoff
  
  const [coordinates, setCoordinates] = useState({ lat: 0, lon: 0 });
  const [showBaselineModal, setShowBaselineModal] = useState(false);
  const [pendingPolygonData, setPendingPolygonData] = useState(null);
  const [selectedFeatureInfo, setSelectedFeatureInfo] = useState(null);
  const [mapReady, setMapReady] = useState(false);
  
  // Layer settings state
  const [layerSettings, setLayerSettings] = useState(DEFAULT_LAYER_SETTINGS);

  // Decoded raster values for cursor hover sampling (filled by EncodedRasterLayers)
  const rasterDecodedRef = useRef(new Map());
  const [cursorRasterValues, setCursorRasterValues] = useState([]); // [{layerId, layerName, value, group}]
  const lastMoveRef = useRef(0);
  
  const { 
    addLog, 
    polygon,
    completePolygon,
    clearPolygon,
    cancelPolygonDrawing,
    updatePolygon,
    setBoundaryRadius,
    project_cords,
    projectName,
    acssSessionId,
    setupState,
    executionStatus,
  } = useACSSContext();

  // Get polygon state directly from setupState
  const isPolygonDone = polygon?.status === 'done';
  const isDrawingMode = polygon?.isDrawing || false;
  const polygonCoords = polygon?.coords || null;
  const boundaryRadius = polygon?.boundaryRadius || 5;
  const boundaryCoords = polygon?.boundaryCoords || null;
  const baselineCells = polygon?.baselineCells || null;

  // All candidates from GDL (preview, available after GDL upload, before execution completes)
  const allCandidates = setupState?.allCandidates || null;
  const hasAllCandidates = allCandidates && allCandidates.length > 0;

  // Saved (selected) candidates from execution results (only when session completes)
  const savedCandidates = setupState?.savedCandidates || null;
  const hasSavedCandidates = executionStatus === 'completed' && savedCandidates && savedCandidates.length > 0;

  // Show GDL preview when candidates exist but execution is NOT completed
  // (once execution completes, savedCandidates layer takes over)
  const showAllCandidatesPreview = hasAllCandidates && executionStatus !== 'completed';

  // Encoded raster map data path (available after execution completes the encoding step)
  const mapEncodedOutputDir = setupState?.mapEncodedOutputDir || null;
  const hasEncodedRaster = executionStatus === 'completed' && !!mapEncodedOutputDir;

  // Callback for EncodedRasterLayers to register/unregister decoded data for cursor sampling
  const handleDecodedData = useCallback((id, data) => {
    let map = rasterDecodedRef.current;
    if (!(map instanceof Map)) {
      map = new Map();
      rasterDecodedRef.current = map;
    }
    if (data === null) {
      map.delete(id);
    } else {
      map.set(id, data);
    }
  }, []);

  // Open full map viewer in new tab
  const openDetailMapViewer = useCallback(() => {
    if (!mapEncodedOutputDir) return;
    // Normalize to forward slashes so the /map/2d viewer can serve files correctly.
    const normalized = String(mapEncodedOutputDir).replace(/\\/g, '/');
    // const url = `/map/2d/${encodeURIComponent(normalized)}`;
    const url = `/map/2d/${mapEncodedOutputDir}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  }, [mapEncodedOutputDir]);

  // Update layer settings
  const updateLayerSetting = useCallback((layerId, updates) => {
    setLayerSettings(prev => ({
      ...prev,
      [layerId]: { ...prev[layerId], ...updates }
    }));
  }, []);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Create draw source (for the drawing interaction)
    drawSourceRef.current = new VectorSource();

    // Create OSM base layer
    osmLayerRef.current = new TileLayer({
      source: new OSM(),
      zIndex: LAYER_Z_INDEX.OSM,
    });

    // Create map
    const map = new Map({
      target: containerRef.current,
      layers: [osmLayerRef.current],
      view: new View({
        center: [0,0],
        zoom: 5,
        maxZoom: 19,
        minZoom: 2,
      }),
      controls: []
    });

    // Track mouse position + sample encoded RSRP layers
    map.on('pointermove', (evt) => {
      // Throttle to ~20fps
      const now = Date.now();
      if (now - lastMoveRef.current < 50) return;
      lastMoveRef.current = now;

      const [lon, lat] = toLonLat(evt.coordinate);
      const [mapX, mapY] = evt.coordinate; // EPSG:3857 map coordinates
      setCoordinates({
        lat: lat.toFixed(6),
        lon: lon.toFixed(6),
      });

      // Sample encoded raster layers (commented out - not working for now)
      // const values = [];
      // const decodedMap = rasterDecodedRef.current;
      // const entries = decodedMap instanceof Map && typeof decodedMap.entries === 'function'
      //   ? decodedMap.entries()
      //   : [];
      // for (const [id, data] of entries) {
      //   const { rasterValues, width, height, extent, bounds, layerName, group } = data;
      //   if (!rasterValues) continue;
      //   if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) continue;
      //   let value = NaN;
      //   if (extent && extent.length === 4) {
      //     const [minX, minY, maxX, maxY] = extent;
      //     if (maxX !== minX && maxY !== minY && mapX >= minX && mapX <= maxX && mapY >= minY && mapY <= maxY) {
      //       const xRatio = (mapX - minX) / (maxX - minX);
      //       const yRatio = (maxY - mapY) / (maxY - minY);
      //       const px = Math.max(0, Math.min(width - 1, Math.floor(xRatio * width)));
      //       const py = Math.max(0, Math.min(height - 1, Math.floor(yRatio * height)));
      //       value = rasterValues[py * width + px];
      //       if (Number.isNaN(value)) {
      //         const yRatioFlipped = (mapY - minY) / (maxY - minY);
      //         const py2 = Math.max(0, Math.min(height - 1, Math.floor(yRatioFlipped * height)));
      //         value = rasterValues[py2 * width + px];
      //       }
      //     }
      //   } else if (bounds) {
      //     if (lon >= bounds.west && lon <= bounds.east && lat >= bounds.south && lat <= bounds.north) {
      //       const xRatio = (lon - bounds.west) / (bounds.east - bounds.west);
      //       const yRatio = (bounds.north - lat) / (bounds.north - bounds.south);
      //       const px = Math.max(0, Math.min(width - 1, Math.floor(xRatio * width)));
      //       const py = Math.max(0, Math.min(height - 1, Math.floor(yRatio * height)));
      //       value = rasterValues[py * width + px];
      //       if (Number.isNaN(value)) {
      //         const yRatioFlipped = (lat - bounds.south) / (bounds.north - bounds.south);
      //         const py2 = Math.max(0, Math.min(height - 1, Math.floor(yRatioFlipped * height)));
      //         value = rasterValues[py2 * width + px];
      //       }
      //     }
      //   }
      //   if (!isNaN(value)) values.push({ layerId: id, layerName, value, group });
      // }
      // setCursorRasterValues(values);
      
      // Change cursor when hovering over cell/site features
      const pixel = map.getEventPixel(evt.originalEvent);
      let hitCellFeature = false;
      map.forEachFeatureAtPixel(pixel, (f) => {
        const featureType = f.get('featureType');
        if (featureType === 'cell' || featureType === 'site') {
          hitCellFeature = true;
          return true;
        }
      }, {
        hitTolerance: 5,
      });
      map.getTargetElement().style.cursor = hitCellFeature ? 'pointer' : '';
    });

    // map.on('pointerout', () => {
    //   setCursorRasterValues([]);
    // });

    // Handle click on cell/site features
    map.on('click', (evt) => {
      const pixel = map.getEventPixel(evt.originalEvent);
      let clickedFeature = null;
      
      map.forEachFeatureAtPixel(pixel, (f) => {
        const featureType = f.get('featureType');
        if (featureType === 'cell' || featureType === 'site') {
          clickedFeature = f;
          return true;
        }
      }, {
        hitTolerance: 5,
      });
      
      if (clickedFeature) {
        setSelectedFeatureInfo({
          type: clickedFeature.get('featureType'),
          cell: clickedFeature.get('cellData'),
          site: clickedFeature.get('siteData'),
        });
      } else {
        setSelectedFeatureInfo(null);
      }
    });

    mapRef.current = map;
    setMapReady(true);
    addLog('Map initialized');

    return () => {
      map.setTarget(null);
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  // Update OSM layer visibility and opacity
  useEffect(() => {
    if (osmLayerRef.current) {
      osmLayerRef.current.setVisible(layerSettings.osm.visible);
      osmLayerRef.current.setOpacity(layerSettings.osm.opacity);
    }
  }, [layerSettings.osm.visible, layerSettings.osm.opacity]);

  // Fit map to project area
  useEffect(() => {
    if (!mapRef.current || !project_cords || project_cords.length < 3) return;

    try {
    
      const polygon = new Polygon([project_cords.map(coord => fromLonLat(coord))]);
      console.log(polygon);
      const view = mapRef.current.getView();
      
      view.fit(polygon, {
        padding: [100, 100, 100, 100],
        duration: 5000,
        maxZoom: 20
      });
      
      addLog('Map centered on project area');
    } catch (error) {
      console.error('Error fitting map to project coordinates:', error);
    }
  }, [project_cords, addLog]);

  // Handle draw completion - opens baseline cell selection modal
  const onDrawEnd = useCallback(async (event) => {
    const feature = event.feature;
    const geometry = feature.getGeometry();
    
    // Get coordinates in WGS84
    const coords = geometry.getCoordinates()[0];
    const coordsWGS84 = coords.map(coord => toLonLat(coord));
    
    // Calculate boundary polygon (expanded by boundaryRadius uniformly)
    const expandedCoords = expandPolygon(coordsWGS84, boundaryRadius);
    
    // Store pending polygon data and open the baseline cell selection modal
    setPendingPolygonData({
      polygon_coords: coordsWGS84,
      boundary_coords: expandedCoords,
      boundary_radius: boundaryRadius,
    });
    setShowBaselineModal(true);
    addLog("Polygon drawn - please select baseline cells");
    
    // Remove draw interaction
    if (drawInteractionRef.current && mapRef.current) {
      mapRef.current.removeInteraction(drawInteractionRef.current);
      drawInteractionRef.current = null;
    }
  }, [addLog, boundaryRadius]);

  // Handle baseline cell selection confirmation
  const handleBaselineConfirm = useCallback(async (selectedSitesData, arrayType, technology, selectedBand) => {
    if (!pendingPolygonData) return;
    
    try {
      const fullPolygonData = {
        ...pendingPolygonData,
        baseline_cells: selectedSitesData,
        array_type: arrayType,
        technology: technology,
        selected_band: selectedBand || null,
      };
      
      await setupApi.putPolygon(acssSessionId, fullPolygonData, projectName);
      
      const totalCells = selectedSitesData.reduce((sum, site) => sum + (site.cells?.length || 0), 0);
      
      completePolygon(pendingPolygonData.polygon_coords, pendingPolygonData.boundary_coords, selectedSitesData, arrayType, technology, selectedBand);
      setShowBaselineModal(false);
      setPendingPolygonData(null);
      addLog(`Polygon saved with ${selectedSitesData.length} sites and ${totalCells} baseline cells (band: ${selectedBand}, array type: ${arrayType}, technology: ${technology})`);
    } catch (error) {
      addLog("Error saving polygon: " + error.message);
    }
  }, [pendingPolygonData, acssSessionId, projectName, completePolygon, addLog]);

  // Handle baseline modal cancel
  const handleBaselineCancel = useCallback(() => {
    setShowBaselineModal(false);
    setPendingPolygonData(null);
    cancelPolygonDrawing();
    if (drawSourceRef.current) {
      drawSourceRef.current.clear();
    }
    addLog("Polygon creation cancelled");
  }, [addLog, cancelPolygonDrawing]);

  // Effect to handle drawing mode changes
  useEffect(() => {
    if (!mapRef.current) return;

    if (isDrawingMode) {
      // Clear draw source
      if (drawSourceRef.current) {
        drawSourceRef.current.clear();
      }
      
      // Create draw interaction
      const draw = new Draw({
        source: drawSourceRef.current,
        type: 'Polygon',
        style: new Style({
          stroke: new Stroke({
            color: '#1d4a91',
            width: 2,
          }),
          fill: new Fill({
            color: 'rgba(29, 74, 145, 0.2)',
          }),
        }),
      });

      draw.on('drawend', onDrawEnd);
      drawInteractionRef.current = draw;
      mapRef.current.addInteraction(draw);
      addLog('Drawing mode enabled - click to add vertices, double-click to finish');
    } else {
      // Disable drawing
      if (drawInteractionRef.current && mapRef.current) {
        mapRef.current.removeInteraction(drawInteractionRef.current);
        drawInteractionRef.current = null;
      }
    }
  }, [isDrawingMode, addLog, onDrawEnd]);

  // Handle clear polygon
  const handleClearPolygon = useCallback(() => {
    if (drawSourceRef.current) {
      drawSourceRef.current.clear();
    }
    clearPolygon();
    addLog('Polygon, Boundary, and Baseline Cells cleared');
  }, [clearPolygon, addLog]);

  // Handle Escape key to cancel drawing
  useEffect(() => {
    if (!isDrawingMode) return;
    
    const handler = (e) => {
      if (e.key === 'Escape') {
        cancelPolygonDrawing();
        addLog('Drawing cancelled');
      }
    };
    
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isDrawingMode, cancelPolygonDrawing, addLog]);

  // ============ COVERAGE-TO-ACSS HANDOFF ============
  // Consume acssHandoff from router navigation state (or sessionStorage fallback).
  // Once projectName + acssSessionId are ready (set by ACSS init), prefill polygon/boundary
  // and auto-open the baseline cell selection modal.
  useEffect(() => {
    if (handoffConsumedRef.current) return;
    if (!projectName || !acssSessionId) return; // Wait until ACSS session is initialized

    // Read handoff from router state, fall back to sessionStorage
    const handoff = location.state?.acssHandoff 
      ?? JSON.parse(sessionStorage.getItem('acssHandoff') || 'null');

    if (!handoff || !handoff.polygonCoords || handoff.polygonCoords.length < 3) return;

    // Mark consumed so this only runs once
    handoffConsumedRef.current = true;
    sessionStorage.removeItem('acssHandoff');

    const radiusKm = handoff.initialRadiusKm || 5;
    const polyCoords = handoff.polygonCoords;
    const boundary = expandPolygon(polyCoords, radiusKm);

    // Update ACSS context so polygon + boundary render on the map immediately
    setBoundaryRadius(radiusKm);
    updatePolygon({
      status: 'running',
      isDrawing: false,
      coords: polyCoords,
      boundaryCoords: boundary,
      vertices: polyCoords.length,
    });

    // Set pending data and open baseline cell selection modal
    setPendingPolygonData({
      polygon_coords: polyCoords,
      boundary_coords: boundary,
      boundary_radius: radiusKm,
    });
    setShowBaselineModal(true);

    addLog(`Coverage handoff received — polygon with ${polyCoords.length} vertices, boundary ${radiusKm}km`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectName, acssSessionId, location.state, addLog, setBoundaryRadius, updatePolygon]);

  // Handle boundary radius change from the baseline cell selection modal
  const handleBoundaryRadiusChange = useCallback((newRadiusKm) => {
    if (!pendingPolygonData?.polygon_coords) return;

    const newBoundary = expandPolygon(pendingPolygonData.polygon_coords, newRadiusKm);

    // Update pending data
    setPendingPolygonData(prev => ({
      ...prev,
      boundary_coords: newBoundary,
      boundary_radius: newRadiusKm,
    }));

    // Update ACSS context so polygon layer + boundary layer update live
    setBoundaryRadius(newRadiusKm);
    updatePolygon({
      boundaryRadius: newRadiusKm,
      boundaryCoords: newBoundary,
    });

    addLog(`Boundary radius changed to ${newRadiusKm}km`);
  }, [pendingPolygonData, setBoundaryRadius, updatePolygon, addLog]);

  return (
    <div className="relative w-full h-full">
      {/* Map Container */}
      <div 
        ref={containerRef} 
        className="w-full h-full"
        style={{ minHeight: '100%' }}
      />

      {/* Map Context Provider - wraps layer components */}
      {mapReady && mapRef.current && (
        <MapProvider value={mapRef.current}>
          {/* Polygon and Boundary Layers */}
          <PolygonLayer
            polygonVisible={layerSettings.polygon.visible}
            polygonOpacity={layerSettings.polygon.opacity}
            boundaryVisible={layerSettings.boundary.visible}
            boundaryOpacity={layerSettings.boundary.opacity}
            polygonCoords={polygonCoords}
            boundaryCoords={boundaryCoords}
            isPolygonDone={isPolygonDone}
          />

          {/* Cells Layer (Baseline) */}
          <CellsLayer
            visible={layerSettings.cells.visible}
            opacity={layerSettings.cells.opacity}
            data={baselineCells}
            enabled={isPolygonDone && baselineCells && baselineCells.length > 0}
          />

          {/* Cells Layer (All GDL Candidates — preview with diamond markers) */}
          <CellsLayer
            visible={layerSettings.allCandidates.visible}
            opacity={layerSettings.allCandidates.opacity}
            data={allCandidates}
            enabled={showAllCandidatesPreview}
            siteMarkerColor="#F59E0B"
            siteMarkerType="diamond"
            zIndexKey="ALL_CANDIDATES"
          />

          {/* Cells Layer (Selected Candidates — after execution complete, green circle markers) */}
          <CellsLayer
            visible={layerSettings.candidateCells.visible}
            opacity={layerSettings.candidateCells.opacity}
            data={savedCandidates}
            enabled={hasSavedCandidates}
            siteMarkerColor="#2E7D32"
            zIndexKey="CANDIDATE_CELLS"
          />

          {/* Encoded raster Coverage Layers (baseline + combined, after execution completes) */}
          {hasEncodedRaster && (
            <EncodedRasterLayers
              dataPath={mapEncodedOutputDir}
              baselineVisible={layerSettings.baselineRaster.visible}
              baselineOpacity={layerSettings.baselineRaster.opacity}
              combinedVisible={layerSettings.combinedRaster.visible}
              combinedOpacity={layerSettings.combinedRaster.opacity}
              onDecodedData={handleDecodedData}
            />
          )}

          {/* Layer Control Panel */}
          {!selectedFeatureInfo && (
            <LayerPanel
              settings={layerSettings}
              onUpdateLayer={updateLayerSetting}
              hasCellsData={isPolygonDone && baselineCells && baselineCells.length > 0}
              hasAllCandidatesData={showAllCandidatesPreview}
              hasCandidateCellsData={hasSavedCandidates}
              hasEncodedRaster={hasEncodedRaster}
            />
          )}
        </MapProvider>
      )}

      {/* Feature Popup (outside MapProvider as it doesn't need map access) */}
      <FeaturePopup 
        info={selectedFeatureInfo} 
        onClose={() => setSelectedFeatureInfo(null)} 
      />

      {/* Controls Overlay - Clear button only */}
      {(executionStatus === 'not started' || executionStatus === 'error') && polygonCoords && !isDrawingMode && (
        <div className="absolute top-4 left-4 z-10">
          <button
            onClick={handleClearPolygon}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm
              bg-card hover:bg-accent text-foreground
              transition-all duration-200 shadow-lg border border-border"
          >
            <Trash2 className="w-4 h-4" />
            Clear Polygon
          </button>
        </div>
      )}

      {/* Drawing Instructions */}
      {isDrawingMode && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10
          bg-primary/90 text-primary-foreground px-4 py-2 rounded-lg text-sm
          shadow-lg backdrop-blur-sm">
          Click to add vertices • Double-click to finish • ESC to cancel
        </div>
      )}

      {/* Coordinates Display */}
      <div className="absolute bottom-4 left-4 z-10
        bg-card/90 backdrop-blur-sm px-3 py-2 rounded-lg
        font-mono text-xs text-foreground shadow-lg border border-border">
        <div className="flex items-center gap-2">
          <MousePointer2 className="w-3 h-3 text-primary" />
          <span>Lat: {coordinates.lat}</span>
          <span className="text-muted-foreground">|</span>
          <span>Lon: {coordinates.lon}</span>
        </div>
      </div>

      {/* Polygon Info */}
      {polygonCoords && (
        <div className="absolute bottom-4 right-4 z-10
          bg-card/90 backdrop-blur-sm px-4 py-3 rounded-lg
          shadow-lg border border-border min-w-[220px]">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
            SIM AREA Polygon
          </div>  
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-green-500/50 border border-green-500"></div>
              <span className="text-xs text-foreground">Polygon: {polygonCoords.length} vertices</span>
            </div>
            {boundaryCoords && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm bg-blue-500/30 border border-blue-500 border-dashed"></div>
                <span className="text-xs text-foreground">Boundary: {boundaryRadius}km radius</span>
              </div>
            )}
            {baselineCells && baselineCells.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm bg-red-500/50 border border-red-500"></div>
                <span className="text-xs text-foreground">
                  Baseline: {baselineCells.length} sites, {baselineCells.reduce((sum, s) => sum + (s.cells?.length || 0), 0)} cells
                </span>
              </div>
            )}
            {showAllCandidatesPreview && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-amber-500/50 border border-amber-500" style={{ transform: 'rotate(45deg)' }}></div>
                <span className="text-xs text-foreground">
                  GDL Preview: {allCandidates.length} sites, {allCandidates.reduce((sum, s) => sum + (s.cells?.length || 0), 0)} cells
                </span>
              </div>
            )}
            {hasSavedCandidates && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm bg-green-600/50 border border-green-500"></div>
                <span className="text-xs text-foreground">
                  Selected: {savedCandidates.length} sites, {savedCandidates.reduce((sum, s) => sum + (s.cells?.length || 0), 0)} cells
                </span>
              </div>
            )}
          </div>
          <div className={`text-xs mt-2 pt-2 border-t border-border ${isPolygonDone ? 'text-green-400' : 'text-muted-foreground'}`}>
            Status: {isPolygonDone ? 'Complete' : 'Pending'}
          </div>
        </div>
      )}

      {/* Raster Cursor Hover Display - commented out, not working for now */}
      {/* {hasEncodedRaster && (
        <div className="absolute bottom-14 left-4 z-10
          bg-slate-900/95 backdrop-blur-sm px-3 py-2.5 rounded-lg
          shadow-lg border border-slate-700/50 min-w-[180px]">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider">Raster Value</div>
            <div className="text-[10px] text-slate-500">
              Layers: {rasterDecodedRef.current instanceof Map ? rasterDecodedRef.current.size : 0}
            </div>
          </div>
          {(() => {
            if (!cursorRasterValues || cursorRasterValues.length === 0) {
              return (
                <div className="text-xs text-slate-400">
                  -- <span className="text-[10px] text-slate-500">(move cursor over raster)</span>
                </div>
              );
            }
            const groups = {};
            cursorRasterValues.forEach((v) => {
              if (!groups[v.group]) groups[v.group] = v;
            });
            return Object.values(groups).map((item) => {
              const typeId = item.registryTypeId || 'rsrp';
              const config = getArrayType(typeId);
              const { color, label: quality } = getColorForValue(item.value, typeId);
              return (
                <div key={item.layerId} className="mb-1 last:mb-0">
                  <div className="text-[10px] text-slate-500 truncate">{item.group === 'baseline' ? 'Baseline' : 'Combined'}</div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-sm font-semibold" style={{ color }}>{item.value.toFixed(1)}</span>
                    <span className="text-[10px] text-slate-400">{config?.unit || ''}</span>
                    <span className="text-[10px] ml-1" style={{ color }}>{quality}</span>
                  </div>
                </div>
              );
            });
          })()}
        </div>
      )} */}

      {/* Detail analysis button — opens full map viewer in new tab */}
      {hasEncodedRaster && (
        <button
          onClick={openDetailMapViewer}
          className="absolute top-14 left-4 z-10 flex items-center gap-2
            px-3 py-2 rounded-lg text-xs font-medium
            bg-primary/90 hover:bg-primary text-primary-foreground
            transition-colors shadow-lg backdrop-blur-sm cursor-pointer"
          title="Open the full interactive map viewer in a new tab"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Detail analysis with map viewer
        </button>
      )}

      {/* Baseline Cell Selection Modal */}
      {showBaselineModal && pendingPolygonData && (
        <BaselineCellSelectionModal
          isOpen={showBaselineModal}
          onClose={handleBaselineCancel}
          onConfirm={handleBaselineConfirm}
          boundaryCoords={pendingPolygonData.boundary_coords}
          boundaryRadiusKm={pendingPolygonData.boundary_radius}
          onBoundaryRadiusChange={handleBoundaryRadiusChange}
          projectName={projectName}
          acssSessionId={acssSessionId}
        />
      )}
    </div>
  );
}

export default MapView;

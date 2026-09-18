import React, { useEffect, useCallback, useRef } from 'react';
import Draw from 'ol/interaction/Draw';
import { Style, Stroke, Fill } from 'ol/style';
import { toLonLat } from 'ol/proj';
import { useMapContext } from '../context/MapContext';
import {
  calculateStats,
  getPixelsInPolygon,
  calculatePolygonArea,
  countCellsInPolygon,
} from '../utils/stats';
import { resolveColorBands } from '../registry';

/**
 * PolygonDrawControl Component
 *
 * Provides UI and functionality for:
 * - Drawing polygons on the map (Draw interaction on active map)
 * - Calculating RSRP statistics within polygons
 * - Managing drawn polygons (list, delete, select)
 *
 * In multi-map mode, the Draw interaction is attached to the active map.
 * The shared polygonSourceRef ensures polygons appear on all map panes
 * (MapView creates VectorLayers from this source).
 */
function PolygonDrawControl() {
  const {
    mapRef,
    sharedViewRef,
    viewMode,
    activeMapId,
    mapsByIdRef,
    polygonSourceRef,
    drawInteractionRef,
    drawnPolygons,
    setDrawnPolygons,
    isDrawingMode,
    setIsDrawingMode,
    activePolygonId,
    setActivePolygonId,
    rasterDataRef,
    rasterLayers,
    getColorTheme,
    cellsData,
  } = useMapContext();

  // Track which map the draw interaction is currently attached to
  const drawingMapRef = useRef(null);

  /**
   * Get the map to use for draw interaction.
   * In single mode: primary map. In split mode: active (hovered) map.
   */
  const getTargetMap = useCallback(() => {
    if (viewMode === 'split' && activeMapId) {
      return mapsByIdRef.current.get(activeMapId) || mapRef.current;
    }
    return mapRef.current;
  }, [viewMode, activeMapId, mapsByIdRef, mapRef]);

  /**
   * Cleanup draw interaction on unmount
   */
  useEffect(() => {
    return () => {
      if (drawInteractionRef.current && drawingMapRef.current) {
        drawingMapRef.current.removeInteraction(drawInteractionRef.current);
        drawInteractionRef.current = null;
        drawingMapRef.current = null;
      }
    };
  }, [drawInteractionRef]);

  /**
   * Calculate statistics for a polygon from all visible raster layers
   */
  const calculatePolygonStats = useCallback((coords) => {
    const layerStats = [];

    const visibleLayers = rasterLayers.filter(l => l.visible);

    visibleLayers.forEach(layer => {
      const cachedData = rasterDataRef.current.get(layer.id);
      if (!cachedData) return;

      const { decodedValues, width, height, bounds, layerName } = cachedData;
      const arrayTypeId = layer.arrayTypeId || 'rsrp';
      const colorBands = resolveColorBands(arrayTypeId, getColorTheme(arrayTypeId));

      const values = getPixelsInPolygon(
        decodedValues,
        width,
        height,
        bounds,
        coords
      );

      if (values.length > 0) {
        const stats = calculateStats(values, colorBands);
        layerStats.push({
          layerId: layer.id,
          layerName: layerName || layer.name,
          arrayTypeId,
          stats,
          sampleCount: values.length,
        });
      }
    });

    const area = calculatePolygonArea(coords);
    const cellStats = countCellsInPolygon(cellsData, coords);

    return {
      byLayer: layerStats,
      area,
      cellStats,
      timestamp: new Date().toISOString(),
    };
  }, [rasterLayers, rasterDataRef, cellsData, getColorTheme]);

  /**
   * Handle drawing completion
   */
  const onDrawEnd = useCallback((event) => {
    const feature = event.feature;
    const geometry = feature.getGeometry();

    const coordinates = geometry.getCoordinates()[0];
    const coordsWGS84 = coordinates.map(coord => toLonLat(coord));

    const id = `polygon-${Date.now()}`;
    feature.set('id', id);

    const stats = calculatePolygonStats(coordsWGS84);

    const newPolygon = {
      id,
      feature,
      coords: coordsWGS84,
      stats,
      name: `Region ${drawnPolygons.length + 1}`,
      createdAt: new Date().toISOString(),
    };

    setDrawnPolygons(prev => [...prev, newPolygon]);
    setActivePolygonId(id);
    setIsDrawingMode(false);

    // Remove draw interaction from the map it was attached to
    if (drawInteractionRef.current && drawingMapRef.current) {
      drawingMapRef.current.removeInteraction(drawInteractionRef.current);
      drawInteractionRef.current = null;
      drawingMapRef.current = null;
    }
  }, [calculatePolygonStats, drawnPolygons.length, drawInteractionRef, setDrawnPolygons, setActivePolygonId, setIsDrawingMode]);

  /**
   * Toggle drawing mode
   */
  const toggleDrawingMode = useCallback(() => {
    if (!polygonSourceRef.current) return;

    if (isDrawingMode) {
      // Disable drawing
      if (drawInteractionRef.current && drawingMapRef.current) {
        drawingMapRef.current.removeInteraction(drawInteractionRef.current);
        drawInteractionRef.current = null;
        drawingMapRef.current = null;
      }
      setIsDrawingMode(false);
    } else {
      const targetMap = getTargetMap();
      if (!targetMap) return;

      const draw = new Draw({
        source: polygonSourceRef.current,
        type: 'Polygon',
        style: new Style({
          stroke: new Stroke({ color: '#1d4a91', width: 2 }),
          fill: new Fill({
            color: 'rgba(239, 68, 68, 0.1)',
          }),
        }),
      });

      draw.on('drawend', onDrawEnd);
      drawInteractionRef.current = draw;
      drawingMapRef.current = targetMap;
      targetMap.addInteraction(draw);
      setIsDrawingMode(true);
    }
  }, [isDrawingMode, polygonSourceRef, drawInteractionRef, onDrawEnd, setIsDrawingMode, getTargetMap]);

  /**
   * Allow Escape key to cancel drawing mode
   */
  useEffect(() => {
    if (!isDrawingMode) return;
    const handler = (e) => {
      if (e.key === 'Escape') {
        if (drawInteractionRef.current && drawingMapRef.current) {
          drawingMapRef.current.removeInteraction(drawInteractionRef.current);
          drawInteractionRef.current = null;
          drawingMapRef.current = null;
        }
        setIsDrawingMode(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isDrawingMode, drawInteractionRef, setIsDrawingMode]);

  /**
   * Delete a polygon
   */
  const deletePolygon = useCallback((id) => {
    const polygon = drawnPolygons.find(p => p.id === id);
    if (polygon && polygonSourceRef.current) {
      polygonSourceRef.current.removeFeature(polygon.feature);
    }

    setDrawnPolygons(prev => prev.filter(p => p.id !== id));

    if (activePolygonId === id) {
      setActivePolygonId(null);
    }
  }, [drawnPolygons, polygonSourceRef, activePolygonId, setDrawnPolygons, setActivePolygonId]);

  /**
   * Select a polygon and fly to it
   */
  const selectPolygon = useCallback((id) => {
    setActivePolygonId(id);

    // Fit view to polygon using shared view
    const polygon = drawnPolygons.find(p => p.id === id);
    if (polygon && polygon.feature && sharedViewRef.current) {
      const extent = polygon.feature.getGeometry().getExtent();
      sharedViewRef.current.fit(extent, {
        padding: [50, 50, 50, 50],
        maxZoom: 13,
        duration: 500,
      });
    }
  }, [drawnPolygons, sharedViewRef, setActivePolygonId]);

  /**
   * Clear all polygons
   */
  const clearAllPolygons = useCallback(() => {
    if (polygonSourceRef.current) {
      polygonSourceRef.current.clear();
    }
    setDrawnPolygons([]);
    setActivePolygonId(null);
  }, [polygonSourceRef, setDrawnPolygons, setActivePolygonId]);

  /**
   * Recalculate stats for all polygons (e.g., when layers change)
   */
  const recalculateAllStats = useCallback(() => {
    setDrawnPolygons(prev => prev.map(polygon => ({
      ...polygon,
      stats: calculatePolygonStats(polygon.coords),
    })));
  }, [calculatePolygonStats, setDrawnPolygons]);

  return (
    <div className="control-section">
      <div className="section-header">
        <span className="section-title">Polygon Analysis</span>
      </div>

      {/* Draw Button */}
      <button
        onClick={toggleDrawingMode}
        style={{
          width: '100%',
          padding: '10px 16px',
          marginBottom: '12px',
          background: isDrawingMode
            ? 'linear-gradient(135deg, #ff4757 0%, #ff6b7a 100%)'
            : 'var(--primary)',
          color: 'var(--primary-foreground)',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          fontSize: '13px',
          fontWeight: '500',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          transition: 'all 0.2s ease',
        }}
      >
        {isDrawingMode ? (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            Cancel Drawing
          </>
        ) : (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
            </svg>
            Draw Polygon
          </>
        )}
      </button>

      {isDrawingMode && (
        <div style={{
          padding: '8px 12px',
          marginBottom: '12px',
          background: 'color-mix(in oklch, var(--primary) 15%, transparent)',
          borderRadius: '6px',
          fontSize: '11px',
          color: 'var(--text-secondary)',
        }}>
          Click on the map to draw polygon vertices. Double-click to complete.
        </div>
      )}

      {/* Polygon List */}
      {drawnPolygons.length > 0 && (
        <>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '8px',
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {drawnPolygons.length} Region{drawnPolygons.length > 1 ? 's' : ''}
            </span>
            <button
              onClick={clearAllPolygons}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--destructive)',
                cursor: 'pointer',
                fontSize: '11px',
                padding: '4px 8px',
              }}
            >
              Clear All
            </button>
          </div>

          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {drawnPolygons.map(polygon => (
              <div
                key={polygon.id}
                onClick={() => selectPolygon(polygon.id)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 10px',
                  marginBottom: '4px',
                  background: polygon.id === activePolygonId
                    ? 'color-mix(in oklch, var(--success, #00d26a) 15%, transparent)'
                    : 'color-mix(in oklch, var(--foreground) 3%, transparent)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  border: polygon.id === activePolygonId
                    ? '1px solid color-mix(in oklch, var(--success, #00d26a) 30%, transparent)'
                    : '1px solid transparent',
                  transition: 'all 0.2s ease',
                }}
              >
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
                    {polygon.name}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                    {(polygon.stats?.byLayer?.reduce((sum, l) => sum + (l.sampleCount || 0), 0) || 0).toLocaleString()} samples
                    {polygon.stats?.area && ` • ${polygon.stats.area.toFixed(2)} km²`}
                  </div>
                  {polygon.stats?.cellStats?.cells > 0 && (
                    <div style={{ fontSize: '10px', color: 'var(--success, #00d26a)', marginTop: '2px' }}>
                      {polygon.stats.cellStats.cells} cells in {polygon.stats.cellStats.sites} sites
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deletePolygon(polygon.id);
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    padding: '4px',
                    borderRadius: '4px',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.color = 'var(--destructive)'}
                  onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                  title="Delete region"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>

          {/* Recalculate button */}
          <button
            onClick={recalculateAllStats}
            style={{
              width: '100%',
              padding: '8px',
              marginTop: '8px',
              background: 'color-mix(in oklch, var(--foreground) 5%, transparent)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '11px',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'color-mix(in oklch, var(--foreground) 10%, transparent)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'color-mix(in oklch, var(--foreground) 5%, transparent)';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            Recalculate Statistics
          </button>
        </>
      )}
    </div>
  );
}

export default PolygonDrawControl;

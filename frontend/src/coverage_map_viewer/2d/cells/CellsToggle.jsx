import React, { useEffect, useRef, useState, useCallback } from 'react';
import VectorSource from 'ol/source/Vector';
import { useMapContext } from '../context/MapContext';
import { getDataFileUrl } from '../utils/dataPath';
import { buildCellFeatures } from './buildCellFeatures';
import { buildLabelBandFromBaseName } from '../utils/build_lebel_band';

function getRenderModeFromZoom(zoom) {
  if (zoom < 8) return 'site';
  if (zoom < 12) return 'simplified';
  return 'full';
}

/**
 * CellsToggle Component
 *
 * Loads cells.json, builds OL features into the shared VectorSource,
 * and renders the visibility toggle in the control panel.
 */
function CellsToggle() {
  const {
    dataPath,
    cellsData,
    setCellsData,
    cellsLayerVisible,
    setCellsLayerVisible,
    cellsVectorSourceRef,
    setCellsSourceReady,
    activeBands,
    sharedViewRef,
  } = useMapContext();

  const [renderMode, setRenderMode] = useState(() =>
    getRenderModeFromZoom(sharedViewRef.current?.getZoom?.() ?? 5)
  );
  const hasLoadedRef = useRef(false);

  const loadCellsData = useCallback(async () => {
    if (!dataPath) return;
    try {
      const url = getDataFileUrl(dataPath, 'cells.json');
      const response = await fetch(url);
      if (!response.ok) {
        console.log('No cells.json found at', dataPath);
        setCellsData(null);
        return;
      }
      const data = await response.json();
      setCellsData(Array.isArray(data) ? data : [data]);
    } catch (err) {
      console.log('Could not load cells.json:', err.message);
      setCellsData(null);
    }
  }, [dataPath, setCellsData]);

  useEffect(() => {
    if (!hasLoadedRef.current && dataPath) {
      hasLoadedRef.current = true;
      loadCellsData();
    }
  }, [dataPath, loadCellsData]);

  useEffect(() => {
    const view = sharedViewRef.current;
    if (!view) return undefined;

    const syncMode = () => {
      const zoom = view.getZoom() ?? 5;
      const nextMode = getRenderModeFromZoom(zoom);
      setRenderMode((prev) => (prev === nextMode ? prev : nextMode));
    };

    syncMode();
    view.on('change:resolution', syncMode);
    return () => view.un('change:resolution', syncMode);
  }, [sharedViewRef]);

  useEffect(() => {
    if (!cellsData || cellsData.length === 0) return;

    const features = buildCellFeatures(cellsData, activeBands, { renderMode });
    const source = new VectorSource();
    source.addFeatures(features);

    cellsVectorSourceRef.current = source;
    setCellsSourceReady((prev) => !prev);

    return () => {
      cellsVectorSourceRef.current = null;
    };
  }, [cellsData, activeBands, renderMode, cellsVectorSourceRef, setCellsSourceReady]);

  if (!cellsData || cellsData.length === 0) return null;

  const totalCells = cellsData.reduce((acc, s) => acc + (s.cells?.length || 0), 0);

  return (
    <div className="control-section">
      <div className="section-title">Cell Sites Layer</div>
      <div className="layer-list">
        <div className="layer-item">
          <div className="layer-info">
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: '#B71C1C' }}
            />
            <div>
              <span className="layer-name">Cells & Sites</span>
              <span className="block text-[10px] text-muted-foreground mt-0.5">
                {cellsData.length} site{cellsData.length !== 1 ? 's' : ''}, {totalCells} cells
              </span>
              {activeBands.size > 0 && (
                <span className="block text-[9px] mt-0.5" style={{ color: 'var(--primary)' }}>
                  Filtered: {activeBands.has('All Carriers') ? 'All Bands' : [...activeBands].map((b) => buildLabelBandFromBaseName(b)).join(', ')}
                </span>
              )}
              <span className="block text-[9px] mt-0.5 text-muted-foreground">
                Detail: {renderMode === 'site' ? 'Sites only' : renderMode === 'simplified' ? 'Simplified sectors' : 'Full sectors'}
              </span>
            </div>
          </div>

          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={cellsLayerVisible}
              onChange={() => setCellsLayerVisible(!cellsLayerVisible)}
            />
            <span className="toggle-slider" />
          </label>
        </div>
      </div>
    </div>
  );
}

export default CellsToggle;

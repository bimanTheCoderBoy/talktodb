import { useState } from 'react';
import { useMapContext } from '../context/MapContext';
import { useLayerManager } from '../hooks/useLayerManager';
import LayerItem from './layers/LayerItem';


/**
 * Displays list of raster layers with controls for:
 * - Toggling visibility
 */
const MAX_VISIBLE_RASTER_LAYERS = 4;

function LayerManager() {
  const { rasterLayers, dataPath, visibleRasterCount } = useMapContext();
  const {
    toggleLayer,
    updateLayerOpacity,
    updateLayerFilterRange,
    updateLayerResolution,
    flyToLayer,
  } = useLayerManager();
  
  const [expandedLayers, setExpandedLayers] = useState(new Set());
  const [error] = useState(null);

  const isLoading = rasterLayers.length === 0;

  /**
   * Toggle layer expansion
   */
  const toggleExpanded = (id) => {
    setExpandedLayers(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) { 
        newSet.delete(id);  //was expanded -> collapse it
      } else {
        newSet.add(id); //was collapsed -> expand it
      }
      return newSet;
    });
  };

  const maxReached = visibleRasterCount >= MAX_VISIBLE_RASTER_LAYERS;

  return (
    <div className="control-section">
      {/* Visible layer counter */}
      {rasterLayers.length > 0 && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: '8px', padding: '4px 6px',
          background: maxReached ? 'color-mix(in oklch, var(--destructive) 8%, transparent)' : 'color-mix(in oklch, var(--foreground) 4%, transparent)',
          borderRadius: '6px', fontSize: '11px',
          color: maxReached ? 'var(--destructive)' : 'var(--text-secondary)',
          transition: 'all 0.2s',
        }}>
          <span>Active: {visibleRasterCount} / {MAX_VISIBLE_RASTER_LAYERS}</span>
          {maxReached && <span style={{ fontSize: '10px' }}>max reached</span>}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div style={{
          padding: '8px',
          marginBottom: '12px',
          background: 'color-mix(in oklch, var(--destructive) 10%, transparent)',
          borderRadius: '6px',
          fontSize: '11px',
          color: 'var(--destructive)',
        }}>
          {error}
        </div>
      )}

      {/* Layer List */}
      <div className="layer-list"> 
        {rasterLayers.length === 0 ? (
          <div className="no-data">
            {isLoading ? (
              'Loading layers...'
            ) : (
              <>
                No raster layers loaded.<br/>
                <small>Check path: {dataPath}</small>
              </>
            )}
          </div>
        ) : (
          rasterLayers.map(item => (
            <LayerItem
              key={item.id}
              layer={item}
              isExpanded={expandedLayers.has(item.id)}
              onToggleExpand={toggleExpanded}
              onToggleVisibility={toggleLayer}
              onFlyTo={flyToLayer}
              onOpacityChange={updateLayerOpacity}
              onFilterRangeChange={updateLayerFilterRange}
              onResolutionChange={updateLayerResolution}
              disableToggleOn={maxReached && !item.visible}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default LayerManager;



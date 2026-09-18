import { useState } from 'react';
import { Layers, ChevronRight, ChevronLeft, Eye, EyeOff } from 'lucide-react';


function LayerPanel({ settings, onUpdateLayer, hasCellsData = false, hasAllCandidatesData = false, hasCandidateCellsData = false, hasEncodedRaster = false }) {
  const [isCollapsed, setIsCollapsed] = useState(true);

  const layerOrder = ['osm', 'baselineRaster', 'combinedRaster', 'boundary', 'polygon', 'cells', 'allCandidates', 'candidateCells'];

  const handleVisibilityToggle = (layerId) => {
    onUpdateLayer(layerId, { visible: !settings[layerId].visible });
  };

  const handleOpacityChange = (layerId, value) => {
    onUpdateLayer(layerId, { opacity: parseFloat(value) });
  };

  // Filter out layers if no data
  const visibleLayers = layerOrder.filter(id => {
    if (id === 'cells') return hasCellsData;
    if (id === 'allCandidates') return hasAllCandidatesData;
    if (id === 'candidateCells') return hasCandidateCellsData;
    if (id === 'baselineRaster' || id === 'combinedRaster') return hasEncodedRaster;
    return true;
  });

  return (
    <div 
      className={`absolute top-4 right-4 z-20 transition-all duration-300 ${
        isCollapsed ? 'w-10' : 'w-64'
      }`}
    >
      <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-border bg-secondary/50">
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold text-foreground">Layers</span>
            </div>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:bg-accent rounded transition-colors ml-auto"
            title={isCollapsed ? 'Expand panel' : 'Collapse panel'}
          >
            {isCollapsed ? (
              <ChevronLeft className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </button>
        </div>

        {/* Layer Controls */}
        {!isCollapsed && (
          <div className="p-2 space-y-1 max-h-[400px] overflow-y-auto">
            {visibleLayers.map((layerId) => {
              const layer = settings[layerId];
              if (!layer) return null;

              return (
                <div 
                  key={layerId}
                  className="bg-secondary/30 rounded-md p-2.5 space-y-2"
                >
                  {/* Layer Header with Toggle */}
                  <div className="flex items-center justify-between gap-1">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <div 
                        className="w-3 h-3 rounded-sm border border-border shrink-0"
                        style={{ backgroundColor: layer.color }}
                      />
                      <span className="text-xs font-medium text-foreground truncate">
                        {layer.label}
                      </span>
                    </div>
                    <button
                      onClick={() => handleVisibilityToggle(layerId)}
                      className={`p-1 rounded transition-colors shrink-0 ${
                        layer.visible 
                          ? 'text-primary hover:bg-accent' 
                          : 'text-muted-foreground hover:bg-accent'
                      }`}
                      title={layer.visible ? 'Hide layer' : 'Show layer'}
                    >
                      {layer.visible ? (
                        <Eye className="w-3.5 h-3.5" />
                      ) : (
                        <EyeOff className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>

                  {/* Opacity Slider */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground w-12">Opacity</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={layer.opacity}
                      onChange={(e) => handleOpacityChange(layerId, e.target.value)}
                      disabled={!layer.visible}
                      className={`flex-1 h-1 rounded-full appearance-none cursor-pointer
                        ${layer.visible 
                          ? 'bg-secondary accent-primary' 
                          : 'bg-muted opacity-50'
                        }
                        [&::-webkit-slider-thumb]:appearance-none
                        [&::-webkit-slider-thumb]:w-3
                        [&::-webkit-slider-thumb]:h-3
                        [&::-webkit-slider-thumb]:rounded-full
                        [&::-webkit-slider-thumb]:bg-primary
                        [&::-webkit-slider-thumb]:cursor-pointer
                        [&::-moz-range-thumb]:w-3
                        [&::-moz-range-thumb]:h-3
                        [&::-moz-range-thumb]:rounded-full
                        [&::-moz-range-thumb]:bg-primary
                        [&::-moz-range-thumb]:border-0
                        [&::-moz-range-thumb]:cursor-pointer
                      `}
                    />
                    <span className="text-[10px] text-muted-foreground w-8 text-right">
                      {Math.round(layer.opacity * 100)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Collapsed State Icon */}
        {isCollapsed && (
          <div className="p-2 flex justify-center">
            <Layers className="w-4 h-4 text-muted-foreground" />
          </div>
        )}
      </div>
    </div>
  );
}

export default LayerPanel;

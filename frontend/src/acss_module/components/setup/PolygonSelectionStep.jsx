import React from 'react';
import { Hexagon, PenTool, X } from 'lucide-react';
import StatusIndicator, { getStatusBadge } from './StatusIndicator';

function PolygonSelectionStep({ 
  status, 
  isDrawingMode, 
  boundaryRadius, 
  onToggleDrawing, 
  onBoundaryRadiusChange,
  isLocked = false,
}) {
  return (
    <div className={`
      relative p-3 rounded-lg transition-all duration-200
      ${status === 'done' 
        ? 'bg-card/30 border border-transparent' 
        : 'bg-muted/50 border border-border dark:bg-amber-500/10 dark:border-amber-500/30'
      }
    `}>
      <div className="flex items-center gap-3">
        <div className={`
          p-2 rounded-lg
          ${status === 'done' ? 'bg-green-500/20' : 'bg-muted dark:bg-amber-500/20'}
        `}>
          <Hexagon className={`w-4 h-4 ${status === 'done' ? 'text-green-400' : 'text-muted-foreground dark:text-amber-400'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground">Polygon Selection</span>
            <StatusIndicator status={status} />
          </div>
          <div className="mt-1">
            <span className={`
              inline-flex items-center px-2 py-0.5 text-[10px] font-medium 
              rounded-full border capitalize
              ${getStatusBadge(status)}
            `}>
              {status}
            </span>
          </div>

          {/* Polygon Controls */}
          {status === 'pending' && !isLocked && (
            <div className="mt-2">
              <label className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                <span>Boundary Radius (km)</span>
                <span className="text-foreground font-medium">{boundaryRadius} km</span>
              </label>
              <input
                type="range"
                min="1"
                max="20"
                step="0.5"
                value={boundaryRadius}
                onChange={onBoundaryRadiusChange}
                disabled={isLocked}
                className="w-full h-1.5 bg-border dark:bg-secondary rounded-lg appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                  [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full 
                  [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer
                  [&::-webkit-slider-thumb]:hover:bg-primary/80
                  disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          )}

          {/* Draw Polygon Button */}
          {(status === 'pending' || status === 'running') && !isLocked && (
            <button
              onClick={onToggleDrawing}
              disabled={isLocked}
              className={`
                mt-2 w-full flex items-center justify-center gap-2 px-3 py-1.5 
                rounded-lg font-medium text-xs transition-all duration-200
                ${isLocked
                  ? 'bg-muted text-muted-foreground cursor-not-allowed'
                  : isDrawingMode
                    ? 'bg-red-500 hover:bg-red-600 text-white'
                    : 'bg-primary hover:bg-primary/90 text-primary-foreground'
                }
              `}
            >
              {isDrawingMode ? (
                <>
                  <X className="w-3.5 h-3.5" />
                  Cancel Drawing
                </>
              ) : (
                <>
                  <PenTool className="w-3.5 h-3.5" />
                  Draw Polygon
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default PolygonSelectionStep;

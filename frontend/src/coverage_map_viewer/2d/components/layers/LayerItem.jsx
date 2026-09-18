import React from 'react';
import LayerControls from './LayerControls';
import { buildLabelBandFromBaseName } from '../../utils/build_lebel_band';

//it is just a CSS for single layer toggle/flyto/expand control

/**
 * LayerItem Component
 * 
 * Displays a single RSRP layer with:
 * - Name and description
 * - Visibility toggle
 * - Fly to location button
 * - Expandable controls (opacity, filter range)
 */
function LayerItem({ 
  layer, 
  isExpanded, 
  onToggleExpand, 
  onToggleVisibility, 
  onFlyTo,
  onOpacityChange,
  onFilterRangeChange,
  onResolutionChange,
  disableToggleOn = false,
}) {
  return (
    <div style={{
      background: 'color-mix(in oklch, var(--foreground) 3%, transparent)',
      borderRadius: '8px',
      marginBottom: '8px',
      overflow: 'hidden',
    }}>
      {/* Layer Header */}
      <div className="layer-item" style={{ marginBottom: 0 }}>
        <div className="layer-info" style={{ alignItems: 'flex-start', overflow: 'visible' }}>
          <div 
            className="layer-color" 
            style={{ backgroundColor: layer.color, marginTop: '4px' }}
          />
          <div style={{ minWidth: 0 }}>
            <span
              className="layer-name"
              style={{ whiteSpace: 'normal', wordBreak: 'break-word', overflow: 'visible' }}
              title={layer.name}
            >
              {layer.name}
            </span>
            <br />
            {layer.band && (
              <span style={{
                display: 'inline-block',
                fontSize: '9px',
                padding: '1px 5px',
                borderRadius: '4px',
                background: 'color-mix(in oklch, var(--primary) 15%, transparent)',
                color: 'var(--primary)',
                marginTop: '2px',
              }}>
                Band:  {buildLabelBandFromBaseName(layer.baseName)}
              </span>
            )}
            {layer.description && (
              <small style={{ 
                display: 'block', 
                color: 'var(--text-secondary)',
                fontSize: '10px',
                marginTop: '2px',
              }}>
                {layer.description}
              </small>
            )}
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          {/* Expand/Collapse button */}
          <button
            onClick={() => onToggleExpand(layer.id)}
            style={{
              background: 'transparent',
              border: 'none',
              color: isExpanded ? 'var(--primary)' : 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '4px',
              fontSize: '14px',
              lineHeight: 1,
              transition: 'color 0.2s, transform 0.2s',
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
            title={isExpanded ? 'Collapse controls' : 'Expand controls'}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>

          {/* Fly to location button */}
          <button
            onClick={() => onFlyTo(layer)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '4px',
              fontSize: '14px',
              lineHeight: 1,
              transition: 'color 0.2s',
            }}
            title="Fly to location"
            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary)'}
            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--foreground)'}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
              <circle cx="12" cy="10" r="3"/>
            </svg>
          </button>

          {/* Visibility toggle */}
          <label className="toggle-switch" style={disableToggleOn ? { opacity: 0.4, cursor: 'not-allowed' } : {}}>
            <input
              type="checkbox"
              checked={layer.visible}
              disabled={disableToggleOn}
              onChange={() => onToggleVisibility(layer.id)}
            />
            <span className="toggle-slider" />
          </label>
        </div>
      </div>

      {/* Expanded Controls */}
      {isExpanded && (
        <LayerControls 
          layer={layer}
          onOpacityChange={onOpacityChange}
          onFilterRangeChange={onFilterRangeChange}
          onResolutionChange={onResolutionChange}
        />
      )}
    </div>
  );
}

export default LayerItem;

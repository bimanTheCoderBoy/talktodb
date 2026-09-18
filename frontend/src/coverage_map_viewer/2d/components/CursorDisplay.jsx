import React from 'react';
import { useMapContext } from '../context/MapContext';
import { getArrayType, getColorForValue } from '../registry';

function CursorDisplay() {
  const { cursorValues, rasterLayers, getColorTheme } = useMapContext();

  if (rasterLayers.length === 0) return null;

  const hasVisibleLayer = rasterLayers.some((layer) => layer.visible);
  if (!hasVisibleLayer) return null;

  const visibleValues = cursorValues.filter((item) => {
    const layer = rasterLayers.find((l) => l.id === item.layerId);
    return layer && layer.visible;
  });

  const hasValues = visibleValues.length > 0;

  return (
    <div className="rsrp-display">
      <div className="label">Cursor Value</div>
      {hasValues ? (
        visibleValues.map((item, index) => {
          const layer = rasterLayers.find((l) => l.id === item.layerId);
          const arrayTypeId = layer?.arrayTypeId || 'rsrp';
          const config = getArrayType(arrayTypeId);
          const colorTheme = getColorTheme(arrayTypeId);
          const { color, label: quality } = getColorForValue(item.value, arrayTypeId, colorTheme);

          const displayColor =  color;

          return (
            <div
              key={item.layerId}
              style={{
                marginTop: index > 0 ? '10px' : '4px',
                paddingTop: index > 0 ? '10px' : '0',
                borderTop: index > 0 ? '1px solid var(--border)' : 'none',
              }}
            >
              <div
                style={{
                  fontSize: '10px',
                  color: 'var(--text-secondary)',
                  marginBottom: '2px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.layerName}
              </div>
              <div className="value" style={{ color: displayColor }}>
                {item.value.toFixed(1)}
                <span className="unit">{config.unit}</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {config.label}: <span style={{ color: displayColor }}>{quality}</span>
              </div>
            </div>
          );
        })
      ) : (
        <div style={{ marginTop: '4px' }}>
          <div className="value" style={{ color: 'var(--text-secondary)' }}>
            --<span className="unit"></span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Hover over a layer
          </div>
        </div>
      )}
    </div>
  );
}

export default CursorDisplay;

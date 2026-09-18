import { formatResolution, RESOLUTION_OPTIONS } from '../../utils/resolution';
import { getArrayType } from '../../registry';
function LayerControls({ layer, onOpacityChange, onFilterRangeChange, onResolutionChange }) {
  const unit = getArrayType(layer.arrayTypeId || 'rsrp').unit;

  return (
    <div
      style={{
        padding: '12px',
        borderTop: '1px solid var(--border)',
        background: 'color-mix(in oklch, var(--foreground) 5%, transparent)',
      }}
    >
      {/* Opacity Slider */}
      <div style={{ marginBottom: '12px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            marginBottom: '6px',
          }}
        >
          <span>Opacity</span>
          <span>{Math.round(layer.opacity * 100)}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={layer.opacity}
          onChange={(e) => onOpacityChange(layer.id, parseFloat(e.target.value))}
          style={{ width: '100%' }}
        />
      </div>

      {/* Filter Range */}
      <div style={{ marginBottom: '8px' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
          Filter Range
        </div>

        <div style={{ marginBottom: '8px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '10px',
              color: 'var(--text-secondary)',
              marginBottom: '4px',
            }}
          >
            <span>Min</span>
            <span>
              {Number(layer.filterRange.min).toFixed(2)} {unit}
            </span>
          </div>
          <input
            type="range"
            min={layer.filterFixedRange.min}
            max={layer.filterFixedRange.max}
            value={layer.filterRange.min}
            onChange={(e) => onFilterRangeChange(layer.id, 'min', parseInt(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>

        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '10px',
              color: 'var(--text-secondary)',
              marginBottom: '4px',
            }}
          >
            <span>Max</span>
            <span>
              {Number(layer.filterRange.max).toFixed(2)} {unit}
            </span>
          </div>
          <input
            type="range"
            min={layer.filterFixedRange.min}
            max={layer.filterFixedRange.max}
            value={layer.filterRange.max}
            onChange={(e) => onFilterRangeChange(layer.id, 'max', parseInt(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      {/* Resolution Selector */}
      <div style={{ marginTop: '12px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            marginBottom: '8px',
            
          }}
        >
          <span >Resolution</span>
          <span style={{ fontSize: '10px', opacity: 0.7 }}>
            Base: {formatResolution(layer.baseResolution)}
          </span>
        </div>
        <select
          value={layer.selectedResolution === null ? 'original' : layer.selectedResolution}
          onChange={(e) => {
            const value = e.target.value;
            onResolutionChange(layer.id, value === 'original' ? null : parseInt(value, 10));
          }}
          style={{
            width: '100%',
            padding: '8px 10px',
            background: 'var(--bg-panel)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            color: 'var(--text-primary)',
            fontSize: '12px',
            cursor: 'pointer',
            outline: 'none',
            backgroundColor: 'var(--bg-panel)',
          }}
        >
          <option value="original">Original ({formatResolution(layer.baseResolution)})</option>
          {RESOLUTION_OPTIONS.filter((res) => res >= layer.baseResolution).map((res) => (
            <option key={res} value={res}>
              {res}m
            </option>
          ))}
        </select>
        <p
          style={{
            fontSize: '10px',
            color: 'var(--text-secondary)',
            marginTop: '6px',
            opacity: 0.7,
          }}
        >
          Lower resolution = faster rendering
        </p>
      </div>
    </div>
  );
}

export default LayerControls;

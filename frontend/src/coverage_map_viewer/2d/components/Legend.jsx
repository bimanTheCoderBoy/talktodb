import React, { useMemo } from 'react';
import { useMapContext } from '../context/MapContext';
import { getArrayType, getThemes, resolveColorBands } from '../registry';

function formatBandSample(band, index, bands, unit) {
  if (Number.isFinite(band.min)) {
    return unit ? `${band.min} ${unit}` : `${band.min}`;
  }
  // Catch-all band (min: -Infinity): show upper bound from the previous finite band
  const prev = bands[index - 1];
  if (prev && Number.isFinite(prev.min)) {
    return unit ? `< ${prev.min} ${unit}` : `< ${prev.min}`;
  }
  return band.label;
}

/** Grayscale band colors can be near-black; keep swatches accurate but lift label text for dark UI. */
function legendLabelColor(color, colorTheme) {
  if (colorTheme !== 'grayscale' || typeof color !== 'string') return color;
  const hex = color.replace('#', '');
  if (hex.length !== 6) return color;
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance < 0.45 ? '#9ca3af' : color;
}

function TypeLegend({ arrayTypeId, colorTheme, onColorThemeChange }) {
  const config = getArrayType(arrayTypeId);

  const legendEntries = useMemo(() => {
    const bands = resolveColorBands(arrayTypeId, colorTheme);
    const entries = bands.map((band, index) => ({
      label: band.label,
      color: band.color,
      sampleDisplay: formatBandSample(band, index, bands, config.unit),
    }));
    const noData = config.noDataEntry || { label: 'No Data', color: '#6b7280' };
    entries.push({
      label: noData.label,
      color: noData.color,
      sampleDisplay: noData.label,
    });
    return entries;
  }, [arrayTypeId, colorTheme, config]);

  const themeOptions = useMemo(
    () => getThemes(arrayTypeId),
    [arrayTypeId]
  );

  // Bands are high→low; gradient bar reads poor (left) → excellent (right)
  const gradientBackground = useMemo(() => {
    const bands = resolveColorBands(arrayTypeId, colorTheme);
    const colors = [...bands].reverse().map((band) => band.color);
    if (colors.length === 0) return undefined;
    if (colors.length === 1) return colors[0];
    const stops = colors.map((color, i) => {
      const pct = (i / (colors.length - 1)) * 100;
      return `${color} ${pct}%`;
    });
    return `linear-gradient(90deg, ${stops.join(', ')})`;
  }, [arrayTypeId, colorTheme]);

  return (
    <div className="control-section">
      <div className="section-title">{config.label}</div>
      <div style={{ marginBottom: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label style={{ color: 'var(--text-secondary)', fontSize: '11px', fontWeight: 600 }}>
          Color Theme
        </label>
        <select
          value={colorTheme}
          onChange={(e) => onColorThemeChange(arrayTypeId, e.target.value)}
          className="w-full appearance-none px-3 py-1.5 text-sm rounded-lg border border-border bg-secondary text-foreground cursor-pointer outline-none transition-colors hover:border-primary/50 focus:ring-2 focus:ring-primary/50"
        >
          {themeOptions.map((option) => (
            <option key={option.id} value={option.id} className="bg-popover text-popover-foreground">
              {option.name}
            </option>
          ))}
        </select>
      </div>

      <div className="legend">
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--map-accent)',
          marginBottom: '8px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}>
          Legend — {config.label} (<span style={{ textTransform: 'none' }}>{config.unit}</span>)
        </div>
        <div className="legend-gradient" style={{ background: gradientBackground }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '12px' }}>
          {legendEntries.map((category, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '6px 8px',
                background: 'color-mix(in oklch, var(--foreground) 3%, transparent)',
                borderRadius: '4px',
                fontSize: '11px',
              }}
            >
              <span
                style={{
                  width: '16px',
                  height: '16px',
                  background: category.color,
                  borderRadius: '3px',
                  flexShrink: 0,
                  boxShadow: `0 0 4px ${category.color}40`,
                }}
              />
              <span
                style={{
                  color: 'var(--text-secondary)',
                  minWidth: '100px',
                  fontFamily: 'Consolas, monospace',
                  fontSize: '10px',
                }}
              >
                {category.sampleDisplay}
              </span>
              <span style={{ color: 'var(--text-secondary)', opacity: 0.5 }}>&rarr;</span>
              <span style={{ color: legendLabelColor(category.color, colorTheme), fontWeight: '600' }}>{category.label}</span>
            </div>
          ))}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            marginTop: '12px',
            padding: '8px 10px',
            background: 'color-mix(in oklch, var(--filtered, #87CEEB) 15%, transparent)',
            borderRadius: '6px',
            fontSize: '11px',
            color: 'var(--filtered, #87CEEB)',
            border: '1px solid color-mix(in oklch, var(--filtered, #87CEEB) 30%, transparent)',
          }}
        >
          <span
            style={{
              width: '16px',
              height: '16px',
              background: 'color-mix(in oklch, var(--filtered, #87CEEB) 60%, transparent)',
              borderRadius: '3px',
              border: '2px solid var(--filtered, #87CEEB)',
              flexShrink: 0,
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>Outside range</span>
          <span style={{ opacity: 0.5 }}>&rarr;</span>
          <span style={{ fontWeight: '600' }}>Filtered</span>
        </div>
      </div>
    </div>
  );
}

function Legend() {
  const { getColorTheme, setColorTheme, rasterLayers } = useMapContext();

  const activeTypes = useMemo(() => {
    const seen = new Set();
    const types = [];
    for (const layer of rasterLayers) {
      const typeId = layer.arrayTypeId || 'rsrp';
      if (!seen.has(typeId)) {
        seen.add(typeId);
        types.push(typeId);
      }
    }
    if (types.length === 0) types.push('rsrp');
    return types;
  }, [rasterLayers]);

  return (
    <>
      {activeTypes.map((typeId) => (
        <TypeLegend
          key={typeId}
          arrayTypeId={typeId}
          colorTheme={getColorTheme(typeId)}
          onColorThemeChange={setColorTheme}
        />
      ))}
    </>
  );
}

export default Legend;

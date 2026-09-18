import React, { useMemo, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import { toast } from 'react-toastify';
import { useMapContext } from '../context/MapContext';
import { useProjectContext } from '@/context/ProjectContext';
import { formatStats, statsToCSV, pointInPolygon } from '../utils/stats';
import { getArrayType } from '../registry';

function PolygonStatsPanel() {
  const { drawnPolygons, activePolygonId, setActivePolygonId, rasterLayers, cellsData } = useMapContext();
  const { projectName } = useProjectContext();

  const navigate = useNavigate();
  const [position, setPosition] = useState({ x: window.innerWidth - 340, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const activePolygon = useMemo(() => {
    return drawnPolygons.find(p => p.id === activePolygonId);
  }, [drawnPolygons, activePolygonId]);

  const formattedByLayer = useMemo(() => {
    const byLayer = activePolygon?.stats?.byLayer;
    if (!byLayer || byLayer.length === 0) return [];
    return byLayer.map((layerStat) => {
      const typeId = layerStat.arrayTypeId || 'rsrp';
      const config = getArrayType(typeId);
      const unit = config.unit;
      return {
        ...layerStat,
        unit,
        typelabel: config.label,
        formatted: formatStats(layerStat.stats, unit),
      };
    });
  }, [activePolygon]);

  const totalSamples = useMemo(() => {
    return formattedByLayer.reduce((sum, l) => sum + (l.sampleCount || 0), 0);
  }, [formattedByLayer]);

  const handleMouseDown = useCallback((e) => {
    if (e.target.tagName === 'BUTTON') return;
    setIsDragging(true);
    dragOffset.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
    e.preventDefault();
  }, [position]);

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return;
    const newX = Math.max(0, Math.min(window.innerWidth - 340, e.clientX - dragOffset.current.x));
    const newY = Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffset.current.y));
    setPosition({ x: newX, y: newY });
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  React.useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  if (!activePolygon || formattedByLayer.length === 0) {
    return null;
  }

  const { stats } = activePolygon;

  const handleExportLayerCSV = (layerStat) => {
    const csv = statsToCSV(layerStat.stats, `${activePolygon.name} - ${layerStat.layerName}`, layerStat.unit);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activePolygon.name.replace(/\s+/g, '_')}_${String(layerStat.layerName || 'layer').replace(/\s+/g, '_')}_stats.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExportLayerJSON = (layerStat) => {
    const data = {
      polygon: {
        id: activePolygon.id,
        name: activePolygon.name,
        area: stats.area,
        createdAt: activePolygon.createdAt,
      },
      layer: {
        id: layerStat.layerId,
        name: layerStat.layerName,
        arrayType: layerStat.arrayTypeId,
      },
      statistics: layerStat.stats,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activePolygon.name.replace(/\s+/g, '_')}_${String(layerStat.layerName || 'layer').replace(/\s+/g, '_')}_stats.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExportAllJSON = () => {
    const data = {
      polygon: {
        id: activePolygon.id,
        name: activePolygon.name,
        area: stats.area,
        createdAt: activePolygon.createdAt,
      },
      byLayer: stats.byLayer,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activePolygon.name.replace(/\s+/g, '_')}_stats.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleClose = () => {
    setActivePolygonId(null);
  };

  const handleImproveWithACSS = () => {
    if (!projectName) {
      toast.warn('Please set a project name before using ASP.');
      return;
    }
    if (!activePolygon?.coords || activePolygon.coords.length < 3) {
      toast.warn('Polygon data is incomplete.');
      return;
    }

    const acssSessionId = uuidv4();

    // Filter cellsData (from MapContext) to sites whose (longitude, latitude) lies
    // inside the active polygon. cellsData has the per-site shape
    // [{site_iid, longitude, latitude, cells: [{azimuth, pci, band, technology, ...}]}, ...]
    // — exactly what the backend azimuth detector consumes. Do NOT use stats.cellStats:
    // that's a count summary {cells, sites, byTechnology, byBand}, not a per-site list.
    const cellsInPolygon = (cellsData || []).filter(site =>
      pointInPolygon(site.longitude, site.latitude, activePolygon.coords)
    );

    const acssHandoff = {
      polygonCoords: activePolygon.coords,
      initialRadiusKm: 5,
      source: 'coverage-2d',
      // ASP auto-gen extension (phase 02): consumed by the auto-gen setup-time
      // config form. Does NOT include a server-side BIL path — auto-gen runs at
      // execution time (after baseline coverage produces the BIL).
      arrayType: rasterLayers?.[0]?.arrayTypeId || 'LTE_Best_RSRP',
      cellsInPolygon,
    };

    sessionStorage.setItem('acssHandoff', JSON.stringify(acssHandoff));

    navigate(`/asp/${projectName}/${acssSessionId}`, {
      state: { acssHandoff },
    });
  };

  return (
    <div 
      ref={panelRef}
      style={{
        position: 'absolute',
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: '320px',
        background: 'var(--bg-panel)',
        borderRadius: '12px',
        boxShadow: '0 8px 32px color-mix(in oklch, var(--foreground) 15%, transparent)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border)',
        overflow: 'hidden',
        zIndex: 1001,
        cursor: isDragging ? 'grabbing' : 'default',
        userSelect: 'none',
      }}
    >
      {/* Header - Draggable */}
      <div 
        onMouseDown={handleMouseDown}
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          background: 'color-mix(in oklch, var(--map-accent) 10%, transparent)',
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
      >
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>
              {activePolygon.name}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {stats.area?.toFixed(3)} km² • {totalSamples.toLocaleString()} samples
            </div>
            {stats.cellStats?.cells > 0 && (
              <div style={{ fontSize: '11px', color: 'var(--success, #00d26a)', marginTop: '2px' }}>
                📡 {stats.cellStats.cells} cells in {stats.cellStats.sites} sites
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <button
              onClick={handleExportAllJSON}
              style={{
                padding: '4px 8px',
                background: 'color-mix(in oklch, var(--primary) 20%, transparent)',
                border: 'none',
                borderRadius: '4px',
                color: 'var(--primary)',
                cursor: 'pointer',
                fontSize: '10px',
              }}
              title="Export all as JSON"
            >
              JSON
            </button>
            <button
              onClick={handleClose}
              style={{
                padding: '4px 6px',
                background: 'transparent',
                border: 'none',
                borderRadius: '4px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '14px',
                marginLeft: '4px',
              }}
              title="Close panel"
            >
              ×
            </button>
          </div>
        </div>
      </div>

      {/* Statistics Content */}
      <div style={{ padding: '12px 16px', maxHeight: '400px', overflowY: 'auto' }}>
        {/* Cell Statistics */}
        {stats.cellStats && stats.cellStats.cells > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <div style={{ 
              fontSize: '11px', 
              color: 'var(--map-accent)', 
              marginBottom: '8px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}>
              📡 Cell Sites in Region
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
              <StatCard label="Sites" value={stats.cellStats.sites} color="#00d26a" />
              <StatCard label="Cells" value={stats.cellStats.cells} color="#3b82f6" />
            </div>

            {Object.keys(stats.cellStats.byTechnology).length > 0 && (
              <div style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  By Technology
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {Object.entries(stats.cellStats.byTechnology).map(([tech, count]) => (
                    <span
                      key={tech}
                      style={{
                        padding: '3px 8px',
                        background: 'color-mix(in oklch, var(--primary) 20%, transparent)',
                        borderRadius: '4px',
                        fontSize: '10px',
                        color: 'var(--primary)',
                      }}
                    >
                      {tech}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(stats.cellStats.byBand).length > 0 && (
              <div>
                <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  By Band
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {Object.entries(stats.cellStats.byBand).map(([band, count]) => (
                    <span
                      key={band}
                      style={{
                        padding: '3px 8px',
                        background: 'color-mix(in oklch, var(--success, #00d26a) 20%, transparent)',
                        borderRadius: '4px',
                        fontSize: '10px',
                        color: 'var(--success, #00d26a)',
                      }}
                    >
                      {band}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Per-layer Stats */}
        <div style={{ marginTop: '8px' }}>
          <div style={{
            fontSize: '11px',
            color: 'var(--map-accent)',
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}>
            {formattedByLayer.length === 1 ? 'Layer Statistics' : 'Per Raster Layer'}
          </div>

          {formattedByLayer.map((layerStat) => (
            <div
              key={layerStat.layerId || layerStat.layerName}
              style={{
                padding: '10px',
                marginBottom: '10px',
                background: 'color-mix(in oklch, var(--foreground) 3%, transparent)',
                borderRadius: '10px',
                border: '1px solid color-mix(in oklch, var(--foreground) 6%, transparent)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
                    {layerStat.layerName}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                    {layerStat.formatted?.count || 0} samples • {layerStat.typelabel} ({layerStat.unit})
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <button
                    onClick={() => handleExportLayerCSV(layerStat)}
                    style={{
                      padding: '4px 8px',
                      background: 'color-mix(in oklch, var(--primary) 20%, transparent)',
                      border: 'none',
                      borderRadius: '4px',
                      color: 'var(--primary)',
                      cursor: 'pointer',
                      fontSize: '10px',
                    }}
                    title="Export this layer as CSV"
                  >
                    CSV
                  </button>
                  <button
                    onClick={() => handleExportLayerJSON(layerStat)}
                    style={{
                      padding: '4px 8px',
                      background: 'color-mix(in oklch, var(--primary) 20%, transparent)',
                      border: 'none',
                      borderRadius: '4px',
                      color: 'var(--primary)',
                      cursor: 'pointer',
                      fontSize: '10px',
                    }}
                    title="Export this layer as JSON"
                  >
                    JSON
                  </button>
                </div>
              </div>

              {/* Signal Strength */}
              <div style={{ marginTop: '10px' }}>
                <div style={{ 
                  fontSize: '10px', 
                  color: 'var(--map-accent)', 
                  marginBottom: '6px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}>
                  {layerStat.typelabel}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <StatCard label="Minimum" value={layerStat.formatted?.min} color="#ff4757" />
                  <StatCard label="Maximum" value={layerStat.formatted?.max} color="#00d26a" />
                  <StatCard label="Mean" value={layerStat.formatted?.mean} color="#3b82f6" />
                  <StatCard label="Median" value={layerStat.formatted?.median} color="#8b5cf6" />
                </div>
              </div>

              {/* Variability */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                <StatCard label="Std Dev" value={layerStat.formatted?.stdDev} />
                <StatCard label="Range" value={layerStat.formatted?.range} />
              </div>

              {/* Percentiles */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '4px', marginTop: '8px' }}>
                <MiniStatCard label="5th" value={layerStat.formatted?.percentiles?.p5} />
                <MiniStatCard label="25th" value={layerStat.formatted?.percentiles?.p25} />
                <MiniStatCard label="50th" value={layerStat.formatted?.percentiles?.p50} />
                <MiniStatCard label="75th" value={layerStat.formatted?.percentiles?.p75} />
                <MiniStatCard label="95th" value={layerStat.formatted?.percentiles?.p95} />
              </div>

              {/* Quality Distribution */}
              {layerStat?.stats?.qualityDistribution?.length > 0 && (
                <div style={{ marginTop: '10px' }}>
                  <QualityBar quality={layerStat.stats.qualityDistribution} />
                  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${layerStat.formatted?.quality?.length || 4}, 1fr)`, gap: '4px', marginTop: '8px' }}>
                    {layerStat.formatted?.quality?.map((entry) => (
                      <QualityLabel key={entry.label} label={entry.label} value={entry.value} color={entry.color} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Improve With ASP CTA */}
      <button
        onClick={handleImproveWithACSS}
        className='fixed bottom-6 right-6 z-50 px-4 py-2 rounded-lg font-bold text-white text-sm bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-700 hover:to-amber-600 shadow-lg shadow-amber-600/50 animate-pulse transition-all duration-200 active:scale-95'
      >
        Improve With ASP?
      </button>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      padding: '8px 10px',
      background: 'color-mix(in oklch, var(--foreground) 3%, transparent)',
      borderRadius: '6px',
      borderLeft: color ? `3px solid ${color}` : 'none',  
    }}>
      <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>
        {label}
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: '500' }}>
        {value}
      </div>
    </div>
  );
}

function MiniStatCard({ label, value }) {
  const numValue = value?.split(' ')[0] || value;
  return (
    <div style={{
      padding: '4px',
      background: 'color-mix(in oklch, var(--foreground) 3%, transparent)',
      borderRadius: '4px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>
        {label}
      </div>
      <div style={{ fontSize: '10px', color: 'var(--text-primary)' }}>
        {numValue}
      </div>
    </div>
  );
}

function QualityBar({ quality }) {
  if (!Array.isArray(quality)) return null;
  return (
    <div style={{
      display: 'flex',
      height: '8px',
      borderRadius: '4px',
      overflow: 'hidden',
    }}>
      {quality.map((entry) => (
        <div key={entry.label} style={{ width: `${entry.percentage}%`, background: entry.color }} />
      ))}
    </div>
  );
}

function QualityLabel({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ 
        width: '8px', 
        height: '8px', 
        borderRadius: '50%', 
        background: color,
        margin: '0 auto 4px',
      }} />
      <div style={{ fontSize: '9px', color: 'var(--text-secondary)' }}>{label}</div>
      <div style={{ fontSize: '10px', color: 'var(--text-primary)' }}>{value}</div>
    </div>
  );
}

export default PolygonStatsPanel;

import React, { useEffect } from 'react';
import {
  MapShell, CellsLayer, DrawPolygon, PolygonLayer,
  MapFeatureSelect, FitToCords,
} from '../map_primitives_ol';
import { useMap } from '../map_primitives_ol/MapContext';
import { fromLonLat } from 'ol/proj';
import { boundingExtent } from 'ol/extent';

function FitToSites({ sites, trigger }) {
  const map = useMap();

  useEffect(() => {
    if (!map || trigger === 0) return;
    const valid = sites.filter(
      s =>
        typeof s.latitude === 'number' && !isNaN(s.latitude) &&
        typeof s.longitude === 'number' && !isNaN(s.longitude),
    );
    if (valid.length === 0) return;

    try {
      const pts = valid.map(s => fromLonLat([s.longitude, s.latitude]));
      const extent = boundingExtent(pts);
      map.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 18, duration: 600 });
    } catch (e) {
      console.error('FitToSites error:', e);
    }
  }, [map, trigger]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

/**
 * Pure map renderer. Popup lives in the parent (TelecomMapContainer),
 * so single-click / double-click do NOT cause SiteMap to re-render.
 *
 * Props:
 *  - sites             : ALL sites array (with cell.selected flags)
 *  - projectBoundary   : [[lon,lat],...] project config polygon (dashed display)
 *  - drawEnabled       : whether the OL Draw interaction is active
 *  - drawKey           : number — increment to force DrawPolygon remount
 *  - polygonRing       : [[lon,lat],...] current user polygon, or null
 *  - onPolygonDrawn    : (ring) => void
 *  - onSelect          : (info|null) => void — single-click (popup)
 *  - onDblClick        : (info) => void — double-click (toggle)
 *  - fitTrigger        : number — increment to re-fit map
 */
function SiteMap({
  sites = [],
  projectBoundary = null,
  drawEnabled = false,
  drawKey = 0,
  polygonRing = null,
  onPolygonDrawn,
  onSelect,
  onDblClick,
  fitTrigger = 0,
}) {
  return (
    <div className="w-full h-full relative">
      <MapShell className="w-full h-full">
        {projectBoundary && <FitToCords cords={projectBoundary} />}
        <FitToSites sites={sites.filter(site => {
          const { cells } = site;
          if (!cells) return false; 
          return cells.some(cell => cell.selected);
        })} trigger={fitTrigger} />

        <CellsLayer data={sites} showSelectionState />

        <MapFeatureSelect
          onSelect={onSelect}
          onDblClick={onDblClick}
        />

        <DrawPolygon
          key={drawKey}
          enabled={drawEnabled}
          initialPolygon={polygonRing}
          onChange={onPolygonDrawn}
        />

        {/* Project config boundary — dashed green line */}
        {projectBoundary && (
          <PolygonLayer
            polygonCoords={projectBoundary}
            strokeColor="#22c55e"
            fillColor="rgba(34, 197, 94, 0.05)"
            lineDash={[10, 8]}
            strokeWidth={2.5}
          />
        )}

        {/* User-drawn polygon — solid blue (display-only when not drawing) */}
        {polygonRing && !drawEnabled && (
          <PolygonLayer
            polygonCoords={polygonRing}
            strokeColor="#3b82f6"
            fillColor="rgba(59, 130, 246, 0.15)"
          />
        )}
      </MapShell>

      {drawEnabled && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10
          bg-primary/90 text-primary-foreground px-4 py-2 rounded-lg text-sm
          shadow-lg backdrop-blur-sm pointer-events-none">
          Click to add vertices &bull; Double-click to finish
        </div>
      )}
    </div>
  );
}

export default React.memo(SiteMap);

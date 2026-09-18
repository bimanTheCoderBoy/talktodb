import { useEffect, useRef } from 'react';
import { useMap } from './MapContext';

/**
 * Attaches OpenLayers click + hover handlers and emits selected feature info.
 *
 * Props:
 *  - onSelect(info|null)  : single-click callback
 *  - onDblClick(info)     : optional double-click callback. When provided, single-click
 *                           is delayed ~300ms to distinguish from double-click.
 *  - hitTolerance         : pixel tolerance for feature detection
 */
function MapFeatureSelect({ onSelect, onDblClick, hitTolerance = 5 }) {
  const map = useMap();
  const clickTimerRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  const onDblClickRef = useRef(onDblClick);
  onSelectRef.current = onSelect;
  onDblClickRef.current = onDblClick;

  useEffect(() => {
    if (!map) return;

    const findFeature = (evt) => {
      const pixel = map.getEventPixel(evt.originalEvent);
      let found = null;
      map.forEachFeatureAtPixel(
        pixel,
        (f) => {
          const t = f.get('featureType');
          if (t === 'cell' || t === 'site' || t === 'sectorSummary') { found = f; return true; }
          return false;
        },
        { hitTolerance },
      );
      return found;
    };

    const buildInfo = (f) => ({
      type: f.get('featureType') === 'sectorSummary' ? 'site' : f.get('featureType'),
      cell: f.get('cellData'),
      site: f.get('siteData'),
    });

    // const handlePointerMove = (evt) => {
    //   const pixel = map.getEventPixel(evt.originalEvent);
    //   let hit = false;
    //   map.forEachFeatureAtPixel(
    //     pixel,
    //     (f) => {
    //       const t = f.get('featureType');
    //       if (t === 'cell' || t === 'site') { hit = true; return true; }
    //       return false;
    //     },
    //     { hitTolerance },
    //   );
    //   map.getTargetElement().style.cursor = hit ? 'pointer' : '';
    // };

    const handleClick = (evt) => {
      const feature = findFeature(evt);
      const info = feature ? buildInfo(feature) : null;

      if (onDblClickRef.current) {
        if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
        clickTimerRef.current = setTimeout(() => {
          clickTimerRef.current = null;
          if (onSelectRef.current) onSelectRef.current(info);
        }, 300);
      } else {
        if (onSelectRef.current) onSelectRef.current(info);
      }
    };

    const handleDblClick = (evt) => {
      if (!onDblClickRef.current) return;
      if (clickTimerRef.current) {
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      const feature = findFeature(evt);
      if (feature) onDblClickRef.current(buildInfo(feature));
    };

    // map.on('pointermove', handlePointerMove);
    map.on('click', handleClick);
    map.on('dblclick', handleDblClick);

    return () => {
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
      // map.un('pointermove', handlePointerMove);
      map.un('click', handleClick);
      map.un('dblclick', handleDblClick);
      try { map.getTargetElement().style.cursor = ''; } catch { /* */ }
    };
  }, [map, hitTolerance]);

  return null;
}

export default MapFeatureSelect;

import { useCallback, useRef } from 'react';
import { toLonLat } from 'ol/proj';

/**
 * useRasterCursor Hook
 *
 * Samples pre-decoded raster values at the cursor position across all visible layers.
 * Extracted from MapView's pointermove handler to keep MapView focused on OL map management.
 *
 * @param {Object}  rasterDataRef - Ref to Map<layerId, {decodedValues, width, height, bounds, layerName}>
 * @param {Array}   rasterLayersRef - Ref keeping latest rasterLayers (avoids stale closures)
 * @param {Function} setCoordinates
 * @param {Function} setCursorValues
 * @param {Function} setActiveMapId
 * @param {string}   mapId
 */
export function useRasterCursor({
  rasterDataRef,
  rasterLayersRef,
  setCoordinates,
  setCursorValues,
  setActiveMapId,
  mapId,
}) {
  const lastMoveRef = useRef(0);

  const handlePointerMove = useCallback(
    (evt) => {
      const now = Date.now();
      if (now - lastMoveRef.current < 50) return;
      lastMoveRef.current = now;

      setActiveMapId(mapId);

      const [lon, lat] = toLonLat(evt.coordinate);
      setCoordinates({ lat: lat.toFixed(6), lon: lon.toFixed(6) });

      const values = [];
      const visibleIds = new Set(
        rasterLayersRef.current.filter((l) => l.visible).map((l) => l.id)
      );

      for (const [id, data] of rasterDataRef.current.entries()) {
        if (!visibleIds.has(id)) continue;

        const { decodedValues, width, height, bounds, layerName } = data;

        if (
          lon >= bounds.west &&
          lon <= bounds.east &&
          lat >= bounds.south &&
          lat <= bounds.north
        ) {
          const xRatio = (lon - bounds.west) / (bounds.east - bounds.west);
          const yRatio = (bounds.north - lat) / (bounds.north - bounds.south);
          const x = Math.max(0, Math.min(width - 1, Math.floor(xRatio * width)));
          const y = Math.max(0, Math.min(height - 1, Math.floor(yRatio * height)));
          const idx = y * width + x;
          const val = decodedValues[idx];

          if (!isNaN(val)) {
            values.push({ layerId: id, layerName: layerName || id, value: val });
          }
        }
      }

      setCursorValues(values);
    },
    [rasterDataRef, rasterLayersRef, setCoordinates, setCursorValues, setActiveMapId, mapId]
  );

  const handlePointerOut = useCallback(() => {
    setCursorValues([]);
  }, [setCursorValues]);

  return { handlePointerMove, handlePointerOut };
}

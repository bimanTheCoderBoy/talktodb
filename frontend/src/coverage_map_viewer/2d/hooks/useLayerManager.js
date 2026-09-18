import { useCallback, useRef, useEffect } from 'react';
import ImageStatic from 'ol/source/ImageStatic';
import { useMapContext } from '../context/MapContext';
import { getDataFileUrl } from '../utils/dataPath';
import { getArrayType, getLayerColor, resolveColorBands } from '../registry';
import { ensureProjection, boundsToExtent, boundsToWGS84 } from '../raster/projection';
import { loadImageAsData, calculateResolutionMetersPerPixel } from '../utils/imageIO';
import { decodePixels } from '../raster/decodeImage';
import { colorizeFromValues } from '../raster/colorize';
import { createRasterLayer } from '../raster/createRasterLayer';

const DEFAULT_OPACITY = 0.8;
const DEFAULT_RESOLUTION = 500;
const MAX_VISIBLE_RASTER_LAYERS = 4;



/**
 * useLayerManager Hook
 *
 * Manages raster layer lifecycle using the registry + raster pipeline.
 * Works with any array type registered in the registry.
 */
export function useLayerManager() {
  const {
    mapRef,
    sharedViewRef,
    rasterLayers,
    setRasterLayers,
    rasterDataRef,
    dataPath,
    colorThemes,
    getColorTheme,
  } = useMapContext();

  const hasLoadedRef = useRef(false);
  const debounceTimerRef = useRef(null);
  const pendingRefreshRef = useRef(new Set());

  /**
   * Add a new raster layer from a base filename.
   * Reads metadata to determine the array type, then runs the generic pipeline.
   */
  const addLayer = useCallback(async (baseName) => {
    const id = `raster-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const colorIndex = rasterLayers.length;

    try {
      const metaResponse = await fetch(getDataFileUrl(dataPath, `${baseName}.json`));
      if (!metaResponse.ok) {
        throw new Error(`Could not load metadata: ${baseName}.json`);
      }
      const metadata = await metaResponse.json();

      const arrayTypeId = metadata.type || 'rsrp';
      const config = getArrayType(arrayTypeId);

      const sourceEpsg = metadata.epsg || 'EPSG:4326';
      await ensureProjection(sourceEpsg);

      const extent = boundsToExtent(metadata.bounds, sourceEpsg);
      const boundsWGS84 = boundsToWGS84(metadata.bounds, sourceEpsg);

      const valMin = metadata.rsrpMin ?? metadata.valueMin ?? config.defaultMin;
      const valMax = metadata.rsrpMax ?? metadata.valueMax ?? config.defaultMax;

      const pngUrl = getDataFileUrl(dataPath, `${baseName}.png`);
      const { imageData, width, height } = await loadImageAsData(pngUrl);

      const decodedValues = decodePixels(imageData, arrayTypeId, valMin, valMax);

      const baseResolution = calculateResolutionMetersPerPixel(metadata.bounds, width, height, sourceEpsg);
      const initialResolution = baseResolution < DEFAULT_RESOLUTION ? DEFAULT_RESOLUTION : null;

      rasterDataRef.current.set(id, {
        decodedValues,
        width,
        height,
        bounds: boundsWGS84,
        valueMin: valMin,
        valueMax: valMax,
        baseResolution,
        layerName: metadata.name || baseName,
      });

      const colorBands = resolveColorBands(arrayTypeId, getColorTheme(arrayTypeId));
      const processedImageUrl = colorizeFromValues(decodedValues, width, height, {
        targetResolution: initialResolution,
        baseResolution,
        colorBands,
        filterRange: { min: valMin, max: valMax },
        opacity: DEFAULT_OPACITY,
      });

      const layer = createRasterLayer(processedImageUrl, extent, {
        zIndex: colorIndex + 1,
        visible: false,
      });

      if (sharedViewRef.current) {
        const size = mapRef.current ? mapRef.current.getSize() : undefined;
        sharedViewRef.current.fit(extent, {
          padding: [50, 50, 50, 50],
          maxZoom: 15,
          size,
        });
      }

      const band = baseName;

      const newLayerData = {
        id,
        name: metadata.name,
        description: metadata.description,
        baseName,
        metadata,
        sourceEpsg,
        layer,
        visible: false,
        color: getLayerColor(colorIndex),
        opacity: DEFAULT_OPACITY,
        filterRange: { min: valMin, max: valMax },
        filterFixedRange: { min: valMin, max: valMax },
        baseResolution,
        selectedResolution: initialResolution,
        arrayTypeId,
        band,
      };

      setRasterLayers((prev) => [...prev, newLayerData]);
      return id;
    } catch (err) {
      console.error(`Failed to load layer ${baseName}:`, err);
      throw err;
    }
  }, [rasterLayers.length, dataPath, rasterDataRef, setRasterLayers, getColorTheme, sharedViewRef, mapRef]);

  /**
   * Re-colorize a layer from the cached decoded array. No network fetch needed.
   */
  const refreshLayer = useCallback((layerInfo) => {
    try {
      const cached = rasterDataRef.current.get(layerInfo.id);
      if (!cached) return;

      const arrayTypeId = layerInfo.arrayTypeId || 'rsrp';
      const colorBands = resolveColorBands(arrayTypeId, getColorTheme(arrayTypeId));

      const processedImageUrl = colorizeFromValues(
        cached.decodedValues,
        cached.width,
        cached.height,
        {
          targetResolution: layerInfo.selectedResolution,
          baseResolution: cached.baseResolution,
          colorBands,
          filterRange: layerInfo.filterRange,
          opacity: layerInfo.opacity,
        }
      );

      const sourceEpsg = layerInfo.sourceEpsg || 'EPSG:4326';
      const extent = boundsToExtent(layerInfo.metadata.bounds, sourceEpsg);

      layerInfo.layer.setSource(
        new ImageStatic({ url: processedImageUrl, imageExtent: extent })
      );
    } catch (err) {
      console.error('Failed to refresh layer:', err);
    }
  }, [getColorTheme, rasterDataRef]);

  const refreshAllLayers = useCallback(() => {
    rasterLayers.forEach((layer) => refreshLayer(layer));
  }, [rasterLayers, refreshLayer]);

  const toggleLayer = useCallback((id) => {
    setRasterLayers((prev) => {
      const target = prev.find((item) => item.id === id);
      if (!target) return prev;

      if (!target.visible) {
        const visibleCount = prev.filter((item) => item.visible).length;
        if (visibleCount >= MAX_VISIBLE_RASTER_LAYERS) return prev;
      }

      return prev.map((item) => {
        if (item.id === id) {
          item.layer.setVisible(!item.visible);
          return { ...item, visible: !item.visible };
        }
        return item;
      });
    });
  }, [setRasterLayers]);

  const updateLayerOpacity = useCallback((id, newOpacity) => {
    pendingRefreshRef.current.add(id);
    setRasterLayers((prev) =>
      prev.map((layer) => (layer.id === id ? { ...layer, opacity: newOpacity } : layer))
    );
  }, [setRasterLayers]);

  const updateLayerFilterRange = useCallback((id, key, value) => {
    pendingRefreshRef.current.add(id);
    setRasterLayers((prev) =>
      prev.map((layer) => {
        if (layer.id !== id) return layer;
        const newRange = { ...layer.filterRange, [key]: value };
        if (key === 'min' && value > layer.filterRange.max) newRange.max = value;
        if (key === 'max' && value < layer.filterRange.min) newRange.min = value;
        return { ...layer, filterRange: newRange };
      })
    );
  }, [setRasterLayers]);

  const updateLayerResolution = useCallback((id, value) => {
    pendingRefreshRef.current.add(id);
    setRasterLayers((prev) =>
      prev.map((layer) => (layer.id === id ? { ...layer, selectedResolution: value } : layer))
    );
  }, [setRasterLayers]);

  const flyToLayer = useCallback((layerInfo) => {
    if (!sharedViewRef.current) return;
    if (!layerInfo?.metadata?.bounds) return;

    const view = sharedViewRef.current;
    const sourceEpsg = layerInfo.sourceEpsg || 'EPSG:4326';
    const extent = boundsToExtent(layerInfo.metadata.bounds, sourceEpsg);

    const currentZoom = view.getZoom();
    const zoomOutLevel = Math.max(currentZoom - 3, 2);

    view.animate(
      { zoom: zoomOutLevel, duration: 1000 },
      () => {
        view.fit(extent, {
          padding: [50, 50, 50, 50],
          maxZoom: 14,
          duration: 2000,
        });
      }
    );
  }, [sharedViewRef]);

  const loadFromDataPath = useCallback(async () => {
    try {
      const response = await fetch(getDataFileUrl(dataPath, 'manifest.json'));
      if (!response.ok) {
        throw new Error(`Could not load manifest.json (${response.status})`);
      }
      const manifest = await response.json();

      if (manifest.files && Array.isArray(manifest.files)) {
        for (const baseName of manifest.files) {
          await addLayer(baseName);
        }
      }
      return true;
    } catch (err) {
      console.warn('No manifest found:', err.message);
      throw err;
    }
  }, [dataPath, addLayer]);

  // Auto-load on mount
  useEffect(() => {
    if (rasterLayers.length === 0 && !hasLoadedRef.current) {
      hasLoadedRef.current = true;
      loadFromDataPath().catch(console.error);
    }
  }, [dataPath, rasterLayers.length, loadFromDataPath]);

  // Debounced refresh for pending layers
  useEffect(() => {
    if (pendingRefreshRef.current.size === 0) return;
    if (rasterLayers.length === 0) return;

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      const idsToRefresh = new Set(pendingRefreshRef.current);
      pendingRefreshRef.current.clear();

      rasterLayers.forEach((layer) => {
        if (idsToRefresh.has(layer.id)) {
          refreshLayer(layer);
        }
      });
    }, 150);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };
  }, [rasterLayers, refreshLayer]);

  // Re-render layers when any per-type color theme changes
  useEffect(() => {
    if (rasterLayers.length === 0) return;
    refreshAllLayers();
  }, [colorThemes, rasterLayers.length, refreshAllLayers]);

  return {
    addLayer,
    refreshLayer,
    refreshAllLayers,
    toggleLayer,
    updateLayerOpacity,
    updateLayerFilterRange,
    updateLayerResolution,
    flyToLayer,
    loadFromDataPath,
  };
}

export default useLayerManager;

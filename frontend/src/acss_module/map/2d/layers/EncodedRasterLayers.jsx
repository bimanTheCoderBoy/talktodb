/**
 * EncodedRasterLayers
 *
 * Loads encoded raster layers produced by the backend encoder:
 *   - Fetch `manifest.json`
 *   - For each entry: fetch `${name}.json` + `${name}.png`
 *   - Decode RGB-encoded PNG into Float32Array raster values (once)
 *   - Generate a color-mapped PNG (data URL) from the decoded raster values
 *   - Render as OpenLayers ImageStatic overlays
 *
 * Color mapping uses the shared registry from coverage_map_viewer/2d/registry,
 * keyed by `metadata.type` (e.g. "rsrp", "dl_loss") so all technologies
 * (LTE, NR/5G) are supported without per-arrayType entries.
 *
 * This component renders nothing to the DOM.
 */

import { useEffect, useRef } from 'react';
import { toast } from 'react-toastify';
import ImageLayer from 'ol/layer/Image';
import ImageStatic from 'ol/source/ImageStatic';

import { useMap } from '../context/MapContext';
import { LAYER_Z_INDEX } from '../constants/layerOrder';
import { getArrayType, resolveColorBands } from '../../../../coverage_map_viewer/2d/registry';
import { ensureProjection, boundsToExtent, boundsToWGS84 } from '../utils/projection';

// ---- Helpers (adapted from coverage_map_viewer/2d) ----

function normalizeExtent(extent) {
  if (!extent || extent.length !== 4) return extent;
  const [x1, y1, x2, y2] = extent;
  const minX = Math.min(x1, x2);
  const maxX = Math.max(x1, x2);
  const minY = Math.min(y1, y2);
  const maxY = Math.max(y1, y2);
  return [minX, minY, maxX, maxY];
}

function normalizeBounds(bounds) {
  if (!bounds) return bounds;
  const west = Math.min(bounds.west, bounds.east);
  const east = Math.max(bounds.west, bounds.east);
  const south = Math.min(bounds.south, bounds.north);
  const north = Math.max(bounds.south, bounds.north);
  return { west, south, east, north };
}

function normalizeBasePathForServe(basePath) {
  if (!basePath) return basePath;
  // Convert Windows separators to URL-style forward slashes so nginx alias resolves correctly.
  const forward = String(basePath).replace(/\\/g, '/');
  // Remove trailing slash for consistent join behavior.
  return forward.endsWith('/') ? forward.slice(0, -1) : forward;
}

function getDataFileUrl(basePath, filename) {
  // Match frontend/src/coverage_map_viewer/2d/utils/dataPath.js behavior,
  // with extra normalization for Windows-style paths coming from backend.
  const normalizedBase = normalizeBasePathForServe(basePath);
  const fullPath = `${normalizedBase}/${filename}`;
  const encodedPath = encodeURIComponent(fullPath);
  return `/serve/${encodedPath}`;
}

function loadImageAsData(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();  
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      resolve({
        imageData: ctx.getImageData(0, 0, img.width, img.height),
        width: img.width,
        height: img.height,
      });
    };
    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}

const MAX_24BIT = 16777215;

/** Decode 24-bit RGB encoded image into Float32Array raster values. */
function decodeImageToRasterValues(imageData, valueMin, valueMax) {
  const count = imageData.width * imageData.height;
  const values = new Float32Array(count);
  const range = valueMax - valueMin;

  for (let i = 0; i < count; i++) {
    const idx = i * 4;
    const r = imageData.data[idx];
    const g = imageData.data[idx + 1];
    const b = imageData.data[idx + 2];
    const a = imageData.data[idx + 3];

    // transparent or black pixels are treated as no-data
    if (a === 0 || (r === 0 && g === 0 && b === 0)) {
      values[i] = NaN;
      continue;
    }

    const int24 = (r << 16) + (g << 8) + b;
    values[i] = (int24 / MAX_24BIT) * range + valueMin;
  }

  return values;
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 0, g: 0, b: 0 };
}

/** Create a color-mapped PNG data-URL from decoded raster values using registry color bands. */
function colorizeRasterValues(rasterValues, width, height, opacity, colorBands) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  const output = ctx.createImageData(width, height);

  const parsedBands = colorBands.map((b) => ({ min: b.min, ...hexToRgb(b.color) }));
  const alphaValue = Math.round(255 * opacity);

  for (let i = 0; i < rasterValues.length; i++) {
    const v = rasterValues[i];
    const outIdx = i * 4;

    if (Number.isNaN(v)) {
      output.data[outIdx + 3] = 0;
      continue;
    }

    let matched = parsedBands[parsedBands.length - 1];
    for (const band of parsedBands) {
      if (v >= band.min) { matched = band; break; }
    }

    output.data[outIdx] = matched.r;
    output.data[outIdx + 1] = matched.g;
    output.data[outIdx + 2] = matched.b;
    output.data[outIdx + 3] = alphaValue;
  }

  ctx.putImageData(output, 0, 0);
  return canvas.toDataURL('image/png');
}

function EncodedRasterLayers({
  dataPath,
  baselineVisible = true,
  baselineOpacity = 0.8,
  combinedVisible = true,
  combinedOpacity = 0.8,
  /**
   * onDecodedData(id, { rasterValues, width, height, bounds, layerName, group, registryTypeId })
   * Pass null to clear.
   */
  onDecodedData,
}) {
  const map = useMap();
  const layersRef = useRef([]);
  const loadedKeyRef = useRef(null);
  const lastStyleRef = useRef({ baselineOpacity: null, combinedOpacity: null, baselineVisible: null, combinedVisible: null });

  // Load layers (once per map + dataPath)
  useEffect(() => {
    if (!map || !dataPath) return;

    if (loadedKeyRef.current === dataPath) return;
    loadedKeyRef.current = dataPath;
    lastStyleRef.current = { baselineOpacity: null, combinedOpacity: null, baselineVisible: null, combinedVisible: null };

    let cancelled = false;

    (async () => {
      try {
        const manifestUrl = getDataFileUrl(dataPath, 'manifest.json');
        const manifestRes = await fetch(manifestUrl);
        if (!manifestRes.ok) {
          console.warn('[EncodedRasterLayers] Could not load manifest.json', manifestRes.status);
          return;
        }
        const manifest = await manifestRes.json();
        if (!manifest.files || !Array.isArray(manifest.files)) return;
        if (cancelled) return;

        for (const baseName of manifest.files) {
          if (cancelled) break;

          const group = baseName.startsWith('baseline') ? 'baseline' : 'combined';

          const metaUrl = getDataFileUrl(dataPath, `${baseName}.json`);
          const metaRes = await fetch(metaUrl);
          if (!metaRes.ok) {
            console.warn(`[EncodedRasterLayers] Skipping ${baseName}: metadata fetch failed`);
            continue;
          }
          const metadata = await metaRes.json();

          const registryTypeId = metadata.type || 'rsrp';
          const registryConfig = getArrayType(registryTypeId);
          if (!registryConfig) {
            toast.error(`Unsupported raster type "${registryTypeId}" in ${baseName}`);
            continue;
          }

          const sourceEpsg = metadata.epsg || 'EPSG:4326';
          await ensureProjection(sourceEpsg);
          const extent = normalizeExtent(boundsToExtent(metadata.bounds, sourceEpsg));
          const boundsWGS84 = normalizeBounds(boundsToWGS84(metadata.bounds, sourceEpsg));
          const valueMin = metadata.valueMin ?? metadata.rsrpMin ?? registryConfig.defaultMin;
          const valueMax = metadata.valueMax ?? metadata.rsrpMax ?? registryConfig.defaultMax;

          const pngUrl = getDataFileUrl(dataPath, `${baseName}.png`);
          const { imageData, width, height } = await loadImageAsData(pngUrl);
          if (cancelled) break;

          const rasterValues = decodeImageToRasterValues(imageData, valueMin, valueMax);

          const layerId = `acss-${group}-${baseName}`;
          if (onDecodedData) {
            onDecodedData(layerId, {
              rasterValues,
              width,
              height,
              bounds: boundsWGS84,
              extent,
              valueMin,
              valueMax,
              layerName: metadata.name || baseName,
              group,
              registryTypeId,
            });
          }

          const isBaseline = group === 'baseline';
          const opacity = isBaseline ? baselineOpacity : combinedOpacity;
          const visible = isBaseline ? baselineVisible : combinedVisible;
          const zIndex = isBaseline ? LAYER_Z_INDEX.BASELINE_RASTER : LAYER_Z_INDEX.COMBINED_RASTER;

          const colorBands = resolveColorBands(registryTypeId, 'classic');
          const url = colorizeRasterValues(rasterValues, width, height, opacity, colorBands);
          const source = new ImageStatic({ url, imageExtent: extent });
          const layer = new ImageLayer({ source, opacity: 1, zIndex, visible });

          map.addLayer(layer);
          layersRef.current.push({
            id: layerId,
            layer,
            group,
            baseName,
            extent,
            metadata,
            rasterValues,
            width,
            height,
            registryTypeId,
          });
        }

        if (layersRef.current.length > 0) {
          map.getView().fit(layersRef.current[0].extent, {
            padding: [50, 50, 50, 50],
            maxZoom: 15,
            duration: 800,
          });
        }
      } catch (err) {
        console.error('[EncodedRasterLayers] Load error:', err);
      }
    })();

    return () => {
      cancelled = true;
      if (map) {
        layersRef.current.forEach(({ layer, id }) => {
          map.removeLayer(layer);
          if (onDecodedData) onDecodedData(id, null);
        });
      }
      layersRef.current = [];
      loadedKeyRef.current = null;
    };
  }, [map, dataPath, onDecodedData]);

  // Apply visibility/opacity updates without reloading everything
  useEffect(() => {
    if (!map || layersRef.current.length === 0) return;

    const last = lastStyleRef.current;
    const didOpacityChange = last.baselineOpacity !== baselineOpacity || last.combinedOpacity !== combinedOpacity;
    const didVisibilityChange = last.baselineVisible !== baselineVisible || last.combinedVisible !== combinedVisible;

    if (!didOpacityChange && !didVisibilityChange) return;

    layersRef.current.forEach((entry) => {
      const isBaseline = entry.group === 'baseline';
      const visible = isBaseline ? baselineVisible : combinedVisible;
      entry.layer.setVisible(visible);

      if (didOpacityChange) {
        const opacity = isBaseline ? baselineOpacity : combinedOpacity;
        const colorBands = resolveColorBands(entry.registryTypeId, 'classic');
        const url = colorizeRasterValues(entry.rasterValues, entry.width, entry.height, opacity, colorBands);
        entry.layer.setSource(new ImageStatic({ url, imageExtent: entry.extent }));
      }
    });

    lastStyleRef.current = { baselineOpacity, combinedOpacity, baselineVisible, combinedVisible };
  }, [map, baselineOpacity, combinedOpacity, baselineVisible, combinedVisible]);

  return null;
}

export default EncodedRasterLayers;


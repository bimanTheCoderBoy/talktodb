import { boundsToWGS84 } from '../raster/projection';

/**
 * Load image and return as ImageData at original resolution.
 * @param {string} url
 * @returns {Promise<{imageData: ImageData, width: number, height: number}>}
 */
export function loadImageAsData(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;

      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);

      const imageData = ctx.getImageData(0, 0, img.width, img.height);
      resolve({ imageData, width: img.width, height: img.height });
    };

    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}

/**
 * Calculate the resolution (meters per pixel) from geographic bounds and image dimensions.
 */
export function calculateResolutionMetersPerPixel(bounds, width, height, sourceEpsg = 'EPSG:4326') {
  const wgs84 = boundsToWGS84(bounds, sourceEpsg);

  const latMid = (wgs84.north + wgs84.south) / 2;
  const metersPerDegreeLat = 111320;
  const metersPerDegreeLon = 111320 * Math.cos((latMid * Math.PI) / 180);

  const widthMeters = Math.abs(wgs84.east - wgs84.west) * metersPerDegreeLon;
  const heightMeters = Math.abs(wgs84.north - wgs84.south) * metersPerDegreeLat;

  return Math.min(widthMeters / width, heightMeters / height);
}

/**
 * Load image with optional downsampling based on target resolution.
 */
export function loadImageWithResolution(url, bounds, targetResolution = null, sourceEpsg = 'EPSG:4326') {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => {
      const originalWidth = img.width;
      const originalHeight = img.height;

      const baseResolution = calculateResolutionMetersPerPixel(bounds, originalWidth, originalHeight, sourceEpsg);

      let scaleFactor = 1;
      let outputWidth = originalWidth;
      let outputHeight = originalHeight;

      if (targetResolution !== null && targetResolution > baseResolution) {
        scaleFactor = targetResolution / baseResolution;
        outputWidth = Math.max(1, Math.ceil(originalWidth / scaleFactor));
        outputHeight = Math.max(1, Math.ceil(originalHeight / scaleFactor));
      }

      const canvas = document.createElement('canvas');
      canvas.width = outputWidth;
      canvas.height = outputHeight;

      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0, outputWidth, outputHeight);

      const imageData = ctx.getImageData(0, 0, outputWidth, outputHeight);

      resolve({
        imageData,
        width: outputWidth,
        height: outputHeight,
        originalWidth,
        originalHeight,
        scaleFactor,
        baseResolution,
      });
    };

    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}

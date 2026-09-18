import { getArrayType } from '../registry';

const MAX_24BIT = 16777215; // 2^24 - 1

const RasterArray = typeof Float16Array !== 'undefined' ? Float16Array : Float32Array;

/**
 * Decode 24-bit RGB-encoded image pixels into a Float16Array of real values.
 *
 * Works for any array type registered in the registry (RSRP, SINR, etc.).
 * The encoding is: int24 = (R << 16) + (G << 8) + B, mapped linearly to [min, max].
 *
 * @param {ImageData} imageData - Raw RGBA pixel data
 * @param {string}    arrayTypeId - Registry key (e.g. 'rsrp')
 * @param {number}   [overrideMin] - Per-layer min (from metadata), falls back to config default
 * @param {number}   [overrideMax] - Per-layer max (from metadata), falls back to config default
 * @returns {Float16Array|Float32Array} One value per pixel; NaN for no-data
 */
export function decodePixels(imageData, arrayTypeId = 'rsrp', overrideMin, overrideMax) {
  const config = getArrayType(arrayTypeId);
  const min = overrideMin ?? config.defaultMin;
  const max = overrideMax ?? config.defaultMax;
  const range = max - min;
  const pixelCount = imageData.width * imageData.height;
  const values = new RasterArray(pixelCount);

  for (let i = 0; i < pixelCount; i++) {
    const idx = i * 4;
    const r = imageData.data[idx];
    const g = imageData.data[idx + 1];
    const b = imageData.data[idx + 2];
    const a = imageData.data[idx + 3];

    if (a === 0 || (r === 0 && g === 0 && b === 0)) {
      values[i] = NaN;
    } else {
      const int24 = (r << 16) + (g << 8) + b;
      values[i] = (int24 / MAX_24BIT) * range + min;
    }
  }

  return values;
}

/**
 * Downsample a decoded value grid by area-averaging.
 */
export function downsampleValues(data, srcWidth, srcHeight, targetWidth, targetHeight) {
  const result = new RasterArray(targetWidth * targetHeight);
  const scaleX = srcWidth / targetWidth;
  const scaleY = srcHeight / targetHeight;

  for (let ty = 0; ty < targetHeight; ty++) {
    for (let tx = 0; tx < targetWidth; tx++) {
      const srcX0 = Math.floor(tx * scaleX);
      const srcY0 = Math.floor(ty * scaleY);
      const srcX1 = Math.min(Math.ceil((tx + 1) * scaleX), srcWidth);
      const srcY1 = Math.min(Math.ceil((ty + 1) * scaleY), srcHeight);

      let sum = 0;
      let count = 0;

      for (let sy = srcY0; sy < srcY1; sy++) {
        for (let sx = srcX0; sx < srcX1; sx++) {
          const value = data[sy * srcWidth + sx];
          if (!isNaN(value)) {
            sum += value;
            count++;
          }
        }
      }

      result[ty * targetWidth + tx] = count > 0 ? sum / count : NaN;
    }
  }

  return result;
}

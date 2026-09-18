import { resolveColorBands } from '../registry';
import { downsampleValues } from './decodeImage';

/**
 * Parse hex color to {r, g, b}.
 */
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 0, g: 0, b: 0 };
}

/**
 * Colorize a decoded value array into a data-URL PNG.
 *
 * @param {number}                      width      - Image width
 * @param {number}                      height     - Image height
 * @param {Float16Array|Float32Array}   values     - Decoded pixel values (one per pixel)
 * @param {Array}                       colorBands - Sorted high-to-low [{min, color}, ...]
 * @param {{min,max}}                   filterRange
 * @param {number}                      opacity    - 0..1
 * @returns {string} data-URL (image/png)
 */
export function colorizeToDataURL(width, height, values, colorBands, filterRange, opacity) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  const output = ctx.createImageData(width, height);

  const alphaValue = Math.round(255 * opacity);

  const parsedBands = colorBands.map((b) => ({ min: b.min, ...hexToRgb(b.color) }));

  for (let i = 0; i < values.length; i++) {
    const px = i * 4;
    const val = values[i];

    if (isNaN(val)) {
      output.data[px + 3] = 0;
      continue;
    }

    if (val < filterRange.min || val > filterRange.max) {
      output.data[px] = 135;
      output.data[px + 1] = 206;
      output.data[px + 2] = 235;
      output.data[px + 3] = 50;
      continue;
    }

    let matched = parsedBands[parsedBands.length - 1];
    for (const band of parsedBands) {
      if (val >= band.min) {
        matched = band;
        break;
      }
    }

    output.data[px] = matched.r;
    output.data[px + 1] = matched.g;
    output.data[px + 2] = matched.b;
    output.data[px + 3] = alphaValue;
  }

  ctx.putImageData(output, 0, 0);
  return canvas.toDataURL('image/png');
}

/**
 * Colorize from a pre-decoded value array, with optional resolution downsampling.
 *
 * Pure in-memory operation -- no network fetch, no PNG re-decode.
 *
 * @param {Float16Array|Float32Array} decodedValues - Full-resolution decoded values
 * @param {number}  fullWidth        - Original image width
 * @param {number}  fullHeight       - Original image height
 * @param {Object}  options
 * @param {number|null} options.targetResolution - Desired meters/pixel (null = full res)
 * @param {number}  options.baseResolution      - Native meters/pixel of the full image
 * @param {Array}   options.colorBands          - [{min, color, label}, ...]
 * @param {{min,max}} options.filterRange
 * @param {number}  options.opacity             - 0..1
 * @returns {string} data-URL (image/png)
 */
export function colorizeFromValues(decodedValues, fullWidth, fullHeight, options) {
  const { targetResolution, baseResolution, colorBands, filterRange, opacity } = options;

  let values = decodedValues;
  let width = fullWidth;
  let height = fullHeight;

  if (targetResolution != null && baseResolution && targetResolution > baseResolution) {
    const scaleFactor = targetResolution / baseResolution;
    width = Math.max(1, Math.ceil(fullWidth / scaleFactor));
    height = Math.max(1, Math.ceil(fullHeight / scaleFactor));
    values = downsampleValues(decodedValues, fullWidth, fullHeight, width, height);
  }

  return colorizeToDataURL(width, height, values, colorBands, filterRange, opacity);
}

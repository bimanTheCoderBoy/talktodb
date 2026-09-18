export const RESOLUTION_OPTIONS = [100, 200, 500, 800, 1000];

/**
 * Format resolution for display.
 * @param {number} resolution - meters per pixel
 * @returns {string} e.g. "123m" or "1.2km"
 */
export function formatResolution(resolution) {
  if (resolution >= 1000) {
    return `${(resolution / 1000).toFixed(1)}km`;
  }
  return `${Math.round(resolution)}m`;
}

/**
 * Get available resolution options that are >= the base resolution.
 */
export function getAvailableResolutions(baseResolution) {
  return RESOLUTION_OPTIONS.map((res) => ({
    value: res,
    label: `${res}m`,
    disabled: res < baseResolution,
  }));
}

/**
 * Calculate downsampled dimensions based on target resolution.
 */
export function calculateDownsampledDimensions(srcWidth, srcHeight, baseResolution, targetResolution) {
  if (targetResolution <= baseResolution) {
    return { width: srcWidth, height: srcHeight, scaleFactor: 1 };
  }

  const scaleFactor = targetResolution / baseResolution;
  const width = Math.max(1, Math.ceil(srcWidth / scaleFactor));
  const height = Math.max(1, Math.ceil(srcHeight / scaleFactor));

  return { width, height, scaleFactor };
}

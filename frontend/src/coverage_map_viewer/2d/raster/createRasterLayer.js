import ImageLayer from 'ol/layer/Image';
import ImageStatic from 'ol/source/ImageStatic';

/**
 * Create an OL ImageLayer from a data-URL and extent.
 *
 * @param {string} dataURL   - PNG data-URL produced by colorize
 * @param {Array}  extent    - [minX, minY, maxX, maxY] in EPSG:3857
 * @param {Object} [options]
 * @param {number} [options.zIndex=1]
 * @param {boolean}[options.visible=false]
 * @returns {ImageLayer}
 */
export function createRasterLayer(dataURL, extent, options = {}) {
  const source = new ImageStatic({
    url: dataURL,
    imageExtent: extent,
  });

  return new ImageLayer({
    source,
    opacity: 1,
    zIndex: options.zIndex ?? 1,
    visible: options.visible ?? false,
  });
}

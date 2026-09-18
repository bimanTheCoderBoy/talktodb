import rsrpConfig from './rsrp.config';
import dlLossConfig from './dl_loss.config';
import ssbIndexConfig from './ssb_index.config';
import beamIndexConfig from './beam_index.config';

const registry = new Map();

export function registerArrayType(config) {
  registry.set(config.id, config);
}

export function getArrayType(id) {
  return registry.get(id) ?? registry.get('rsrp');
}

export function getAllArrayTypes() {
  return [...registry.values()];
}

export function getThemes(arrayTypeId) {
  const config = getArrayType(arrayTypeId);
  return Object.entries(config.themes).map(([key, theme]) => ({
    id: key,
    name: theme.name || key,
  }));
}

export function resolveColorBands(arrayTypeId, themeId) {
  const config = getArrayType(arrayTypeId);
  return config.themes?.[themeId]?.colorBands ?? config.colorBands;
}

export function getColorForValue(value, arrayTypeId, themeId = 'classic') {
  const config = getArrayType(arrayTypeId);

  if (value == null || Number.isNaN(value)) {
    return config.noDataEntry || { label: 'No Data', color: '#6b7280' };
  }

  const bands = resolveColorBands(arrayTypeId, themeId);
  for (const band of bands) {
    if (value >= band.min) {
      return { label: band.label, color: band.color };
    }
  }

  const last = bands[bands.length - 1];
  return last || { label: 'Unknown', color: '#660000' };
}

export function getLayerColor(index) {
  const hues = [0, 210, 120, 45, 280, 180, 330, 60];
  const hue = hues[index % hues.length];
  return `hsl(${hue}, 70%, 50%)`;
}

registerArrayType(rsrpConfig);
registerArrayType(dlLossConfig);
registerArrayType(ssbIndexConfig);
registerArrayType(beamIndexConfig);

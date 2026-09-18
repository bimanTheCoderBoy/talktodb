export function buildLabelBandFromBaseName(baseName) {
  const parts = baseName.split('-');
  const last = parts[parts.length - 1].trim();
  if (last.toLowerCase() === 'all carriers') return 'All Carriers';
  return last;
}
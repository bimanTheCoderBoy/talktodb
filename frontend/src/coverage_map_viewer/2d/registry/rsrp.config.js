const rsrpConfig = {
  id: 'rsrp',
  label: 'RSRP/SS-RSRP',
  unit: 'dBm',
  defaultMin: -140,
  defaultMax: -40,
  encoding: '24bit-rgb',

  colorBands: [
    { min: -80,       label: 'Excellent', color: '#10b981' },
    { min: -90,       label: 'Good',      color: '#84cc16' },
    { min: -100,      label: 'Fair',      color: '#eab308' },
    { min: -110,      label: 'Poor',      color: '#f97316' },
    { min: -120,      label: 'Very Poor', color: '#ef4444' },
    { min: -Infinity, label: 'No Signal', color: '#991b1b' },
  ],

  noDataEntry: { label: 'No Data', color: '#6b7280' },

  themes: {
    classic: {
      name: 'Classic',
      colorBands: [
        { min: -80,       label: 'Excellent', color: '#10b981' },
        { min: -90,       label: 'Good',      color: '#84cc16' },
        { min: -100,      label: 'Fair',      color: '#eab308' },
        { min: -110,      label: 'Poor',      color: '#f97316' },
        { min: -120,      label: 'Very Poor', color: '#ef4444' },
        { min: -Infinity, label: 'No Signal', color: '#991b1b' },
      ],
    },
    blueScale: {
      name: 'Blue Scale',
      colorBands: [
        { min: -80,       label: 'Excellent', color: '#1e40af' },
        { min: -90,       label: 'Good',      color: '#2563eb' },
        { min: -100,      label: 'Fair',      color: '#60a5fa' },
        { min: -110,      label: 'Poor',      color: '#93c5fd' },
        { min: -Infinity, label: 'Very Poor', color: '#bfdbfe' },
      ],
    },
    heatmap: {
      name: 'Heatmap',
      colorBands: [
        { min: -80,       label: 'Excellent', color: '#22c55e' },
        { min: -90,       label: 'Good',      color: '#84cc16' },
        { min: -100,      label: 'Fair',      color: '#eab308' },
        { min: -110,      label: 'Poor',      color: '#a76630' },
        { min: -Infinity, label: 'Very Poor', color: '#dc2626' },
      ],
    },
    grayscale: {
      name: 'Grayscale',
      colorBands: [
        { min: -80,       label: 'Excellent', color: '#111827' },
        { min: -90,       label: 'Good',      color: '#374151' },
        { min: -100,      label: 'Fair',      color: '#6b7280' },
        { min: -110,      label: 'Poor',      color: '#9ca3af' },
        { min: -Infinity, label: 'Very Poor', color: '#d1d5db' },
      ],
    },
    highContrast: {
      name: 'High Contrast',
      colorBands: [
        { min: -80,       label: 'Excellent', color: '#00ff00' },
        { min: -90,       label: 'Good',      color: '#ffff00' },
        { min: -100,      label: 'Fair',      color: '#ff8800' },
        { min: -110,      label: 'Poor',      color: '#ff0000' },
        { min: -Infinity, label: 'Very Poor', color: '#800000' },
      ],
    },
  },
};

export default rsrpConfig;

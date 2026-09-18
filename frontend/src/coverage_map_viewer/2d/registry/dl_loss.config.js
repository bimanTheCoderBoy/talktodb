const dlLossConfig = {
    id: 'dl_loss',
    label: 'DL Loss',
    unit: 'dB',
    defaultMin: 50,
    defaultMax: 190,
    encoding: '24bit-rgb',
  
    // Lower DL loss = better coverage
    // Higher DL loss = worse coverage
  
    colorBands: [
      { min: 170,      label: 'Critical',  color: '#7f1d1d' },
      { min: 150,      label: 'Very Poor', color: '#dc2626' },
      { min: 130,      label: 'Poor',      color: '#f97316' },
      { min: 110,      label: 'Fair',      color: '#eab308' },
      { min: 90,       label: 'Good',      color: '#84cc16' },
      { min: -Infinity,label: 'Excellent', color: '#22c55e' },
    ],
  
    noDataEntry: {
      label: 'No Data',
      color: '#6b7280',
    },
  
    themes: {
      classic: {
        name: 'Classic',
        colorBands: [
          { min: 170,      label: 'Critical',  color: '#7f1d1d' },
          { min: 150,      label: 'Very Poor', color: '#dc2626' },
          { min: 130,      label: 'Poor',      color: '#f97316' },
          { min: 110,      label: 'Fair',      color: '#eab308' },
          { min: 90,       label: 'Good',      color: '#84cc16' },
          { min: -Infinity,label: 'Excellent', color: '#22c55e' },
        ],
      },
  
      blueScale: {
        name: 'Blue Scale',
        colorBands: [
          { min: 170,      label: 'Critical',  color: '#172554' },
          { min: 150,      label: 'Very Poor', color: '#1e3a8a' },
          { min: 130,      label: 'Poor',      color: '#1d4ed8' },
          { min: 110,      label: 'Fair',      color: '#3b82f6' },
          { min: 90,       label: 'Good',      color: '#93c5fd' },
          { min: -Infinity,label: 'Excellent', color: '#dbeafe' },
        ],
      },
  
      heatmap: {
        name: 'Heatmap',
        colorBands: [
          { min: 170,      label: 'Critical',  color: '#7f1d1d' },
          { min: 150,      label: 'Very Poor', color: '#dc2626' },
          { min: 130,      label: 'Poor',      color: '#ea580c' },
          { min: 110,      label: 'Fair',      color: '#facc15' },
          { min: 90,       label: 'Good',      color: '#84cc16' },
          { min: -Infinity,label: 'Excellent', color: '#16a34a' },
        ],
      },
  
      grayscale: {
        name: 'Grayscale',
        colorBands: [
          { min: 170,      label: 'Critical',  color: '#111827' },
          { min: 150,      label: 'Very Poor', color: '#374151' },
          { min: 130,      label: 'Poor',      color: '#4b5563' },
          { min: 110,      label: 'Fair',      color: '#6b7280' },
          { min: 90,       label: 'Good',      color: '#9ca3af' },
          { min: -Infinity,label: 'Excellent', color: '#d1d5db' },
        ],
      },
  
      highContrast: {
        name: 'High Contrast',
        colorBands: [
          { min: 170,      label: 'Critical',  color: '#800000' },
          { min: 150,      label: 'Very Poor', color: '#ff0000' },
          { min: 130,      label: 'Poor',      color: '#ff8800' },
          { min: 110,      label: 'Fair',      color: '#ffff00' },
          { min: 90,       label: 'Good',      color: '#88ff00' },
          { min: -Infinity,label: 'Excellent', color: '#00ff00' },
        ],
      },
    },
  };
  
  export default dlLossConfig;
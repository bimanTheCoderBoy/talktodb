const beamIndexConfig = {
  id: 'beam_index',
  label: 'Beam Index',
  unit: '',
  defaultMin: 0,
  defaultMax: 7,
  encoding: '24bit-rgb',

  colorBands: [
    { min: 5,         label: '5+',  color: '#9333ea' },
    { min: 4,         label: '4',   color: '#6366f1' },
    { min: 3,         label: '3',   color: '#3b82f6' },
    { min: 2,         label: '2',   color: '#0ea5e9' },
    { min: 1,         label: '1',   color: '#14b8a6' },
    { min: -Infinity, label: '0',   color: '#22c55e' },
  ],

  noDataEntry: { label: 'No Data', color: '#6b7280' },

  themes: {
    classic: {
      name: 'Classic',
      colorBands: [
        { min: 5,         label: '5+',  color: '#9333ea' },
        { min: 4,         label: '4',   color: '#6366f1' },
        { min: 3,         label: '3',   color: '#3b82f6' },
        { min: 2,         label: '2',   color: '#0ea5e9' },
        { min: 1,         label: '1',   color: '#14b8a6' },
        { min: -Infinity, label: '0',   color: '#22c55e' },
      ],
    },
    grayscale: {
      name: 'Grayscale',
      colorBands: [
        { min: 5,         label: '5+',  color: '#111827' },
        { min: 4,         label: '4',   color: '#374151' },
        { min: 3,         label: '3',   color: '#6b7280' },
        { min: 2,         label: '2',   color: '#9ca3af' },
        { min: 1,         label: '1',   color: '#d1d5db' },
        { min: -Infinity, label: '0',   color: '#e5e7eb' },
      ],
    },
  },
};

export default beamIndexConfig;

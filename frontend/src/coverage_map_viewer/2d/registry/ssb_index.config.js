const ssbIndexConfig = {
  id: 'ssb_index',
  label: 'SSB Index',
  unit: '',
  defaultMin: 0,
  defaultMax: 7,
  encoding: '24bit-rgb',

  colorBands: [
    { min: 5,         label: '5+',  color: '#7c3aed' },
    { min: 4,         label: '4',   color: '#3b82f6' },
    { min: 3,         label: '3',   color: '#06b6d4' },
    { min: 2,         label: '2',   color: '#10b981' },
    { min: 1,         label: '1',   color: '#84cc16' },
    { min: -Infinity, label: '0',   color: '#eab308' },
  ],

  noDataEntry: { label: 'No Data', color: '#6b7280' },

  themes: {
    classic: {
      name: 'Classic',
      colorBands: [
        { min: 5,         label: '5+',  color: '#7c3aed' },
        { min: 4,         label: '4',   color: '#3b82f6' },
        { min: 3,         label: '3',   color: '#06b6d4' },
        { min: 2,         label: '2',   color: '#10b981' },
        { min: 1,         label: '1',   color: '#84cc16' },
        { min: -Infinity, label: '0',   color: '#eab308' },
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

export default ssbIndexConfig;

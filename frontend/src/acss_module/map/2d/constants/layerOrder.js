/**
 * Z-index values for map layers
 * Higher values render on top of lower values
 */
export const LAYER_Z_INDEX = {
  OSM: 0,
  BASELINE_RASTER: 10,
  COMBINED_RASTER: 20,
  BOUNDARY: 99,
  POLYGON: 100,
  CELLS: 200,
  ALL_CANDIDATES: 220,
  CANDIDATE_CELLS: 250,
};

/**
 * Default settings for each layer
 * Used to initialize layer state in MapView
 */
export const DEFAULT_LAYER_SETTINGS = {
  osm: { 
    visible: true, 
    opacity: 1, 
    label: 'Base Map',
    color: '#64748b', // slate-500
  },
  baselineRaster: {
    visible: false,
    opacity: 0.8,
    label: 'Baseline Coverage',
    color: '#6366f1', // indigo-500
  },
  combinedRaster: {
    visible: true,
    opacity: 0.8,
    label: 'Combined Coverage',
    color: '#14b8a6', // teal-500
  },
  boundary: { 
    visible: true, 
    opacity: 0.5, 
    label: 'Boundary',
    color: '#3b82f6', // blue-500
  },
  polygon: { 
    visible: true, 
    opacity: 0.7, 
    label: 'Polygon',
    color: '#22c55e', // green-500
  },
  cells: { 
    visible: true, 
    opacity: 1, 
    label: 'Baseline Cells',
    color: '#ef4444', // red-500
  },
  allCandidates: { 
    visible: true, 
    opacity: 0.85, 
    label: 'GDL Candidates (Preview)',
    color: '#f59e0b', // amber-500
  },
  candidateCells: { 
    visible: true, 
    opacity: 1, 
    label: 'Selected Candidates',
    color: '#22c55e', // green-500
  },
};

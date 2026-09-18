import { createContext, useContext } from 'react';

const MapContext = createContext(null);

/**
 * Hook to access the shared OpenLayers Map instance.
 * Must be used inside a <MapShell> (which provides the context).
 */
export function useMap() {
  const map = useContext(MapContext);
  return map;
}

export default MapContext;

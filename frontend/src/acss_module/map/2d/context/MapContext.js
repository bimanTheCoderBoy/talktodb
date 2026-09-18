import { createContext, useContext } from 'react';

const MapContext = createContext(null);


export const useMap = () => {
  const context = useContext(MapContext);
  if (!context) {
    throw new Error('useMap must be used within MapProvider');
  }
  return context;
};

export const MapProvider = MapContext.Provider;

export default MapContext;

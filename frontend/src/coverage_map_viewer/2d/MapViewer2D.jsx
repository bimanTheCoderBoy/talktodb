import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MapProvider, useMapContext } from './context/MapContext';
import MapView from './components/MapView';
import ControlPanel from './components/ControlPanel';
import CoordinatesDisplay from './components/CoordinatesDisplay';
import CursorDisplay from './components/CursorDisplay';
import PolygonStatsPanel from './components/PolygonStatsPanel';
import CellInfoPanel from './cells/CellInfoPanel';
import 'ol/ol.css';
import { Home, Columns2, Combine } from 'lucide-react';

/**
 * MapViewer2D - Wrapper for the 2D Raster Map
 *
 * Extracts filepath from URL route and passes to MapProvider
 * Supports single and split (multi-map) view modes.
 *
 * Usage: Navigate to /map/2d/your/data/path
 */
function MapViewer2D() {
  const location = useLocation();
  const navigate = useNavigate();

  // Extract filepath from route (everything after /map/2d/)
  const dataPath = decodeURIComponent(location.pathname.replace('/map/2d/', ''));

  // Handle Escape key to navigate back to home
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        navigate('/');
      }
    };

    window.addEventListener('keydown', handleEscape);

    return () => {
      window.removeEventListener('keydown', handleEscape);
    };
  }, [navigate]);

  const handleClose = () => {
    navigate('/');
  };

  return (
    <MapProvider initialDataPath={dataPath}>
      <div className="map-2d-wrapper">
        <div className="app-container" style={{ width: '100%', height: '100vh', position: 'relative' }}>
          {/* Top-right buttons */}
          <div className="absolute top-4 right-4 flex gap-2 z-1000">
            <SplitButton />
            <button
              onClick={handleClose}
              className="close-button bg-primary hover:bg-primary/80 transition-colors w-10 h-10 rounded-md flex items-center justify-center text-primary-foreground text-2xl cursor-pointer p-0"
              aria-label="Close map viewer"
              title="Close map viewer"
            >
              <Home className="w-6 h-6 text-primary-foreground hover:text-primary-foreground/80 transition-colors" />
            </button>
          </div>

          {/* Map area */}
          <MapArea />

          <ControlPanel />
          <CoordinatesDisplay />
          <CursorDisplay />
          <PolygonStatsPanel />
          <CellInfoPanel />
        </div>
      </div>
    </MapProvider>
  );
}

/**
 * SplitButton - toggles between single and split view modes
 * Enabled only when 2-4 raster layers are visible.
 */
function SplitButton() {
  const { viewMode, setViewMode, rasterLayers } = useMapContext();
  const visibleCount = rasterLayers.filter(l => l.visible).length;
  const canSplit = visibleCount >= 2 && visibleCount <= 4;
  const isSplit = viewMode === 'split';

  const handleToggle = () => {
    setViewMode(isSplit ? 'single' : 'split');
  };

  return (
    <button
      onClick={handleToggle}
      disabled={!isSplit && !canSplit}
      className={`transition-colors w-10 h-10 rounded-md flex items-center justify-center text-primary-foreground cursor-pointer p-0 ${
        isSplit
          ? 'bg-amber-600 hover:bg-amber-500'
          : canSplit
            ? 'bg-primary hover:bg-primary/80'
            : 'bg-gray-600 opacity-50 cursor-not-allowed'
      }`}
      aria-label={isSplit ? 'Merge views' : 'Split views'}
      title={
        isSplit
          ? 'Merge back to single view'
          : canSplit
            ? `Split into ${visibleCount} map panes`
            : visibleCount < 2
              ? 'Enable 2+ layers to split'
              : 'Max 4 layers for split view'
      }
    >
      {isSplit ? (
        <Combine className="w-5 h-5 text-primary-foreground" />
      ) : (
        <Columns2 className="w-5 h-5 text-primary-foreground" />
      )}
    </button>
  );
}

/**
 * MapArea - renders single or split map layout based on viewMode
 * Auto-falls back to single mode if visible layers drop below 2.
 */
function MapArea() {
  const { viewMode, setViewMode, rasterLayers } = useMapContext();
  const visibleLayers = rasterLayers.filter(l => l.visible);

  // Auto-fallback: if in split mode but fewer than 2 visible layers, revert
  useEffect(() => {
    if (viewMode === 'split' && visibleLayers.length < 2) {
      setViewMode('single');
    }
  }, [viewMode, visibleLayers.length, setViewMode]);

  if (viewMode === 'split' && visibleLayers.length >= 2) {
    const count = visibleLayers.length;
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gridTemplateRows: count <= 2 ? '1fr' : 'repeat(2, 1fr)',
          width: '100%',
          height: '100vh',
          gap: '2px',
          background: 'var(--background)',
        }}
      >
        {visibleLayers.map(layer => (
          <div key={layer.id} style={{ overflow: 'hidden', position: 'relative' }}>
            <MapView
              mapId={layer.id}
              assignedLayerIds={[layer.id]}
              title={layer.name}
            />
          </div>
        ))}
      </div>
    );
  }

  // Single mode (default)
  return <MapView mapId="single" assignedLayerIds={null} />;
}

export default MapViewer2D;

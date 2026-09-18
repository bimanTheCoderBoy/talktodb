import { useMapContext } from '../context/MapContext';

function CoordinatesDisplay() {
  const { coordinates } = useMapContext();

  return (
    <div className="coords-display">
      <span style={{ color: 'var(--text-secondary)' }}>Lat:</span>{' '}
      <span style={{ color: 'var(--text-primary)' }}>{coordinates.lat}</span>
      <span style={{ margin: '0 8px', color: 'var(--map-accent)' }}>|</span>
      <span style={{ color: 'var(--text-secondary)' }}>Lon:</span>{' '}
      <span style={{ color: 'var(--text-primary)' }}>{coordinates.lon}</span>
    </div>
  );
}

export default CoordinatesDisplay;


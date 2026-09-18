import { X, Radio, MapPin, Compass, Hash, Layers } from 'lucide-react';
import { getBandColor } from './utils/cellSectors';

function FeaturePopup({ info, onClose }) {
  if (!info) return null;

  return (
    <div className="absolute top-4 right-4 z-[1000] bg-card border border-border rounded-lg shadow-xl w-[300px]">
      {/* Popup Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-secondary/50 rounded-t-lg">
        <div className="flex items-center gap-2">
          {info.type === 'cell' ? (
            <Radio className="w-4 h-4 text-teoco-real-blue" />
          ) : (
            <MapPin className="w-4 h-4 text-red-500" />
          )}
          <span className="text-sm font-semibold text-foreground">
            {info.type === 'cell' ? 'Cell Info' : 'Site Info'}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-accent rounded transition-colors"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      {/* Popup Content */}
      <div className="p-3 space-y-3">
        {/* Site Info (always shown) */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wider">
            <MapPin className="w-3 h-3" />
            Site
          </div>
          <div className="bg-secondary/50 rounded-md p-2 space-y-1">
            <div className="flex justify-between">
              <span className="text-xs text-muted-foreground">Site ID:</span>
              <span className="text-xs text-foreground font-mono">{info.site?.site_iid || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-muted-foreground">Latitude:</span>
              <span className="text-xs text-foreground font-mono">{info.site?.latitude?.toFixed?.(6) ?? 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-muted-foreground">Longitude:</span>
              <span className="text-xs text-foreground font-mono">{info.site?.longitude?.toFixed?.(6) ?? 'N/A'}</span>
            </div>
            {info.site?.technology && (
              <div className="flex justify-between">
                <span className="text-xs text-muted-foreground">Technology:</span>
                <span className="text-xs text-foreground">
                  {Array.isArray(info.site.technology)
                    ? info.site.technology.join(', ')
                    : info.site.technology}
                </span>
              </div>
            )}
            {info.type === 'site' && info.site?.cells && (
              <div className="flex justify-between">
                <span className="text-xs text-muted-foreground">Total Cells:</span>
                <span className="text-xs text-foreground">{info.site.cells.length}</span>
              </div>
            )}
          </div>
        </div>

        {/* Cell Info (only for cell clicks) */}
        {info.type === 'cell' && info.cell && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wider">
              <Radio className="w-3 h-3" />
              Cell
            </div>
            <div className="bg-secondary/50 rounded-md p-2 space-y-1">
              <div className="flex justify-between">
                <span className="text-xs text-muted-foreground">Cell ID:</span>
                <span className="text-xs text-foreground font-mono">{info.cell.cell_iid || 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Compass className="w-3 h-3" /> Azimuth:
                </span>
                <span className="text-xs text-foreground">{info.cell.azimuth ?? 'N/A'}°</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Layers className="w-3 h-3" /> Band:
                </span>
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-sm border border-border"
                    style={{ backgroundColor: getBandColor(info.cell.band) }}
                  />
                  <span className="text-xs text-foreground">{info.cell.band || 'N/A'}</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Hash className="w-3 h-3" /> PCI:
                </span>
                <span className="text-xs text-foreground">{info.cell.pci ?? 'N/A'}</span>
              </div>
              {info.cell.technology && (
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Technology:</span>
                  <span className="text-xs text-foreground">{info.cell.technology}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default FeaturePopup;


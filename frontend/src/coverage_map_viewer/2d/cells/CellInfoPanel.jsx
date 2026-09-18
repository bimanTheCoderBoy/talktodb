import React, { useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useMapContext } from '../context/MapContext';
import { getBandColor } from './cellGeometry';

function getSiteTechnologies(site) {
  const siteTechnologies = Array.isArray(site?.technology)
    ? site.technology
    : [site?.technology];
  const cellTechnologies = site?.cells?.map((cell) => cell.technology) || [];

  const technologies = [...new Set(
    [...siteTechnologies, ...cellTechnologies]
      .filter(Boolean)
      .map((technology) => String(technology).trim())
      .filter(Boolean)
  )];

  return technologies.join(', ') || 'N/A';
}

/**
 * CellInfoPanel Component
 *
 * Floating panel (portal) showing info for the clicked cell or site.
 */
function CellInfoPanel() {
  const { selectedCellInfo, setSelectedCellInfo } = useMapContext();

  const closeInfoPanel = useCallback(() => {
    setSelectedCellInfo(null);
  }, [setSelectedCellInfo]);

  if (!selectedCellInfo) return null;

  return createPortal(
    <div
      className="fixed top-5 right-5 bg-card rounded-xl shadow-2xl w-72 text-sm text-foreground z-[3000] border border-border animate-in slide-in-from-right-5 duration-200"
      style={{ padding: '20px', boxSizing: 'border-box' }}
    >
      <button
        className="absolute top-2 right-2 bg-transparent border-none text-xl text-muted-foreground cursor-pointer leading-none w-8 h-8 flex items-center justify-center hover:text-foreground transition-colors"
        onClick={closeInfoPanel}
        aria-label="Close"
        style={{ padding: '0' }}
      >
        &times;
      </button>

      {selectedCellInfo.type === 'cell' ? (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h3
            className="text-[13px] font-semibold text-foreground m-0 pr-6 wrap-break-word border-b border-border"
            style={{ paddingBottom: '12px', marginBottom: '12px' }}
          >
            {selectedCellInfo.cell.cell_iid}
          </h3>

          {[
            { label: 'Band', value: `${selectedCellInfo.cell.band} MHz`, color: getBandColor(selectedCellInfo.cell.band) },
            { label: 'Tech', value: selectedCellInfo.cell.technology },
            { label: 'Azimuth', value: `${selectedCellInfo.cell.azimuth}\u00B0` },
            { label: 'PCI', value: selectedCellInfo.cell.pci },
          ].map((row, idx) => (
            <div
              key={idx}
              className="flex justify-between items-center border-b border-border/30"
              style={{ padding: '8px 0', margin: '0' }}
            >
              <span className="text-muted-foreground font-medium text-xs">{row.label}:</span>
              <span
                className="font-semibold font-mono text-xs"
                style={{ color: row.color || undefined }}
              >
                {row.value}
              </span>
            </div>
          ))}

          <div
            className="block border-t border-border text-blue-500 text-[11px] font-medium text-center"
            style={{ marginTop: '12px', paddingTop: '12px' }}
          >
            Layer {selectedCellInfo.layerIndex}/{selectedCellInfo.layerTotal} at this azimuth
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h3
            className="text-[13px] font-semibold text-foreground m-0 pr-6 wrap-break-word border-b border-border"
            style={{ paddingBottom: '12px', marginBottom: '12px' }}
          >
            {selectedCellInfo.site.site_iid}
          </h3>

          {[
            { label: 'Location', value: `${selectedCellInfo.site.latitude.toFixed(5)}, ${selectedCellInfo.site.longitude.toFixed(5)}` },
            { label: 'Technologies', value: getSiteTechnologies(selectedCellInfo.site) },
            { label: 'Total Cells', value: selectedCellInfo.site.cells?.length || 0 },
          ].map((row, idx) => (
            <div
              key={idx}
              className="flex justify-between items-center border-b border-border/30"
              style={{ padding: '8px 0', margin: '0' }}
            >
              <span className="text-muted-foreground font-medium text-xs">{row.label}:</span>
              <span className="text-foreground font-semibold font-mono text-xs">
                {row.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>,
    document.body
  );
}

export default CellInfoPanel;

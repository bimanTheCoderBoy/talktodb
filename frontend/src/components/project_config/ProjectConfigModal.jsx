import React, { useEffect, useState, useCallback, useRef } from 'react';
import { X, Save, Trash2, Loader2, PenTool, MapPin, Upload, RefreshCw, Eraser, Mail, Search, HomeIcon } from 'lucide-react';

import { MapShell, FitToCords, DrawPolygon, PolygonLayer, CellsLayer, FeaturePopup, MapFeatureSelect } from '../map_primitives_ol';
import SitesCellsSidebar from './SitesCellsSidebar';
import { useProjectConfigState } from './projectConfigState';
import { useProjectContext } from '@/context/ProjectContext';
import { parseSingleColumnCsv } from './parseSingleColumnCsv';
import { getPolygonAreaKm2 , MAX_POLYGON_AREA} from './projectConfigState';

/**
 * Project configuration view.
 *
 * Props:
 *  - isOpen      : boolean
 *  - onClose     : () => void
 *  - projectName : string (initial project name to load)
 *  - readOnly    : boolean (if true, all editing is disabled — TopBar view)
 */
function ProjectConfigModal({ isOpen, onClose, projectName, readOnly = false }) {
  const { refreshProjectConfigured } = useProjectContext();
  const {
    allSites, projectCords, polygonCoords,
    loading, saving, syncing, error,
    configEmail, setConfigEmail,
    selectedForMap, selectedCellIids,
    init, applyPolygon, clearPolygon,
    syncPolygonSelection, clearSelections,
    toggleCell, toggleSite, replaceSelectionFromCsv, save, setError
  } = useProjectConfigState();

  const [drawEnabled, setDrawEnabled] = useState(false);
  const [drawResetKey, setDrawResetKey] = useState(0);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [selectedFeatureInfo, setSelectedFeatureInfo] = useState(null);
  const [localProjectName, setLocalProjectName] = useState(projectName || '');
  const [localEmail, setLocalEmail] = useState('');
  const [configLoaded, setConfigLoaded] = useState(false);
  const [csvNotice, setCsvNotice] = useState(null);
  const csvInputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setLocalProjectName(projectName || '');
      setLocalEmail('');
      setConfigLoaded(false);
    }
  }, [isOpen, projectName]);

  useEffect(() => {
    if (isOpen && projectName && readOnly) {
      init(projectName);
      setDrawEnabled(false);
      setSaveSuccess(false);
      setSelectedFeatureInfo(null);
    }
  }, [isOpen, projectName, readOnly, init]);

  const handleLoadConfig = useCallback(async () => {
    const trimmedName = localProjectName.trim();
    const trimmedEmail = localEmail.trim();
    if (!trimmedName || !trimmedEmail) return;
    setDrawEnabled(false);
    setSaveSuccess(false);
    setSelectedFeatureInfo(null);
    setConfigLoaded(false);
    await init(trimmedName, trimmedEmail);
    setConfigLoaded(true);
  }, [localProjectName, localEmail, init]);

  const handleClear = useCallback(() => {
    clearPolygon();
    setDrawEnabled(false);
    setDrawResetKey(k => k + 1);
  }, [clearPolygon]);

  const handlePolygonChange = useCallback((ring) => {
    const area = getPolygonAreaKm2(ring);
    if (area > MAX_POLYGON_AREA) {
      setDrawEnabled(false);
      setDrawResetKey(k => k + 1);
      setError(`Polygon area is too large (${Math.round(area)} km²) — maximum is ${MAX_POLYGON_AREA} km².`);
      return;
    }

    setDrawEnabled(false);
    applyPolygon(ring);
    setError(null);
  }, [applyPolygon, setError]);

  const handleClearCells = useCallback(() => {
    clearSelections();
  }, [clearSelections]);

  const handleSyncPolygon = useCallback(async () => {
    const result = await syncPolygonSelection();
    if (result?.applied) {
      setCsvNotice({ type: 'success', text: `Synced ${result.matched} cells from polygon.` });
      setTimeout(() => setCsvNotice(null), 4000);
    }
  }, [syncPolygonSelection]);

  const handleSave = useCallback(async () => {
    try {
      if (!polygonCoords || selectedCellIids.length === 0) {
        setError('Please draw a polygon and select cells before saving. No data to save.');
        return;
      }
      
    
      await save(readOnly ? undefined : localEmail.trim() || undefined);
      setSaveSuccess(true);
      // refreshProjectConfigured();
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch {
      // error is already set in state
    }
  }, [save, readOnly, localEmail, refreshProjectConfigured]);

  const handleCsvImport = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    const reader = new FileReader();
    reader.onload = (evt) => {
      const ids = parseSingleColumnCsv(evt.target.result);
      if (ids.length === 0) {
        setCsvNotice({ type: 'error', text: 'CSV is empty or has no data rows.' });
        setTimeout(() => setCsvNotice(null), 4000);
        return;
      }

      const result = replaceSelectionFromCsv(ids);
      if (!result.applied) {
        setCsvNotice(null);
        return;
      }

      const msg = result.ignored > 0
        ? `Selected ${result.matched} cells (${result.ignored} unknown IDs ignored).`
        : `Selected ${result.matched} cells from CSV.`;
      setCsvNotice({ type: 'success', text: msg });
      setTimeout(() => setCsvNotice(null), 4000);
    };
    reader.onerror = () => {
      setCsvNotice({ type: 'error', text: 'Failed to read the CSV file.' });
      setTimeout(() => setCsvNotice(null), 4000);
    };
    reader.readAsText(file);
  }, [replaceSelectionFromCsv]);

  if (!isOpen) return null;

  const wrapperClass = readOnly
    ? "fixed inset-0 z-[6000000] flex items-center justify-center backdrop-blur-[2px] bg-black/40"
    : "fixed inset-0 z-[6000000] flex flex-col bg-background";

  const containerClass = readOnly
    ? "bg-card border border-border rounded-xl shadow-2xl shadow-black/50 w-[95%] h-[85vh] max-w-7xl flex flex-col overflow-hidden"
    : "w-full h-full flex flex-col overflow-hidden";

  return (
    <div className={wrapperClass}>
      <div className={containerClass}>

        {/* ====== Header ====== */}
        <div className="flex items-center justify-between p-4 border-b border-border bg-secondary/50">
          <div className="flex items-center gap-3">
            <MapPin className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">
              Project Config
              {readOnly && <span className="ml-2 text-xs font-normal text-muted-foreground">(View Only)</span>}
            </h2>

            {readOnly ? (
              <>
                <span className="px-2.5 py-1 text-xs font-medium bg-secondary text-foreground rounded-lg border border-border w-48 inline-block truncate">
                  {projectName || 'No Project'}
                </span>
                <div className="flex items-center gap-1.5 ml-2 border-l border-border pl-3">
                  <Mail className="w-4 h-4 text-primary" />
                  <span className="text-xs text-muted-foreground truncate">{configEmail || 'No email'}</span>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={localProjectName}
                    onChange={(e) => setLocalProjectName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleLoadConfig(); }}
                    className="px-2.5 py-1 text-xs font-medium bg-secondary text-foreground rounded-lg border border-border focus:outline-none focus:border-primary w-48"
                    placeholder="Project name..."
                  />
                </div>
                <div className="flex items-center gap-1.5 ml-2 border-l border-border pl-3">
                  <Mail className="w-4 h-4 text-primary" />
                  <input
                    type="email"
                    value={localEmail}
                    onChange={(e) => setLocalEmail(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleLoadConfig(); }}
                    className="px-2.5 py-1 text-xs font-medium bg-secondary text-foreground rounded-lg border border-border focus:outline-none focus:border-primary w-56"
                    placeholder="User email..."
                  />
                </div>
                <button
                  onClick={handleLoadConfig}
                  disabled={!localProjectName.trim() || !localEmail.trim() || loading}
                  className="flex items-center gap-1.5 ml-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Load config for this project and user"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Load Config
                </button>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!readOnly && configLoaded && (
              <>
                {/* Import CSV */}
                <input
                  ref={csvInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={handleCsvImport}
                />
                <button
                  onClick={() => csvInputRef.current?.click()}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Import cell IIDs from a CSV file"
                >
                  <Upload className="w-4 h-4" />
                  Import CSV
                </button>

                {/* Draw polygon */}
                {!polygonCoords &&
                (<button
                  onClick={() => setDrawEnabled(v => !v)}
                  disabled={loading || !!polygonCoords}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed ${
                    drawEnabled ? 'ring-2 ring-primary-foreground/40' : ''
                  }`}
                  title={polygonCoords ? 'Clear polygon first to draw a new one' : 'Draw selection polygon'}
                >
                  <PenTool className="w-4 h-4" />
                  Draw Polygon
                </button>
                )
                }

                {/* Sync polygon -> selection */}
                {polygonCoords && (
                  <button
                    onClick={handleSyncPolygon}
                    disabled={loading || syncing}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title="Select cells inside the polygon"
                  >
                    {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    {syncing ? 'Syncing...' : 'Sync'}
                  </button>
                )}

                {/* Clear polygon only */}
                {polygonCoords && (
                  <button
                    onClick={handleClear}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                    title="Clear polygon boundary only"
                  >
                    <Trash2 className="w-4 h-4" />
                    Clear Polygon
                  </button>
                )}

                {/* Clear selected cells only */}
                <button
                  onClick={handleClearCells}
                  disabled={loading || selectedCellIids.length === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Clear selected cells only"
                >
                  <Eraser className="w-4 h-4" />
                  Clear Cells
                </button>

                {/* Save */}
                <button
                  onClick={handleSave}
                  disabled={saving || loading}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saveSuccess ? 'Saved!' : 'Save'}
                </button>
              </>
            )}

            {/* Close */}
            {readOnly && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground cursor-pointer"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
            )}
            {!readOnly && (
              <button
                onClick={() => {
                  window.location.href = '/';
                }}
                className="p-2 rounded-lg transition-colors hover:scale-105 cursor-pointer bg-secondary text-muted-foreground hover:text-primary-foreground hover:bg-primary"
                title="Go to home"
              >
                <HomeIcon className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* ====== Body ====== */}
        <div className="flex-1 flex overflow-hidden relative">
          {/* Loading overlay */}
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70">
              <div className="flex items-center gap-3 px-6 py-3 bg-card rounded-lg border border-border">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
                <span className="text-sm text-muted-foreground">Loading project data...</span>
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-red-600/90 text-white text-sm rounded-lg shadow-lg">
              {error}
            </div>
          )}

          {/* CSV import notice */}
          {csvNotice && (
            <div className={`absolute top-2 left-1/2 -translate-x-1/2 z-20 px-4 py-2 text-white text-sm rounded-lg shadow-lg ${
              csvNotice.type === 'success' ? 'bg-green-600/90' : 'bg-red-600/90'
            }`}>
              {csvNotice.text}
            </div>
          )}

          {/* No config loaded hint (admin mode) */}
          {!readOnly && !configLoaded && !loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70">
              <div className="text-center px-6 py-4 bg-card rounded-lg border border-border">
                <MapPin className="w-8 h-8 text-primary mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Enter a project name and user email above, then click <strong>Load Config</strong>.</p>
              </div>
            </div>
          )}

          {/* Missing project polygon hint */}
          {configLoaded && !loading && !projectCords && !error && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70">
              <div className="text-center px-6 py-4 bg-card rounded-lg border border-border">
                <p className="text-sm text-muted-foreground">put right KML file in the server.</p>
              </div>
            </div>
          )}

          {/* Sidebar */}
          <SitesCellsSidebar
            allSites={allSites}
            onToggleCell={readOnly ? () => {} : toggleCell}
            onToggleSite={readOnly ? () => {} : toggleSite}
            disabled={loading || readOnly}
          />

          {/* Map */}
          
          <div className="flex-1 relative">
            <MapShell className="w-full h-full">
              <FitToCords cords={projectCords} />
              <MapFeatureSelect onSelect={setSelectedFeatureInfo} />

              {!readOnly && (
                <DrawPolygon
                  key={drawResetKey}
                  enabled={drawEnabled}
                  initialPolygon={polygonCoords}
                  onChange={handlePolygonChange}
                />
              )}

              {polygonCoords && (readOnly || !drawEnabled) && (
                <PolygonLayer polygonCoords={polygonCoords} />
              )}

              <CellsLayer data={selectedForMap} />
            </MapShell>

            <FeaturePopup info={selectedFeatureInfo} onClose={() => setSelectedFeatureInfo(null)} />

            {drawEnabled && !readOnly && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10
                bg-primary/90 text-primary-foreground px-4 py-2 rounded-lg text-sm
                shadow-lg backdrop-blur-sm pointer-events-none">
                Click to add vertices &bull; Double-click to finish
              </div>
            )}

            <div className="absolute bottom-3 right-3 z-10 bg-card/90 backdrop-blur-sm px-3 py-2 rounded-lg border border-border text-xs text-muted-foreground">
              {selectedCellIids.length} cells selected across {selectedForMap.length} sites
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProjectConfigModal;

import React, { useState, useCallback, useEffect, useMemo, useRef } from "react";
import SiteMap from "./SiteMap";
import SitesCellsSidebar from "../project_config/SitesCellsSidebar";
import { FeaturePopup } from "../map_primitives_ol";
import {
  X, MapPin, RefreshCw, Settings, List, PanelLeftClose,
  Crosshair, PenTool, Trash2, Loader2, RefreshCcw,
} from "lucide-react";
import ArrayTypeMultiSelect from "./parameter/ArrayTypeMultiSelect";
import ParameterSettingsModal from "./parameter/ParameterSettingsModal";
import { useProjectContext } from "@/context/ProjectContext";
import { getUserProjectConfig } from "../../api";
import { ensureClosedRing } from "../project_config/projectConfigTransform";

const URL_PARAMS_STORAGE_KEY = "coverage_url_parameter_settings";
const OUTPUT_CONFIG_STORAGE_KEY = "coverage_output_config";

const loadFromStorage = (key) => {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : null;
  } catch { return null; }
};

const saveToStorage = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) { console.error(`Error saving ${key}:`, e); }
};

/**
 * Prefer localStorage per-tech values over backend defaults.
 * Backend provides the tech key structure; stored values override field-by-field.
 */
function mergeStoredOverBackend(stored, backend) {
  if (!stored || Object.keys(stored).length === 0) return backend;
  const merged = { ...backend };
  for (const tech of Object.keys(merged)) {
    if (stored[tech]) merged[tech] = { ...merged[tech], ...stored[tech] };
  }
  for (const tech of Object.keys(stored)) {
    if (!merged[tech]) merged[tech] = stored[tech];
  }
  return merged;
}

/**
 * Output path is always the backend timestamp for this run.
 * Only a previously saved output name is restored from localStorage.
 */
function mergeStoredOutputOverBackend(stored, backend) {
  if (!stored || Object.keys(stored).length === 0) return backend;
  const merged = {};
  for (const tech of Object.keys(backend || {})) {
    merged[tech] = { ...backend[tech] };
    if (stored[tech]?.name) merged[tech].name = stored[tech].name;
  }
  return merged;
}

function namesOnlyOutputConfig(output) {
  const namesOnly = {};
  for (const tech of Object.keys(output || {})) {
    if (output[tech]?.name != null) namesOnly[tech] = { name: output[tech].name };
  }
  return namesOnly;
}

/**
 * Merge per-tech parameters into a single flat arrayTypes list for UI display.
 * Each item gets a `_tech` tag so we can split them back.
 */
function mergeArrayTypes(parameters) {
  const merged = [];
  for (const tech of ["lte", "nr"]) {
    const techParams = parameters?.[tech];
    if (!techParams?.arrayTypes) continue;
    for (const at of techParams.arrayTypes) {
      merged.push({ ...at, _tech: tech });
    }
  }
  return merged;
}

/**
 * Given a flat merged array (with `_tech` tags), reconstruct per-tech parameters.
 */
function splitArrayTypesBack(mergedList, originalParameters) {
  const result = {};
  for (const tech of ["lte", "nr"]) {
    if (!originalParameters?.[tech]) continue;
    result[tech] = {
      ...originalParameters[tech],
      arrayTypes: mergedList.filter(at => at._tech === tech).map(({ _tech, ...rest }) => rest),
    };
  }
  return result;
}

// ─── Helpers ────────────────────────────────────────────────────────

function pointInPolygon(x, y, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function isPolygonWithinBoundary(innerRing, outerRing) {
  if (!innerRing || !outerRing || outerRing.length < 3) return true;
  for (const pt of innerRing) {
    if (!pointInPolygon(pt[0], pt[1], outerRing)) return false;
  }
  return true;
}

function applySitesFromPolygon(sitesArr, ring) {
  return sitesArr.map(s => {
    const inside = pointInPolygon(s.longitude, s.latitude, ring);
    return { ...s, cells: s.cells.map(c => ({ ...c, selected: inside })) };
  });
}

// ─── Main component ─────────────────────────────────────────────────

export default function TelecomMapContainer({ data = {}, onClose, onConfirm }) {
  const { projectName } = useProjectContext();

  // ── Loading ──
  const [loading, setLoading] = useState(true);

  // ── Core data ──
  const [sites, setSites] = useState([]);
  const [parameters, setParameters] = useState({});
  const [outputConfig, setOutputConfig] = useState({});
  const [urlParameterSettings, setUrlParameterSettings] = useState({});

  // ── Project config polygon (the ACTUAL polygon the user saved, not KML rect) ──
  const [projectBoundary, setProjectBoundary] = useState(null);

  // ── Polygon / area state ──
  const [drawMode, setDrawMode] = useState(false);
  const [drawEnabled, setDrawEnabled] = useState(false);
  const [drawKey, setDrawKey] = useState(0);
  const [polygonRing, setPolygonRing] = useState(null);
  const [analysisArea, setAnalysisArea] = useState(null);
  const [polygonError, setPolygonError] = useState(null);
  const errorTimerRef = useRef(null);

  // ── Feature popup (lives here so single-click does NOT re-render SiteMap) ──
  const [selectedFeatureInfo, setSelectedFeatureInfo] = useState(null);

  // ── UI state ──
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [showList, setShowList] = useState(false);
  const [fitTrigger, setFitTrigger] = useState(0);

  // ── Initialize from data ──
  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(async () => {
      setSites(data?.map_data || []);
      setParameters(data?.parameters || {});

      const backendUrlParams = data?.url_parameter_settings || {};
      const storedUrlParams = loadFromStorage(URL_PARAMS_STORAGE_KEY);
      setUrlParameterSettings(
        mergeStoredOverBackend(storedUrlParams, backendUrlParams)
      );

      const backendOutput = data?.output || {};
      const storedOutput = loadFromStorage(OUTPUT_CONFIG_STORAGE_KEY);
      setOutputConfig(
        mergeStoredOutputOverBackend(storedOutput, backendOutput)
      );

      if (projectName) {
        try {
          const savedConfig = await getUserProjectConfig(projectName);
          if (savedConfig?.cords && savedConfig.cords.length >= 3) {
            setProjectBoundary(ensureClosedRing(savedConfig.cords));
          }
        } catch (e) {
          console.error("Failed to fetch project config polygon:", e);
        }
      }

      setLoading(false);
      setFitTrigger(t => t + 1);
    }, 80);
    return () => clearTimeout(timer);
  }, []); 

  // ── Auto-dismiss polygon error ──
  const showPolygonError = useCallback((msg) => {
    setPolygonError(msg);
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    errorTimerRef.current = setTimeout(() => setPolygonError(null), 4000);
  }, []);

  // ── Toggle "Select Area" ON/OFF ──
  const handleToggleDrawMode = useCallback(() => {
    if (!drawMode) {
      setPolygonRing(null);
      setDrawEnabled(true);
      setPolygonError(null);
      setDrawMode(true);
      setDrawKey(k => k + 1);
    } else {
      setDrawMode(false);
      setPolygonRing(null);
      setDrawEnabled(false);
      setAnalysisArea(null);
      setPolygonError(null);
    }
  }, [drawMode]);

  // ── User finished drawing a polygon ──
  const handlePolygonDrawn = useCallback((ring) => {
    if (projectBoundary && !isPolygonWithinBoundary(ring, projectBoundary)) {
      showPolygonError("Polygon must be within the project config boundary (green dashed line). Polygon removed.");
      setDrawKey(k => k + 1);
      return;
    }
    setPolygonError(null);
    setDrawEnabled(false);
    setPolygonRing(ring);
    setAnalysisArea({ type: 'Polygon', coordinates: [ring] });
  }, [projectBoundary, showPolygonError]);

  // ── Sync: apply polygon to cell selection ──
  const handleSyncPolygon = useCallback(() => {
    if (!polygonRing) return;
    setSites(prev => applySitesFromPolygon(prev, polygonRing));
  }, [polygonRing]);

  // ── Clear polygon ──
  const handleClearPolygon = useCallback(() => {
    setPolygonRing(null);
    setDrawEnabled(false);
    setAnalysisArea(null);
    setPolygonError(null);
  }, []);

  // ── Enable Draw interaction ──
  const handleStartDraw = useCallback(() => {
    setDrawEnabled(true);
    setDrawKey(k => k + 1);
    setPolygonError(null);
  }, []);

  // ── Single-click: show info popup (does NOT touch sites → SiteMap won't re-render) ──
  const handleFeatureSelect = useCallback((info) => {
    setSelectedFeatureInfo(info);
  }, []);

  // ── Double-click: toggle cell selection ──
  const handleCellDblClick = useCallback((info) => {
    if (!info || info.type !== 'cell') return;
    const siteIid = info.site?.site_iid;
    const cellIid = info.cell?.cell_iid;
    if (!siteIid || !cellIid) return;
    setSites(prev =>
      prev.map(site => {
        if (site.site_iid !== siteIid) return site;
        return {
          ...site,
          cells: site.cells.map(cell =>
            cell.cell_iid === cellIid ? { ...cell, selected: !cell.selected } : cell,
          ),
        };
      }),
    );
  }, []);

  // ── Sidebar cell / site toggle ──
  const handleCellToggle = useCallback((site_iid, cell_iid) => {
    setSites(prev =>
      prev.map(site => {
        if (site.site_iid !== site_iid) return site;
        return {
          ...site,
          cells: site.cells.map(cell =>
            cell.cell_iid === cell_iid ? { ...cell, selected: !cell.selected } : cell,
          ),
        };
      }),
    );
  }, []);

  const handleSiteToggle = useCallback((site_iid) => {
    setSites(prev => {
      const site = prev.find(s => s.site_iid === site_iid);
      if (!site) return prev;
      const allSelected = site.cells.every(cell => cell.selected);
      return prev.map(s => {
        if (s.site_iid !== site_iid) return s;
        return { ...s, cells: s.cells.map(cell => ({ ...cell, selected: !allSelected })) };
      });
    });
  }, []);

  // ── Focus / Reload ──
  const handleFocus = useCallback(() => {
    setFitTrigger(t => t + 1);
  }, []);

  const reloadMap = useCallback(() => {
    setLoading(true);
    setDrawMode(false);
    setDrawEnabled(false);
    setPolygonRing(null);
    setAnalysisArea(null);
    setPolygonError(null);
    setSelectedFeatureInfo(null);
    setTimeout(() => {
      setSites(data?.map_data || []);
      setParameters(data?.parameters || {});

      const backendUrlParams = data?.url_parameter_settings || {};
      const storedUrlParams = loadFromStorage(URL_PARAMS_STORAGE_KEY);
      setUrlParameterSettings(
        mergeStoredOverBackend(storedUrlParams, backendUrlParams)
      );

      const backendOutput = data?.output || {};
      const storedOutput = loadFromStorage(OUTPUT_CONFIG_STORAGE_KEY);
      setOutputConfig(
        mergeStoredOutputOverBackend(storedOutput, backendOutput)
      );

      setLoading(false);
      setFitTrigger(t => t + 1);
    }, 80);
  }, [data]);

  // ── Persist urlParameterSettings & outputConfig to localStorage ──
  const handleUrlParameterSettingsChange = useCallback((next) => {
    setUrlParameterSettings(next);
    saveToStorage(URL_PARAMS_STORAGE_KEY, next);
  }, []);

  const handleOutputConfigChange = useCallback((next) => {
    setOutputConfig(next);
    saveToStorage(OUTPUT_CONFIG_STORAGE_KEY, namesOnlyOutputConfig(next));
  }, []);

  // ── Merged arrayTypes for UI display ──
  const mergedArrayTypesForUI = useMemo(() => mergeArrayTypes(parameters), [parameters]);

  const handleMergedArrayTypesChange = useCallback((updater) => {
    setParameters(prev => {
      const currentMerged = mergeArrayTypes(prev);
      const nextMerged = typeof updater === "function"
        ? updater({ arrayTypes: currentMerged }).arrayTypes
        : updater.arrayTypes;
      return splitArrayTypesBack(nextMerged, prev);
    });
  }, []);

  // ── Confirm / Close ──
  const handleConfirm = useCallback(() => {
    if (!onConfirm) return;
    const cells = sites.flatMap(site =>
      site.cells.filter(cell => cell.selected).map(cell => cell.cell_iid),
    );
    let boundaries = null;
    if (drawMode && analysisArea) {
      boundaries = analysisArea.coordinates[0]?.map(coord => [coord[0], coord[1]]);
    }

    const cleanParameters = {};
    for (const tech of ["lte", "nr"]) {
      if (!parameters?.[tech]) continue;
      cleanParameters[tech] = {
        arrayTypes: (parameters[tech].arrayTypes || []).map(({ _tech, ...rest }) => rest),
      };
    }

    onConfirm({
      cells,
      boundaries,
      parameters: cleanParameters,
      url_parameter_settings: urlParameterSettings,
      output: outputConfig,
      success: true,
    });
  }, [sites, drawMode, analysisArea, urlParameterSettings, parameters, outputConfig, onConfirm]);

  const handleClose = useCallback(() => {
    if (onClose) onClose({ success: false, cells: [], boundaries: null });
  }, [onClose]);

  const selectedCellCount = useMemo(
    () => sites.reduce((acc, site) => acc + site.cells.filter(c => c.selected).length, 0),
    [sites],
  );

  return (
    <div className="absolute top-0 left-0 right-0 bottom-0 min-h-screen z-[5000000] min-w-screen bg-white/20">
      <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-[2px] bg-black/40">
        <div className="bg-card border border-border rounded-xl shadow-2xl shadow-black/50 w-[95%] h-[85vh] max-w-7xl flex flex-col overflow-hidden">

          {/* ====== Header ====== */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-secondary/50">
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-semibold text-foreground">
                Confirm/Update Cell Selection, Parameter Settings and Map Area
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowList(v => !v)}
                className={`p-2 rounded-lg transition-colors ${
                  showList
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-accent text-muted-foreground hover:text-foreground'
                }`}
                title={showList ? "Hide List" : "Show List"}
              >
                {showList ? <PanelLeftClose className="w-5 h-5" /> : <List className="w-5 h-5" />}
              </button>

              <button
                onClick={() => setIsSettingsModalOpen(true)}
                className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                title="Parameter Settings"
              >
                <Settings className="w-5 h-5" />
              </button>

              <button
                onClick={handleToggleDrawMode}
                disabled={loading}
                className={`px-3 py-2 rounded-lg transition-colors font-medium text-sm ${
                  drawMode
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'bg-secondary text-muted-foreground hover:bg-accent border border-border'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                Select Area {drawMode ? 'ON' : 'OFF'}
              </button>

              {drawMode && !polygonRing && !drawEnabled && (
                <button
                  onClick={handleStartDraw}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-secondary text-muted-foreground hover:bg-accent border border-border transition-colors"
                  title="Draw a selection polygon"
                >
                  <PenTool className="w-4 h-4" />
                  Draw Polygon
                </button>
              )}

              {drawMode && polygonRing && (
                <button
                  onClick={handleSyncPolygon}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 border border-primary/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Select cells inside the polygon"
                >
                  <RefreshCcw className="w-4 h-4" />
                  Sync
                </button>
              )}

              {drawMode && polygonRing && (
                <button
                  onClick={handleClearPolygon}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-secondary text-muted-foreground hover:bg-red-600/20 hover:text-red-400 border border-border transition-colors"
                  title="Clear polygon boundary"
                >
                  <Trash2 className="w-4 h-4" />
                  Clear Polygon
                </button>
              )}

              <button
                onClick={handleFocus}
                className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                title="Focus on selected cells"
              >
                <Crosshair className="w-5 h-5" />
              </button>

              <button
                onClick={reloadMap}
                className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                title="Reload Map"
              >
                <RefreshCw className="w-5 h-5" />
              </button>

              <button
                onClick={handleClose}
                className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* ====== Body ====== */}
          <div className="flex-1 flex overflow-hidden relative">
            {loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/70">
                <div className="flex items-center gap-3 px-6 py-3 bg-card rounded-lg border border-border">
                  <Loader2 className="w-5 h-5 text-primary animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading map data...</span>
                </div>
              </div>
            )}

            {polygonError && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-red-600/90 text-white text-sm rounded-lg shadow-lg">
                {polygonError}
              </div>
            )}

            {showList && (
              <SitesCellsSidebar
                allSites={sites}
                onToggleCell={handleCellToggle}
                onToggleSite={handleSiteToggle}
                disabled={loading}
              />
            )}

            {/* Map + FeaturePopup wrapper */}
            <div className="flex-1 relative overflow-hidden">
              <SiteMap
                sites={sites}
                projectBoundary={projectBoundary}
                drawEnabled={drawEnabled}
                drawKey={drawKey}
                polygonRing={polygonRing}
                onPolygonDrawn={handlePolygonDrawn}
                onSelect={handleFeatureSelect}
                onDblClick={handleCellDblClick}
                fitTrigger={fitTrigger}
              />

              {/* Popup rendered OUTSIDE SiteMap so info clicks don't re-render the map */}
              <FeaturePopup
                info={selectedFeatureInfo}
                onClose={() => setSelectedFeatureInfo(null)}
              />
            </div>
          </div>

          {/* ====== Footer ====== */}
          <div className="p-4 border-t border-border bg-secondary/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3 z-50">
                <label className="text-sm text-foreground font-bold">Array Types:</label>
                <ArrayTypeMultiSelect
                  parameters={{ arrayTypes: mergedArrayTypesForUI }}
                  setParameters={handleMergedArrayTypesChange}
                />
              </div>

              <div className="flex items-center space-x-3">
                <div className="text-xs text-muted-foreground">
                  {selectedCellCount} cells selected
                </div>
                <button
                  onClick={handleClose}
                  className="px-4 py-2 text-muted-foreground bg-secondary hover:bg-accent border border-border rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={selectedCellCount === 0 || !mergedArrayTypesForUI.some(o => o?.isSelected)}
                  className="px-6 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed shadow-lg shadow-primary/20 transition-colors"
                >
                  Confirm ({selectedCellCount})
                </button>
              </div>
            </div>
          </div>
        </div>

        <ParameterSettingsModal
          isOpen={isSettingsModalOpen}
          onClose={() => setIsSettingsModalOpen(false)}
          urlParameterSettings={urlParameterSettings}
          onUrlParameterSettingsChange={handleUrlParameterSettingsChange}
          outputConfig={outputConfig}
          onOutputConfigChange={handleOutputConfigChange}
        />
      </div>
    </div>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import { Sparkles, RefreshCw } from 'lucide-react';
import LoadingButton from '../../LoadingButton';
import { useACSSContext } from '../../context/ACSSContext';
import { setupApi } from '../../api/acssApi';

const DEFAULT_THRESHOLD = -110;
const MIN_THRESHOLD = -200;
const MAX_THRESHOLD = 0;

function AutoGenPanel({ isLocked = false }) {
  const { submitAutoGenConfig, loadCandidateGdl, projectName, setupState } = useACSSContext();
  const [n, setN] = useState(5);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [seed, setSeed] = useState(0);
  const [populationEnabled, setPopulationEnabled] = useState(true);
  const [populationStatus, setPopulationStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState(null);
  const tech = setupState?.polygon?.technology;
  const isFiveG = tech === 'FiveG' || tech === 'NR' || tech === '5G';
  const rsrpLabel = isFiveG ? 'SS-RSRP' : 'RSRP';

  // Probe population-raster availability per project
  useEffect(() => {
    if (!projectName) return;
    let cancelled = false;
    setupApi.getPopulationRasterStatus(projectName)
      .then((s) => {
        if (cancelled) return;
        setPopulationStatus(s || { available: false });
        if (!s?.available) setPopulationEnabled(false);
      });
    return () => { cancelled = true; };
  }, [projectName]);

  // Hydrate from backend state when re-entering this step
  useEffect(() => {
    const cfg = loadCandidateGdl?.autoGenConfig;
    if (cfg) {
      setN(cfg.n ?? 5);
      setThreshold(cfg.threshold_dbm ?? DEFAULT_THRESHOLD);
      setSeed(cfg.seed ?? 0);
      if (typeof cfg.enable_population_weighting === 'boolean') {
        setPopulationEnabled(cfg.enable_population_weighting);
      }
    }
  }, [loadCandidateGdl?.autoGenConfig]);

  const handleSave = useCallback(async () => {
    const thresholdValue = Number(threshold);
    if (
      threshold === ''
      || !Number.isFinite(thresholdValue)
      || thresholdValue < MIN_THRESHOLD
      || thresholdValue > MAX_THRESHOLD
    ) {
      setErrorText(`${rsrpLabel} threshold must be between ${MIN_THRESHOLD} and ${MAX_THRESHOLD} dBm`);
      return;
    }

    setSubmitting(true);
    setErrorText(null);
    try {
      await submitAutoGenConfig({
        n: Number(n),
        threshold_dbm: thresholdValue,
        seed: Number(seed),
        enable_population_weighting: !!populationEnabled,
      });
    } catch (err) {
      setErrorText(err?.message || 'Failed to save auto-gen config');
    } finally {
      setSubmitting(false);
    }
  }, [n, threshold, seed, populationEnabled, submitAutoGenConfig, rsrpLabel]);

  const handleRegenerate = useCallback(() => {
    setSeed(prev => prev + 1);
  }, []);

  const thresholdValue = Number(threshold);
  const isThresholdValid = threshold !== ''
    && Number.isFinite(thresholdValue)
    && thresholdValue >= MIN_THRESHOLD
    && thresholdValue <= MAX_THRESHOLD;
  const isValid = n >= 1 && n <= 10 && isThresholdValid;

  return (
    <div className="mt-3 p-3 rounded-lg bg-card/40 border border-border space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground dark:text-amber-300">
        <Sparkles className="w-3.5 h-3.5" />
        <span>Auto-generate candidates from poor coverage</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="text-[10px] text-muted-foreground">
          N (1-10)
          <input
            type="number" min={1} max={10} value={n} disabled={isLocked || submitting}
            onChange={e => setN(e.target.value)}
            className="mt-0.5 w-full bg-background text-foreground text-xs px-2 py-1 rounded border border-border"
          />
        </label>
        <label className="text-[10px] text-muted-foreground">
          {rsrpLabel} threshold (dBm)
          <input
            type="number" min={MIN_THRESHOLD} max={MAX_THRESHOLD}
            value={threshold} disabled={isLocked || submitting}
            onChange={e => setThreshold(e.target.value)}
            className={`mt-0.5 w-full bg-background text-foreground text-xs px-2 py-1 rounded border ${
              isThresholdValid ? 'border-border' : 'border-red-500'
            }`}
            placeholder={String(DEFAULT_THRESHOLD)}
          />
        </label>
      </div>

      {/* Population-density weighting toggle */}
      <label className={`flex items-start gap-2 text-[10px] ${populationStatus?.available ? 'text-foreground' : 'text-muted-foreground'}`}>
        <input
          type="checkbox"
          checked={!!populationEnabled && !!populationStatus?.available}
          disabled={isLocked || submitting || !populationStatus?.available}
          onChange={(e) => setPopulationEnabled(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          Prioritize by population density
          {populationStatus?.available ? (
            <span className="block text-muted-foreground">
              ✓ {populationStatus.filename}
              {populationStatus.total_population != null && (
                <> · ≈{Math.round(populationStatus.total_population).toLocaleString()} people</>
              )}
            </span>
          ) : (
            <span className="block text-muted-foreground italic">
              No population raster for project {projectName || ''} — drop a GeoTIFF into
              population_rasters/{projectName?.toLowerCase() || '<project>'}/ and re-run setup_datastore
            </span>
          )}
        </span>
      </label>

      {errorText && <div className="text-[10px] text-red-400">{errorText}</div>}

      <div className="flex justify-between gap-2">
        <button
          onClick={handleRegenerate}
          disabled={isLocked || submitting}
          className="flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground"
          title="Increment seed for alternative placement"
        >
          <RefreshCw className="w-3 h-3" />
          Regenerate (seed: {seed})
        </button>
        <LoadingButton
          name={submitting ? 'Saving…' : 'Save Auto-gen Config'}
          onClick={handleSave}
          disabled={isLocked || submitting || !isValid}
          variant="primary"
        />
      </div>
    </div>
  );
}

export default AutoGenPanel;

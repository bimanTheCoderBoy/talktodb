import React, { useState, useEffect, useCallback } from 'react';
import { useACSSContext } from '../context/ACSSContext';
import { executionApi } from '../api/acssApi';
import { CheckCircle2, Loader2, XCircle, Users, Check, Star, Copy, FolderOpen, ChevronDown, ChevronUp, X, Sparkles } from 'lucide-react';

/**
 * Keys in result_details that hold report file paths (not KPI stats).
 * These are rendered separately from the stats grid.
 */
const REPORT_PATH_KEYS = new Set([
  'Report Directory',
  'Report PNG',
  'Report Stats',
]);

/**
 * GoalType 1 KPI keys in display order (Signal Gain section).
 */
const GOAL1_KEYS = [
  'Total Pixels (Best-valid)',
  'Total Pixels (Overlap-valid)',
  'New Valid Pixels',
  'Improved Pixels',
  'Improved Pixels (%)',
  'Average Baseline RSRP (dBm)',
  'Average Best RSRP (dBm)',
  'Avg Absolute Gain (dB)',
  'Avg % Gain',
  'X Value (%)',
  'Goal Satisfied',
];

/**
 * GoalType 2 KPI keys in display order (Threshold Compliance section).
 */
const GOAL2_KEYS = [
  'Threshold (dBm)',
  'Total Pixels (Best-valid)',
  'Pixels Meeting Threshold (Best)',
  '% Meets Threshold (Best)',
  'Pixels Below Threshold (Best)',
  'Pixels Meeting Threshold (Baseline)',
  'Pixels Meeting Threshold (Best, Overlap)',
  'Avg % Gain',
  'Meets Threshold (All)',
];

/**
 * Detect which goal type a result_details dict belongs to based on its keys.
 */
function detectGoalType(details) {
  if (!details) return null;
  if ('X Value (%)' in details || 'Goal Satisfied' in details || 'Avg Absolute Gain (dB)' in details) return 'goal1';
  if ('Threshold (dBm)' in details || '% Meets Threshold (Best)' in details || 'Meets Threshold (All)' in details) return 'goal2';
  return null;
}

/**
 * Format a single result_details value for display.
 */
function formatDetailValue(val) {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toFixed(4);
  }
  return String(val);
}

/**
 * Tiny "copy to clipboard" button with brief feedback.
 */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // fallback — ignore
    }
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      title="Copy path"
      className="ml-1 p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
    >
      {copied ? (
        <Check className="w-3 h-3 text-green-400" />
      ) : (
        <Copy className="w-3 h-3" />
      )}
    </button>
  );
}

/**
 * Collapsible section showing report file paths with copy buttons.
 */
function ReportPathsSection({ reportEntries }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-2 pt-2 border-t border-border">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
        className="flex items-center gap-1 text-[10px] font-medium text-gray-600 dark:text-sky-400 hover:text-gray-700 dark:hover:text-sky-300 transition-colors"
      >
        <FolderOpen className="w-3 h-3" />
        <span>Report Files</span>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          {reportEntries.map(([label, path]) => (
            <div key={label} className="flex items-center text-[10px] gap-1">
              <span className="text-muted-foreground dark:text-slate-400 shrink-0">{label}:</span>
              <span
                className="font-mono text-foreground/80 dark:text-slate-300 truncate flex-1 select-all"
                title={path}
              >
                {path}
              </span>
              <CopyButton text={path} />
            </div>
          ))}
          <p className="text-[9px] text-muted-foreground dark:text-slate-400 mt-1 italic">
            Open these paths in file explorer or share drive to view reports.
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Renders an ordered KPI grid based on goal type, with a section header.
 */
function KpiStatsGrid({ details, isSelected = false }) {
  const goalType = detectGoalType(details);
  const orderedKeys = goalType === 'goal1' ? GOAL1_KEYS : goalType === 'goal2' ? GOAL2_KEYS : null;

  // Filter out report path keys
  let entries;
  if (orderedKeys) {
    // Show in the defined order, then any remaining non-report keys
    const shown = new Set(orderedKeys);
    const ordered = orderedKeys
      .filter((k) => k in details)
      .map((k) => [k, details[k]]);
    const extras = Object.entries(details).filter(
      ([k]) => !shown.has(k) && !REPORT_PATH_KEYS.has(k)
    );
    entries = [...ordered, ...extras];
  } else {
    entries = Object.entries(details).filter(([k]) => !REPORT_PATH_KEYS.has(k));
  }

  if (entries.length === 0) return null;

  const sectionLabel = goalType === 'goal1' ? 'Signal Gain' : goalType === 'goal2' ? 'Threshold Compliance' : 'Stats';

  return (
    <div className={`mt-2 pt-2 border-t ${isSelected ? 'border-primary/30' : 'border-border'}`}>
      <p className={`text-[10px] font-medium mb-1 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{sectionLabel}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {entries.map(([label, value]) => (
          <div key={label} className="flex justify-between text-[10px]">
            <span className={`truncate mr-2 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</span>
            <span className={`font-mono shrink-0 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>
              {formatDetailValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Modal shown when finalEvaluation reaches WAITING_USER.
 * Fetches ALL evaluated candidates from GET /review, lets user pick one combination,
 * POSTs confirmation, then triggers /run again to resume execution.
 */
function CandidateReviewModal() {
  const {
    needsReview,
    setNeedsReview,
    acssSessionId,
    projectName,
    setJobId,
    setIsExecutionListening,
    setExecutionStatus,
    updateExecutionFromSSE,
    addLog,
    setReviewResults,
  } = useACSSContext();

  const [reviewData, setReviewData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCandidates, setSelectedCandidates] = useState(new Set());

  // Fetch review data when modal opens
  useEffect(() => {
    if (!needsReview || !acssSessionId || !projectName) return;

    let cancelled = false;
    const fetchReview = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await executionApi.getReview(acssSessionId, projectName);
        if (!cancelled) {
          setReviewData(data);
          setReviewResults(data);
          // Auto-select the first tied candidate (single selection)
          const firstTied = (data.all_candidates || []).find((c) => c.is_tied);
          setSelectedCandidates(
            firstTied ? new Set([firstTied.candidate_name]) : new Set()
          );
        }
      } catch (err) {
        if (!cancelled) setError('Failed to fetch Candidate Review Data. Please refresh the page and try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchReview();
    return () => { cancelled = true; };
  }, [needsReview, acssSessionId, projectName]);

  const selectCandidate = (name) => {
    setSelectedCandidates((prev) => {
      if (prev.has(name) && prev.size === 1) {
        return new Set();
      }
      return new Set([name]);
    });
  };

  const handleConfirm = async () => {
    if (selectedCandidates.size === 0) return;
    setConfirming(true);
    setError(null);
    try {
      const namesList = Array.from(selectedCandidates);
      // 1) Confirm selection (send list)
      await executionApi.confirmReview(acssSessionId, projectName, namesList);
      addLog(`Candidate(s) confirmed: ${namesList.join(', ')}`);

      // Persist selection into reviewResults so the Results panel can highlight chosen candidates
      setReviewResults((prev) => prev ? {
        ...prev,
        selection: { status: 'confirmed', selected_candidate_names: namesList },
      } : prev);

      // 2) Resume execution
      const result = await executionApi.runExecution(acssSessionId, projectName);
      if (result.status === 'rejected' || result.status === 'needs_review') {
        addLog(result.message || 'Could not resume execution.');
        setError(result.message);
        return;
      }
      setJobId(result.job_id);
      setIsExecutionListening(true);
      setExecutionStatus('running');
      setNeedsReview(false);
      addLog('Execution resumed after candidate selection');
    } catch (err) {
      setError(err.message);
    } finally {
      setConfirming(false);
    }
  };

  const handleClose = async () => {
    setClosing(true);
    setError(null);
    try {
      const result = await executionApi.closeReview(acssSessionId, projectName);
      addLog('Candidate selection cancelled by user.');

      // Apply the returned execution_status_state so finalEvaluation shows cancelled
      if (result.execution_status_state) {
        updateExecutionFromSSE(result.execution_status_state);
      }

      setNeedsReview(false);
      setExecutionStatus('cancelled');
      setIsExecutionListening(false);
    } catch (err) {
      setError('Failed to close. Please refresh the page and try again.');
    } finally {
      setClosing(false);
    }
  };

  if (!needsReview) return null;

  const candidates = reviewData?.all_candidates || [];

  return (
    <div className="absolute top-0 left-0 right-0 bottom-0 min-h-screen z-[5000000] min-w-screen bg-white/20">
      <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-[2px] bg-black/40">
        <div className="w-[640px] max-h-[85vh] bg-card border border-primary/30 rounded-xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-border bg-secondary">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Select Candidate</h3>
            </div>
            <div className="flex items-center gap-3">
              <p className="text-xs text-muted-foreground">
                Choose one combination to keep
              </p>
              <button
                onClick={handleClose}
                disabled={closing}
                className="p-1 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                title="Cancel candidate selection"
              >
                {closing ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-transparent">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-primary animate-spin" />
                <span className="ml-2 text-muted-foreground text-sm">Loading candidates...</span>
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start gap-2">
                <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                <p className="text-xs text-red-300">{error}</p>
              </div>
            )}

            {!loading && reviewData && (
              <>
                {/* Summary stats */}
                <div className="mb-4 p-3 rounded-lg bg-secondary border border-border">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Max Goal Value</span>
                    <span className="text-black-600 dark:text-sky-400 font-mono font-medium">
                      {reviewData.max_goal_value?.toFixed(4) ?? 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>Total Evaluated</span>
                    <span className="font-mono text-foreground">{reviewData.total_evaluated ?? 0}</span>
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>Best (Tied) Candidates</span>
                    <span className="font-mono text-foreground">
                      {candidates.filter((c) => c.is_tied).length}
                    </span>
                  </div>
                </div>

                {/* Candidate list */}
                <div className="space-y-2">
                  {candidates.map((candidate) => {
                    const isSelected = selectedCandidates.has(candidate.candidate_name);
                    const sites = candidate.candidate_name.split('|');

                    const reportEntries = candidate.result_details
                      ? Object.entries(candidate.result_details).filter(
                          ([key]) => REPORT_PATH_KEYS.has(key) && candidate.result_details[key]
                        )
                      : [];

                    return (
                      <button
                        key={candidate.candidate_name}
                        onClick={() => selectCandidate(candidate.candidate_name)}
                        className={`w-full text-left p-3 rounded-lg border transition-all ${
                          isSelected
                            ? 'bg-primary/20 border-primary ring-1 ring-primary/60 shadow-md shadow-primary/20 hover:bg-gray-200/25 hover:ring-primary/80 dark:hover:bg-sky-600/10 dark:hover:ring-primary/80'
                            : 'bg-secondary border-border/80 dark:border-slate-600 opacity-90 hover:opacity-100 hover:border-gray-400 hover:bg-gray-50 dark:hover:border-sky-400/70 dark:hover:bg-sky-500/10'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            {isSelected ? (
                              <CheckCircle2 className="w-4 h-4 text-gray-600 dark:text-sky-300" />
                            ) : (
                              <div className="w-4 h-4 rounded-full border-2 border-slate-400 dark:border-slate-400 bg-transparent shrink-0" />
                            )}
                            <span className={`text-sm font-medium ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>
                              {sites.length} site{sites.length > 1 ? 's' : ''}
                            </span>
                            {candidate.is_tied && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded bg-amber-400/20 text-amber-600 border border-amber-500/30">
                                <Star className="w-3 h-3" />
                                Best
                              </span>
                            )}
                          </div>
                          <span className={`px-2 py-0.5 text-xs font-mono rounded-full ${
                            isSelected
                              ? 'text-white bg-black dark:bg-secondary dark:text-foreground'
                              : 'bg-secondary text-muted-foreground'
                          }`}>
                            {candidate.goal_value?.toFixed(4)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {sites.map((site) => (
                            <span
                              key={site}
                              className={`px-1.5 py-0.5 text-[10px] font-mono rounded ${
                                isSelected
                                  ? 'text-white bg-black dark:bg-secondary dark:text-foreground'
                                  : 'bg-secondary dark:bg-secondary dark:text-muted-foreground'
                              }`}
                            >
                              {site}
                            </span>
                          ))}
                        </div>

                        {/* Auto-gen annotations (v1: auto_generated + covers_poor_bins).
                            median_uplift_dB is v1.1 deferred — null-gated so it lights up
                            automatically when backend populates result_details.median_uplift_dB. */}
                        {candidate.auto_generated && (
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 flex items-center gap-1">
                              <Sparkles className="w-2.5 h-2.5" /> auto-generated
                            </span>
                            {candidate.covers_poor_bins != null && (
                              <span className={`text-[10px] ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>covers {candidate.covers_poor_bins} poor bins</span>
                            )}
                            {/* median_uplift_dB is v1.1 deferred — render only if backend populates it (no-op in v1) */}
                            {candidate.median_uplift_dB != null && (
                              <span className="text-[10px] text-emerald-400">+{Number(candidate.median_uplift_dB).toFixed(1)} dB median uplift</span>
                            )}
                          </div>
                        )}

                        {/* KPI stats (grouped by goal type) */}
                        {candidate.result_details && Object.keys(candidate.result_details).length > 0 && (
                          <KpiStatsGrid details={candidate.result_details} isSelected={isSelected} />
                        )}

                        {/* Report paths section */}
                        {reportEntries.length > 0 && (
                          <ReportPathsSection reportEntries={reportEntries} />
                        )}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-border bg-secondary">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground dark:text-slate-300">
                {selectedCandidates.size > 0
                  ? '1 combination selected'
                  : 'Select one combination to continue'
                }
              </div>
              <button
                onClick={handleConfirm}
                disabled={selectedCandidates.size === 0 || confirming}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all border ${
                  selectedCandidates.size === 0 || confirming
                    ? 'bg-muted text-muted-foreground border-border cursor-not-allowed opacity-70'
                    : 'bg-black text-white border-gray-500 hover:bg-gray-500 dark:bg-sky-500 dark:hover:bg-sky-400 dark:text-slate-950 dark:border-sky-400 shadow-lg shadow-gray-500/25 dark:shadow-sky-500/25'
                }`}
              >
                {confirming ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Confirming...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Confirm &amp; Resume
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CandidateReviewModal;

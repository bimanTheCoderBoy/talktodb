import React, { useRef, useEffect, useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import keycloak from '../../keycloak';
import { useACSSContext } from '../context/ACSSContext';
import { executionApi, setupApi } from '../api/acssApi';
import {
  Zap, Circle, CheckCircle2, Loader2, AlertCircle,
  LineChart, MapPin, GitBranch, Calculator, Database,
  Heart, XCircle, Clock, Wifi, WifiOff,
  Activity, RefreshCw, UserCheck, Layers, FileImage, Trash2, Sparkles,
} from 'lucide-react';

const STEP_ICONS = {
  baselineCoverage: LineChart,
  autoGenCandidates: Sparkles,
  creatingCandidates: MapPin,
  runingCoverageForCandidates: Activity,
  calculateCombinations: GitBranch,
  calculation: Calculator,
  finalEvaluation: Database,
  updateActualCandidates: RefreshCw,
  runningCoverageForBaselineAndCandidates: Layers,
  convertingBilsForInteractiveView: FileImage,
};

const STATUS_STYLES = {
  done: { badge: 'bg-green-300/20 text-green-500 border-green-500/30', icon: CheckCircle2 },
  running: { badge: 'bg-amber-300/20 text-amber-600 border-amber-500/30', icon: Loader2 },
  error: { badge: 'bg-red-300/20 text-red-500 border-red-500/30', icon: AlertCircle },
  pending: { badge: 'bg-secondary text-muted-foreground border-border', icon: Circle },
  waiting_user: { badge: 'bg-purple-300/20 text-purple-500 border-purple-500/30', icon: UserCheck },
  cancelled: { badge: 'bg-orange-300/20 text-orange-500 border-orange-500/30', icon: XCircle },
};

const CELERY_STYLES = {
  SUCCESS: { bg: 'bg-green-300/20', text: 'text-green-500', border: 'border-green-500/30' },
  STARTED: { bg: 'bg-amber-300/20', text: 'text-amber-500', border: 'border-amber-500/30' },
  FAILURE: { bg: 'bg-red-300/20', text: 'text-red-500', border: 'border-red-500/30' },
  PENDING: { bg: 'bg-secondary', text: 'text-muted-foreground', border: 'border-border' },
};

function ExecutionPanel({ isSetupComplete }) {
  const {
    executionSteps, currentExecutionStep, jobId,
    isExecutionListening, toggleExecutionListening,
    updateExecutionFromSSE, updateCeleryStatus, celeryStatus, addLog,
    acssSessionId, projectName, setupState,
  } = useACSSContext();

  const abortControllerRef = useRef(null);
  const healthIntervalRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  // Standalone EDS cleanup — testing helper. Detached from the review-modal
  // close flow so it can be invoked at any time, including after a run that
  // failed midway and left orphaned EDS objects.
  const [cleaningEds, setCleaningEds] = useState(false);
  const [cleanupBanner, setCleanupBanner] = useState(null);

  const handleCleanupEds = useCallback(async () => {
    if (!acssSessionId || !projectName) return;
    if (!window.confirm(
      'Delete the last-created Cell, MU, and Location objects from EDS?\n\n' +
      'Frees up the IID+bvid pairs so the next Run can re-create them. ' +
      'Use only for testing iterations.'
    )) return;
    setCleaningEds(true);
    setCleanupBanner(null);
    try {
      const result = await setupApi.cleanupEdsSites(acssSessionId, projectName);
      const { cell = 0, mu = 0, location = 0 } = result.deleted || {};
      const errs = result.errors || {};
      const errCount = Object.keys(errs).length;
      addLog(`EDS cleanup: deleted ${cell} cell, ${mu} MU, ${location} location${errCount ? ` (errors on ${errCount} tier)` : ''}`);
      setCleanupBanner({
        kind: errCount ? 'partial' : 'ok',
        text: errCount
          ? `Partial — ${Object.entries(errs).map(([t, m]) => `${t}: ${m}`).join('; ')}`
          : `Deleted ${cell} cell, ${mu} MU, ${location} location`,
      });
    } catch (err) {
      setCleanupBanner({ kind: 'error', text: err.message || 'Cleanup failed' });
    } finally {
      setCleaningEds(false);
    }
  }, [acssSessionId, projectName, addLog]);

  // SSE for state updates — with auto-reconnect on error
  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const connectSSE = () => {
      if (!jobId) return;

      const sseUrl = `${import.meta.env.VITE_ACSS_API_URL}/api/v1/redis/execution/${jobId}`;
      const ctrl = new AbortController();
      abortControllerRef.current = ctrl;

      fetchEventSource(sseUrl, {
        signal: ctrl.signal,
        headers: {
          Authorization: `Bearer ${keycloak.token}`,
        },
        onopen() {
          console.log('[SSE] Connection opened');
        },
        onmessage(event) {
          if (!event.data) return;
          try {
            updateExecutionFromSSE(JSON.parse(event.data));
          } catch (err) {
            console.error('[SSE] Parse error:', err);
          }
        },
        onerror() {
          console.warn('[SSE] Connection error — will auto-reconnect in 3s');
          reconnectTimerRef.current = setTimeout(connectSSE, 3000);
        },
        openWhenHidden: true,
      });
    };

    connectSSE();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [isExecutionListening, jobId, updateExecutionFromSSE]);

  // Polling for health (auto-stop when complete)
  useEffect(() => {
    if (healthIntervalRef.current) {
      clearInterval(healthIntervalRef.current);
      healthIntervalRef.current = null;
    }

    if (isExecutionListening && jobId) {
      // console.log('[Health] Starting polling for job:', jobId);
      
      const checkHealth = async () => {
        const health = await executionApi.getJobHealth(jobId);
        // console.log('[Health] Status:', health);
        updateCeleryStatus(health);

        if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(health.status)) {
          // console.log('[Health] Task finished, stopping polling');
          clearInterval(healthIntervalRef.current);
          healthIntervalRef.current = null;
          if (health.status === 'FAILURE') {
            const err = String(health.error || '');
            if (err.includes('Work Paused for user confirmation')) {
              addLog('Execution paused — waiting for candidate selection.');
            } else {
              addLog(`Execution failed: ${health.error}`);
            }
          }
          if (health.status === 'SUCCESS') {
            if (health.paused) {
              addLog(health.message || 'Execution paused — waiting for candidate selection.');
            } else if (health.skipped) {
              addLog(health.message || 'Nothing to run for this session.');
            } else {
              addLog('Execution completed');
            }
          }
        }
      };

      checkHealth(); // Initial check
      healthIntervalRef.current = setInterval(checkHealth, 5000);
    }

    return () => {
      if (healthIntervalRef.current) {
        clearInterval(healthIntervalRef.current);
        healthIntervalRef.current = null;
      }
    };
  }, [isExecutionListening, jobId, updateCeleryStatus, addLog]);

  const celeryStyle = celeryStatus ? CELERY_STYLES[celeryStatus.status] || CELERY_STYLES.PENDING : null;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-primary" />
          <span className="text-xs font-semibold text-primary uppercase tracking-wider">Execution</span>
        </div>

        <div className="flex items-center gap-1.5">
          {acssSessionId && projectName && (
            <button
              onClick={handleCleanupEds}
              disabled={cleaningEds}
              title="Testing helper — delete last-created Cell/MU/Location objects from EDS"
              className={`px-2 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 border transition-colors ${
                cleaningEds
                  ? 'border-border text-muted-foreground cursor-not-allowed'
                  : 'border-red-500/30 text-red-500 hover:bg-red-500/10 hover:border-red-500/50'
              }`}
            >
              {cleaningEds
                ? <><Loader2 className="w-2.5 h-2.5 animate-spin" /> Cleaning…</>
                : <><Trash2 className="w-2.5 h-2.5" /> Clean EDS</>}
            </button>
          )}
          {jobId && (
            <button
              onClick={toggleExecutionListening}
              className={`px-2 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 transition-colors ${
                isExecutionListening ? 'bg-green-600/20 text-green-400' : 'bg-secondary text-muted-foreground'
              }`}
            >
              {isExecutionListening ? <><Wifi className="w-2.5 h-2.5" /> Live</> : <><WifiOff className="w-2.5 h-2.5" /> Connect</>}
            </button>
          )}
        </div>
      </div>

      {cleanupBanner && (
        <div className={`mb-2 px-2 py-1 rounded text-[10px] border ${
          cleanupBanner.kind === 'ok'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            : cleanupBanner.kind === 'partial'
              ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
              : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>
          EDS cleanup: {cleanupBanner.text}
        </div>
      )}
      
      {/* Job Health */}
      {jobId && celeryStatus && (
        <div className={`mb-3 p-2 rounded-lg border ${celeryStyle.bg} ${celeryStyle.border}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Heart className={`w-3.5 h-3.5 ${celeryStyle.text}`} />
              <span className="text-[10px] font-semibold uppercase text-muted-foreground">Health</span>
            </div>
            <span className={`text-[11px] font-medium ${celeryStyle.text}`}>{celeryStatus.status}</span>
          </div>
          {celeryStatus.error && (
            <p className="mt-2 p-2 bg-red-500/20 border border-red-500/30 rounded text-[10px] text-red-600 dark:text-red-300 font-mono break-all">
              {celeryStatus.error}
            </p>
          )}
        </div>
      )}
      
      {/* Steps */}
      <div className={`space-y-2 ${!isSetupComplete ? 'opacity-50 pointer-events-none' : ''}`}>
        {executionSteps.map((step, i) => {
          const Icon = STEP_ICONS[step.name] || Circle;
          const isActive = currentExecutionStep === step.name;
          const style = STATUS_STYLES[step.status] || STATUS_STYLES.pending;
          const StatusIcon = style.icon;

          const isAutoGenStep = step.name === 'autoGenCandidates';
          const autoGenEnabled = !!setupState?.loadCandidateGdl?.autoGenConfig;
          const isDisabled = isAutoGenStep && !autoGenEnabled;

          return (
            <div
              key={step.name}
              className={`relative p-3 rounded-lg transition-all ${
                isDisabled ? 'opacity-30' :
                isActive ? 'bg-primary/10 border border-primary/30' : 'bg-secondary/30 border border-transparent'
              }`}
            >
              <div className="absolute -left-1 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-card border border-border flex items-center justify-center text-[10px] text-muted-foreground">
                {i + 1}
              </div>

              <div className="flex items-center gap-3 ml-3">
                <div className={`p-2 rounded-lg ${isActive && !isDisabled ? 'bg-primary/20' : 'bg-secondary'}`}>
                  <Icon className={`w-4 h-4 ${isActive && !isDisabled ? 'text-primary' : 'text-muted-foreground'}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium truncate ${isActive && !isDisabled ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {step.label}
                    </span>
                    {isDisabled
                      ? <XCircle className="w-4 h-4 text-muted-foreground" />
                      : <StatusIcon className={`w-4 h-4 ${style.badge.split(' ')[1]} ${step.status === 'running' ? 'animate-spin' : ''}`} />
                    }
                  </div>
                  
                  {!isDisabled && step.status === 'running' && (
                    <div className="mt-1.5 w-full bg-secondary rounded-full h-1.5">
                      <div className="bg-amber-400 h-1.5 rounded-full transition-all" style={{ width: `${step.progress || 0}%` }} />
                    </div>
                  )}
                  
                  <div className="mt-1 flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full border capitalize ${isDisabled ? 'bg-secondary/50 text-muted-foreground border-border' : style.badge}`}>
                      {isDisabled ? 'Disabled' : step.status === 'waiting_user' ? 'Awaiting User' : step.status === 'cancelled' ? 'Cancelled' : step.status}
                    </span>
                    {!isDisabled && step.progress > 0 && step.status === 'running' && (
                      <span className="text-[10px] text-muted-foreground">{step.progress}%</span>
                    )}
                  </div>
                </div>
              </div>

              {isActive && !isDisabled && <div className="absolute left-0 top-2 bottom-2 w-0.5 bg-primary rounded-full" />}
            </div>
          );
        })}
      </div>
      
      {!isSetupComplete && (
        <div className="mt-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <p className="text-amber-600 dark:text-amber-400 text-xs font-semibold tracking-wide text-center">Complete setup to enable execution</p>
        </div>
      )}
      
      {jobId && (
        <div className="mt-2 px-2 py-1.5 bg-secondary/30 rounded text-[10px] flex items-center justify-between">
          <span className="text-muted-foreground font-mono">Job: {jobId.slice(0, 8)}...</span>
          <span className={isExecutionListening ? 'text-green-400' : 'text-muted-foreground'}>
            {isExecutionListening && <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse mr-1" />}
            {isExecutionListening ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      )}
    </div>
  );
}

export default ExecutionPanel;

import React, { useState, useEffect, useCallback } from 'react';
import { Settings, CheckCircle2, Rocket, XCircle } from 'lucide-react';

import LoadProjectStep from './LoadProjectStep';
import PolygonSelectionStep from './PolygonSelectionStep';
import LoadCandidateGdlStep from './LoadCandidateGdlStep';
import CandidateTable from './CandidateTable';
import DefineGoalStep from './DefineGoalStep';
import { useACSSContext } from '../../context/ACSSContext';
import { EXECUTION_STEP_DEFINITIONS } from '../../context/ACSSContext';
import { executionApi } from '../../api/acssApi';

function Setup({
  // Setup completion state
  isSetupComplete,
  executionStatus,

  // Load Project props
  loadProjectStatus,
  projectName,

  // Polygon Selection props
  polygonStatus,
  isDrawingMode,
  boundaryRadius,
  handleToggleDrawing,
  handleBoundaryRadiusChange,

  // Load Candidate GDL props
  gdlStatus,
  gdlFileName,
  fileInputRef,
  handleFileSelect,
  handleFileRemove,
  handleGdlFileUpload,

  // Define Goal props
  goalStatus,
  goalOptions,
  goalType,
  onGoalTypeChange,
  goalParameters,
  onGoalParametersChange,
  handleSaveGoal,
  isGoalFormValid,
  goalsLoading,
  goalsError,
}) {

  const {
    acssSessionId,
    setExecutionStatus,
    setCurrentExecutionStep,
    setJobId,
    setIsExecutionListening,
    setNeedsReview,
    addLog,
    setupState,
  } = useACSSContext();

  // Lock all setup inputs while execution is running or completed
  const isLocked = executionStatus === 'running' || executionStatus === 'completed';

  // Detect whether user arrived from Coverage Agent handoff.
  // Read sessionStorage ONCE on mount — do NOT remove it here
  // (MapView.jsx removes it on its own mount path; double-removal breaks refresh).
  const [cameFromCoverage, setCameFromCoverage] = useState(false);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('acssHandoff');
      if (raw) {
        const handoff = JSON.parse(raw);
        if (handoff?.source === 'coverage-2d') {
          setCameFromCoverage(true);
        }
      }
    } catch {
      // Malformed JSON — treat as no handoff
    }
  }, []);

  const runExecution = useCallback(async () => {
    if (!isSetupComplete || !acssSessionId) {
      console.warn('Cannot start execution: Setup incomplete or no session');
      return null;
    }

    try {
      setExecutionStatus('running');
      setCurrentExecutionStep(EXECUTION_STEP_DEFINITIONS[0].name);
      const result = await executionApi.runExecution(acssSessionId, projectName);

      // Graceful reject — session already finished / cancelled
      if (result.status === 'rejected') {
        addLog(result.message || 'Cannot start execution for this session.');
        setExecutionStatus('cancelled');
        return null;
      }

      // Reopen candidate selection after a prior cancel
      if (result.status === 'needs_review') {
        addLog(result.message || 'Please select a candidate to continue.');
        setNeedsReview(true);
        setExecutionStatus('waiting_user');
        setCurrentExecutionStep('finalEvaluation');
        return null;
      }

      // Store job_id and enable SSE listening
      setJobId(result.job_id);
      setIsExecutionListening(true);

      return result.job_id;
    } catch (error) {
      console.error('Failed to start execution:', error);
      addLog(error.message || 'Failed to start execution.');
      setExecutionStatus('error');
      return null;
    }
  }, [isSetupComplete, acssSessionId, projectName, addLog, setNeedsReview, setExecutionStatus, setCurrentExecutionStep, setJobId, setIsExecutionListening]);


  return (
    <div>
      <div className="flex items-center gap-2 mb-2 px-1">
        <Settings className="w-3.5 h-3.5 text-muted-foreground dark:text-amber-400" />
        <span className="text-xs font-semibold text-muted-foreground dark:text-amber-400 uppercase tracking-wider">Setup</span>
        {isSetupComplete && (
          <CheckCircle2 className="w-3.5 h-3.5 text-green-500 ml-auto" />
        )}
      </div>

      <div className="space-y-2">
        {/* Step 1: Load Project */}
        <LoadProjectStep
          status={loadProjectStatus}
          projectName={projectName}
        />

        {/* Step 2: Polygon Selection */}
        <PolygonSelectionStep
          status={polygonStatus}
          isDrawingMode={isDrawingMode}
          boundaryRadius={boundaryRadius}
          onToggleDrawing={handleToggleDrawing}
          onBoundaryRadiusChange={handleBoundaryRadiusChange}
          isLocked={isLocked}
        />

        {/* Step 3: Load Candidate GDL */}
        <LoadCandidateGdlStep
          status={gdlStatus}
          fileName={gdlFileName}
          fileInputRef={fileInputRef}
          onFileSelect={handleFileSelect}
          onFileRemove={handleFileRemove}
          onUpload={handleGdlFileUpload}
          isLocked={isLocked}
          showAutoGenOption={true}
        />

        {/* Candidate table — rendered below the GDL step regardless of mode.
            Populated from setupState.allCandidates (auto-gen execution sub-step
            or GDL upload via session restore). isLocked prevents delete during run. */}
        <CandidateTable
          candidates={setupState.allCandidates}
          isLocked={isLocked}
        />

        {/* Step 4: Define Goal
            nCandidates drives the dynamic K-value cap inside DefineGoalStep:
            - Auto-gen path: target N from autoGenConfig (set at setup time)
            - Manual upload: actual count from allCandidates (set post-parse)
            - Either way, K cap = max(1, nCandidates - 1) so K never equals N
              (C(N,N)=1 trivial combination is rejected by design). */}
        <DefineGoalStep
          status={goalStatus}
          goalOptions={goalOptions ?? []}
          goalType={goalType}
          onGoalTypeChange={onGoalTypeChange}
          goalParameters={goalParameters ?? {}}
          onGoalParametersChange={onGoalParametersChange}
          isGoalFormValid={isGoalFormValid}
          onSaveGoal={handleSaveGoal}
          goalsLoading={goalsLoading}
          goalsError={goalsError}
          isLocked={isLocked}
          technology={setupState.polygon?.technology ?? null}
          nCandidates={
            setupState.loadCandidateGdl?.autoGenConfig?.n
            ?? setupState.allCandidates?.length
            ?? null
          }
        />
      </div>

      {/* Execute Button */}
      <button
        onClick={async () => {
          const jobId = await runExecution();
          if (jobId) {
            console.log('Execution started with job:', jobId);
          }
        }}
        disabled={!isSetupComplete || executionStatus === 'running' || executionStatus === 'completed'}
        className={`
          mt-3 w-full flex items-center justify-center gap-2 px-4 py-2.5
          rounded-lg font-semibold text-sm transition-all duration-200
          ${executionStatus === 'completed'
            ? 'bg-green-500/20 text-green-400 border border-green-500/30 cursor-default'
            : executionStatus === 'cancelled'
              ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30 cursor-default'
              : isSetupComplete && executionStatus !== 'running'
                ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white shadow-lg shadow-green-500/25'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
          }
        `}
      >
        {executionStatus === 'completed' ? (
          <><CheckCircle2 className="w-4 h-4" /> Execution Complete</>
        ) : executionStatus === 'cancelled' ? (
          <><XCircle className="w-4 h-4" /> Candidate Selection Cancelled</>
        ) : executionStatus === 'running' ? (
          <><Rocket className="w-4 h-4 animate-pulse" /> Execution Running...</>
        ) : (
          <><Rocket className="w-4 h-4" /> Execute</>
        )}
      </button>
    </div>
  );
}

export default Setup;

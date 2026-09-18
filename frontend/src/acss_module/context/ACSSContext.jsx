import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { setupApi, sessionApi } from '../api/acssApi';

const ACSSContext = createContext(null);

// ============ SETUP DEFINITIONS ============
// Setup items are prerequisites before execution begins
const SETUP_DEFINITIONS = [
  { name: 'loadProject', label: 'Load Project' },
  { name: 'polygon', label: 'Polygon Selection' },
  { name: 'loadCandidateGdl', label: 'Load Candidate GDL' },
  { name: 'defineGoal', label: 'Define Goal' },
];

// ============ EXECUTION STEP DEFINITIONS ============
// Execution steps run in order after setup is complete
const EXECUTION_STEP_DEFINITIONS = [
  { name: 'baselineCoverage', label: 'Run Baseline Coverage' },
  { name: 'autoGenCandidates', label: 'Auto-Gen Candidates' },
  { name: 'creatingCandidates', label: 'Creating Sites in ASSET' },
  { name: 'runingCoverageForCandidates', label: 'Running Coverage for Candidates' },
  { name: 'calculateCombinations', label: 'Calculating Combinations' },
  { name: 'calculation', label: 'Calculation' },
  { name: 'finalEvaluation', label: 'Final Evaluation' },
  { name: 'updateActualCandidates', label: 'Update Actual Candidates' },
  { name: 'runningCoverageForBaselineAndCandidates', label: 'Running Coverage with Updated Site List' },
  { name: 'convertingBilsForInteractiveView', label: 'Converting BILs for Interactive View' },
];

// Initial setup state
const INITIAL_SETUP_STATE = {
  loadProject: {
    status: 'pending',        // 'pending' | 'done' | 'error' - Auto-set to 'done' on initializeSession success
  },
  polygon: {
    status: 'pending',        // 'pending' | 'running' | 'done' | 'error'
    isDrawing: false,         // Whether drawing mode is active
    coords: null,             // Array of [lon, lat] coordinates for SIM_AREA
    boundaryRadius: 5,        // Boundary expansion radius in km
    boundaryCoords: null,     // Array of [lon, lat] coordinates for boundary
    vertices: 0,              // Number of vertices
    timestamp: null,          // When polygon was completed
    baselineCells: null,      // Array of cell_iid values selected for baseline coverage
    arrayType: null,          // Selected array type (e.g., 'LTE_Best_RSRP', 'LTE_DL_Loss')
    selectedBand: null,       // Band selected in baseline cell selection modal
  },
  loadCandidateGdl: {
    status: 'pending',        // 'pending' | 'done' | 'error'
    file: null,               // Selected file object
    fileName: null,           // Selected file name
    autoGenConfig: null,      // null = manual upload mode; object = auto-gen mode
  },
  defineGoal: {
    status: 'pending',        // 'pending' | 'done' | 'error'
    goalType: 'increase_rsrp',
    parameters: { x_value: '', k_value: 1 },  // defaults for default goal; other goals get defaults on switch
  },
  allCandidates: [],          // populated from server; optimistically filtered on deleteAutoGenCandidate
};

// Initialize execution steps with default pending status
// Structure matches backend execution_status_state
const initializeExecutionSteps = () => {
  return EXECUTION_STEP_DEFINITIONS.map((step) => ({
    name: step.name,
    label: step.label,
    status: 'pending',
    progress: 0,
    startTime: null,
    endTime: null,
  }));
};

export function ACSSProvider({ children }) {
  // Session and project info
  const [acssSessionId, setAcssSessionId] = useState();
  const [projectName, setProjectName] = useState();
  const [project_cords, setProject_cords] = useState(null);
  
  // Setup state - contains polygon and other setup-related data
  const [setupState, setSetupState] = useState(INITIAL_SETUP_STATE);
  
  // Current execution step (only for execution steps, not setup)
  const [currentExecutionStep, setCurrentExecutionStep] = useState(null);
  
  // Execution steps array with status tracking
  const [executionSteps, setExecutionSteps] = useState(initializeExecutionSteps);
  
  // Log messages
  const [logs, setLogs] = useState([]);
  
  // Files map
  const [files, setFiles] = useState({});
  
  // Execution status: 'not started' | 'running' | 'completed' | 'error' | 'waiting_user'
  const [executionStatus, setExecutionStatus] = useState('not started');
  
  // Whether finalEvaluation is paused waiting for user candidate selection
  const [needsReview, setNeedsReview] = useState(false);
  
  // Job ID from Celery task (used for SSE connection)
  const [jobId, setJobId] = useState(null);
  
  // Execution SSE listening state
  const [isExecutionListening, setIsExecutionListening] = useState(false);
  
  // Celery task status for job health monitoring
  // { task_id, status: 'PENDING'|'STARTED'|'SUCCESS'|'FAILURE'|'REVOKED', error, traceback }
  const [celeryStatus, setCeleryStatus] = useState(null);

  // Review results (persisted after modal closes so they remain visible in the sidebar)
  // Shape: { max_goal_value, total_evaluated, all_candidates, tied_candidates, selection }
  const [reviewResults, setReviewResults] = useState(null);

  // Goals list from API (for Define Goal dropdown)
  const [goalOptions, setGoalOptions] = useState([]);
  const [goalsLoading, setGoalsLoading] = useState(false);
  const [goalsError, setGoalsError] = useState(null);
  
  // Check if setup is complete (all setup items are done)
  const isSetupComplete = 
    setupState.loadProject.status === 'done' &&
    setupState.polygon.status === 'done' &&
    setupState.loadCandidateGdl.status === 'done' &&
    setupState.defineGoal.status === 'done';

  // Fetch goals list when ACSS module is used
  const fetchGoals = useCallback(async () => {
    setGoalsLoading(true);
    setGoalsError(null);
    try {
      const data = await setupApi.getGoals();
      setGoalOptions(data?.goals ?? []);
    } catch (err) {
      setGoalsError(err?.message ?? 'Failed to load goals');
      setGoalOptions([]);
    } finally {
      setGoalsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGoals();
  }, [fetchGoals]);

  // ============ SETUP STATE ACTIONS ============
  
  // Update polygon state
  const updatePolygon = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      polygon: { ...prev.polygon, ...updates },
    }));
  }, []);

  // Start polygon drawing mode
  const startPolygonDrawing = useCallback(() => {
    updatePolygon({ isDrawing: true, status: 'running' });
  }, [updatePolygon]);

  // Cancel polygon drawing mode
  const cancelPolygonDrawing = useCallback(() => {
    updatePolygon({ isDrawing: false, status: 'pending' });
  }, [updatePolygon]);

  // Complete polygon with coordinates, baseline cells, array type, and technology
  const completePolygon = useCallback((coords, boundaryCoords, baselineCells = null, arrayType = null, technology = null, selectedBand = null) => {
    updatePolygon({
      status: 'done',
      isDrawing: false,
      coords,
      boundaryCoords,
      vertices: coords?.length || 0,
      timestamp: new Date().toISOString(),
      baselineCells,
      arrayType,
      technology,
      selectedBand,
    });
  }, [updatePolygon]);

  // Clear polygon and reset
  const clearPolygon = useCallback(() => {
    updatePolygon({
      status: 'pending',
      isDrawing: false,
      coords: null,
      boundaryCoords: null,
      vertices: 0,
      timestamp: null,
      baselineCells: null,
      arrayType: null,
      selectedBand: null,
    });
  }, [updatePolygon]);

  // Update boundary radius
  const setBoundaryRadius = useCallback((radius) => {
    updatePolygon({ boundaryRadius: radius });
  }, [updatePolygon]);

  // ============ LOAD PROJECT ACTIONS ============
  
  // Update load project state
  const updateLoadProject = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      loadProject: { ...prev.loadProject, ...updates },
    }));
  }, []);

  // Mark project as loaded (called on successful initializeSession)
  const markProjectLoaded = useCallback(() => {
    updateLoadProject({ status: 'done' });
  }, [updateLoadProject]);

  // ============ CANDIDATE GDL ACTIONS ============
  
  // Update candidate GDL state
  const updateCandidateGdl = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      loadCandidateGdl: { ...prev.loadCandidateGdl, ...updates },
    }));
  }, []);

  // Set candidate GDL file
  const setCandidateGdlFile = useCallback((file) => {
    updateCandidateGdl({
      file,
      fileName: file?.name || null,
      status:'pending',
    });
  }, [updateCandidateGdl]);

  // Update candidate GDL file status
  const markCandidateGdlDone = useCallback(() => {
     setSetupState((prev) => ({
      ...prev,
      loadCandidateGdl: { ...prev.loadCandidateGdl, status: 'done' },
    }));
  }, []);

  // Clear candidate GDL file
  const clearCandidateGdlFile = useCallback(() => {
    updateCandidateGdl({
      file: null,
      fileName: null,
      status: 'pending',
    });
  }, [updateCandidateGdl]);

  // ============ AUTO-GEN CONFIG ACTIONS ============

  // Update auto-gen config draft (local form state before submit)
  const setAutoGenConfigDraft = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      loadCandidateGdl: {
        ...prev.loadCandidateGdl,
        autoGenConfig: { ...(prev.loadCandidateGdl.autoGenConfig || {}), ...updates },
      },
    }));
  }, []);

  // Submit auto-gen config to the backend and reflect response into state.
  // The backend (autogenv2 service layer) now generates the skeleton GDL
  // immediately, so we refresh the session to pick up allCandidates.
  const submitAutoGenConfig = useCallback(async (config) => {
    if (!acssSessionId) throw new Error('No active ACSS session');
    const data = await setupApi.postAutoGenConfig(acssSessionId, config, projectName);
    // Backend returns { session_id, load_candidate_gdl }. Reflect into setupState.
    if (data?.load_candidate_gdl) {
      setSetupState((prev) => ({
        ...prev,
        loadCandidateGdl: {
          ...prev.loadCandidateGdl,
          ...data.load_candidate_gdl,
          status: 'done',
        },
      }));
    }
    // Refresh session to pick up allCandidates generated by the v2 service layer
    try {
      const sessionResponse = await sessionApi.createOrGetSession({
        acss_session_id: acssSessionId,
        project_name: projectName,
      });
      if (sessionResponse.setup_state) {
        setSetupState(sessionResponse.setup_state);
      }
    } catch (err) {
      console.error('[ACSS] Failed to refresh session after autogen config:', err);
    }
    return data;
  }, [acssSessionId, projectName]);

  // Delete an auto-gen candidate by site_iid; optimistically removes it from local state
  const deleteAutoGenCandidate = useCallback(async (siteIid) => {
    if (!acssSessionId) throw new Error('No active ACSS session');
    const data = await setupApi.deleteCandidate(acssSessionId, siteIid, projectName);
    // Optimistically filter the deleted site_iid out of local state
    setSetupState((prev) => ({
      ...prev,
      allCandidates: (prev.allCandidates || []).filter(s => s.site_iid !== siteIid),
    }));
    return data;
  }, [acssSessionId, projectName]);

  // ============ DEFINE GOAL ACTIONS ============
  
  // Snapshot of the last-saved goal (goalType + parameters) for dirty-checking
  const savedGoalSnapshotRef = useRef(null);

  // Update define goal state (without auto-calculating status)
  const updateDefineGoal = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      defineGoal: { ...prev.defineGoal, ...updates },
    }));
  }, []);

  // Mark define goal as done (called after successful API save)
  const markDefineGoalDone = useCallback(() => {
    setSetupState((prev) => {
      const next = { ...prev, defineGoal: { ...prev.defineGoal, status: 'done' } };
      // Capture saved snapshot after successful save
      savedGoalSnapshotRef.current = {
        goalType: next.defineGoal.goalType,
        parameters: { ...(next.defineGoal.parameters ?? {}) },
      };
      return next;
    });
  }, []);

  // Capture saved snapshot when goal is loaded from server as 'done'
  useEffect(() => {
    if (setupState.defineGoal?.status === 'done' && !savedGoalSnapshotRef.current) {
      savedGoalSnapshotRef.current = {
        goalType: setupState.defineGoal.goalType,
        parameters: { ...(setupState.defineGoal.parameters ?? {}) },
      };
    }
  }, [setupState.defineGoal]);

  // Check if goal form is valid and has unsaved changes
  // Validation: only non-select params must be filled
  // Dirty check: returns false if nothing changed vs saved snapshot
  const isGoalFormValid = useCallback(() => {
    const goal = setupState.defineGoal;
    if (!goal?.goalType) return false;
    const params = goal.parameters ?? {};
    const goalDef = goalOptions.find((g) => g.id === goal.goalType);
    if (!goalDef?.params?.length) return false;

    // Only validate non-select params (dropdowns always have a value).
    // Number fields must contain a complete, finite number; parseFloat is not
    // sufficient because it accepts values such as "123abc".
    for (const p of goalDef.params) {
      if (p.type === 'select') continue; // skip dropdown validation
      const v = params[p.id];
      if (v === undefined || v === null || v === '') return false;
      if (p.type === 'number') {
        if (typeof v === 'string' && v.trim() === '') return false;
        // Reject strings that Number() would partially accept (e.g. "12abc")
        if (typeof v === 'string' && !/^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(v.trim())) {
          return false;
        }
        const num = Number(v);
        if (!Number.isFinite(num)) return false;
        if (p.min != null && num < p.min) return false;
        if (p.max != null && num > p.max) return false;
      }
    }

    // Dirty check: disable save if nothing changed compared to last-saved snapshot
    const saved = savedGoalSnapshotRef.current;
    if (saved) {
      const sameGoalType = saved.goalType === goal.goalType;
      const sameParams = sameGoalType && goalDef.params.every(
        (p) => String(saved.parameters?.[p.id] ?? '') === String(params[p.id] ?? '')
      );
      if (sameGoalType && sameParams) return false; // nothing changed
    }

    return true;
  }, [setupState.defineGoal, goalOptions]);

  // Set goal type and reset parameters to defaults for that goal (so select params have a value)
  const setGoalType = useCallback((goalType) => {
    const goalDef = goalOptions.find((g) => g.id === goalType);
    const defaults = {};
    if (goalDef?.params) {
      for (const p of goalDef.params) {
        defaults[p.id] = p.type === 'select' && p.options?.length ? p.options[0] : '';
      }
    }
    updateDefineGoal({ goalType, parameters: defaults });
  }, [updateDefineGoal, goalOptions]);

  // Single updater for goal parameters (so new goals need no new code)
  const updateGoalParameters = useCallback((updates) => {
    setSetupState((prev) => ({
      ...prev,
      defineGoal: {
        ...prev.defineGoal,
        parameters: { ...(prev.defineGoal?.parameters ?? {}), ...updates },
      },
    }));
  }, []);

  // ============ EXECUTION STEP ACTIONS ============
  
  // Update an execution step's status and metadata
  const updateExecutionStep = useCallback((stepName, status, metadata = {}) => {
    setExecutionSteps((prevSteps) =>
      prevSteps.map((step) =>
        step.name === stepName
          ? { ...step, status, metadata: { ...step.metadata, ...metadata } }
          : step
      )
    );
    
    // Auto-advance currentExecutionStep if step is completed
    if (status === 'done') {
      const stepIndex = EXECUTION_STEP_DEFINITIONS.findIndex((s) => s.name === stepName);
      if (stepIndex < EXECUTION_STEP_DEFINITIONS.length - 1) {
        setCurrentExecutionStep(EXECUTION_STEP_DEFINITIONS[stepIndex + 1].name);
      }
    }
    
    // Set current step if starting
    if (status === 'running') {
      setCurrentExecutionStep(stepName);
    }
  }, []);

  // Get execution step by name
  const getExecutionStep = useCallback((stepName) => {
    return executionSteps.find((step) => step.name === stepName);
  }, [executionSteps]);
  
  // Start execution (begins with first step after setup is complete)
  const startExecution = useCallback(() => {
    if (!isSetupComplete) {
      console.warn('Cannot start execution: Setup is not complete');
      return false;
    }
    setCurrentExecutionStep(EXECUTION_STEP_DEFINITIONS[0].name);
    return true;
  }, [isSetupComplete]);



  // Track previous autoGenCandidates status to detect transition to done
  const prevAutoGenStatusRef = useRef(null);

  // Update execution steps from SSE data (backend state format)
  const updateExecutionFromSSE = useCallback((sseData) => {
    // Map backend state to frontend executionSteps array
    setExecutionSteps(prevSteps => 
      prevSteps.map(step => ({
        ...step,
        status: sseData[step.name]?.status || step.status,
        progress: sseData[step.name]?.progress || step.progress,
        startTime: sseData[step.name]?.startTime || step.startTime,
        endTime: sseData[step.name]?.endTime || step.endTime,
      }))
    );
    
    // Find and set current running step
    const runningStep = Object.entries(sseData).find(([key, value]) => value.status === 'running');
    if (runningStep) {
      setCurrentExecutionStep(runningStep[0]);
    }

    // When autoGenCandidates transitions to done, refresh setup_state
    // so allCandidates appear on the map immediately
    const autoGenStatus = sseData.autoGenCandidates?.status;
    if (autoGenStatus === 'done' && prevAutoGenStatusRef.current !== 'done') {
      if (acssSessionId && projectName) {
        sessionApi.createOrGetSession({
          acss_session_id: acssSessionId,
          project_name: projectName,
        }).then((resp) => {
          if (resp?.setup_state) {
            setSetupState(resp.setup_state);
          }
        }).catch((err) => {
          console.error('[ACSS] setup_state refresh after auto-gen done failed:', err);
        });
      }
    }
    prevAutoGenStatusRef.current = autoGenStatus;

    // Detect waiting_user (paused for candidate review)
    if (sseData.finalEvaluation?.status === 'waiting_user') {
      setNeedsReview(true);
      setExecutionStatus('waiting_user');
      setCurrentExecutionStep('finalEvaluation');
      return; // Don't check allDone when paused
    }

    // Clear needsReview if finalEvaluation moved past waiting_user
    if (sseData.finalEvaluation?.status === 'done' || sseData.finalEvaluation?.status === 'cancelled') {
      setNeedsReview(false);
    }
    
    // Check if all steps are done (skip autoGenCandidates if pending/disabled)
    const allDone = Object.entries(sseData).every(([key, step]) => {
      if (key === 'autoGenCandidates' && step.status === 'pending') return true;
      return step.status === 'done';
    });
    if (allDone) {
      setExecutionStatus('completed');
    }
  }, [acssSessionId, projectName]);

  // Toggle execution SSE listening
  const toggleExecutionListening = useCallback(() => {
    setIsExecutionListening(prev => !prev);
  }, []);

  // Update Celery status and stop listening when task finishes
  const updateCeleryStatus = useCallback((statusData) => {
    const errText = String(statusData?.error || '');
    // Legacy pause used HTTPException(499) which Celery reported as FAILURE.
    // Treat that as a graceful pause, not a hard error.
    const isPauseForReview =
      statusData?.status === 'FAILURE' &&
      errText.includes('Work Paused for user confirmation');

    const displayStatus = isPauseForReview
      ? { ...statusData, status: 'SUCCESS', error: null, message: 'Paused for candidate selection' }
      : statusData;

    setCeleryStatus(displayStatus);
    
    // Update execution status based on Celery task status
    if (isPauseForReview) {
      setExecutionStatus((prev) => (prev === 'waiting_user' ? 'waiting_user' : prev));
      setIsExecutionListening(false);
    } else if (statusData.status === 'FAILURE') {
      setExecutionStatus('error');
      setIsExecutionListening(false); // Stop SSE on failure
    } else if (statusData.status === 'SUCCESS') {
      // Don't overwrite waiting_user / cancelled with completed
      // (SUCCESS also covers a deliberate pause-for-review / skipped exit)
      setExecutionStatus((prev) => {
        if (prev === 'waiting_user' || prev === 'cancelled') return prev;
        if (statusData.paused) return 'waiting_user';
        if (statusData.skipped) return prev === 'running' ? 'cancelled' : prev;
        return 'completed';
      });
      setIsExecutionListening(false); // Stop SSE on success
    } else if (statusData.status === 'REVOKED') {
      setExecutionStatus('cancelled');
      setIsExecutionListening(false); // Stop SSE on cancel
    } else if (statusData.status === 'STARTED') {
      setExecutionStatus('running');
    }
  }, []);

  // ============ AUTO-REFRESH ON EXECUTION COMPLETE ============
  // When execution transitions to 'completed' (not on initial page load),
  // re-fetch the session so that saved_candidates (from step 7) become
  // available to the map without a manual page reload.
  const prevExecutionStatusRef = useRef(executionStatus);

  useEffect(() => {
    const prev = prevExecutionStatusRef.current;
    prevExecutionStatusRef.current = executionStatus;

    // Only refresh when execution just completed (transition from a running state)
    if (
      executionStatus === 'completed' &&
      prev !== 'completed' &&
      prev !== 'not started' &&
      acssSessionId &&
      projectName
    ) {
      const refreshSession = async () => {
        try {
          const sessionResponse = await sessionApi.createOrGetSession({
            acss_session_id: acssSessionId,
            project_name: projectName,
          });
          if (sessionResponse.setup_state) {
            setSetupState(sessionResponse.setup_state);
          }
        } catch (err) {
          console.error('[ACSS] Failed to refresh session after execution completed:', err);
        }
      };
      refreshSession();
    }
  }, [executionStatus, acssSessionId, projectName]);

  // ============ LOG ACTIONS ============
  
  // Log listening state
  const [isLogListening, setIsLogListening] = useState(true);
  
  // Add a log message with timestamp
  const addLog = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    setLogs((prevLogs) => {
      const newLog = `[${timestamp}] ${message}`;
      // Keep only latest 1000 logs
      const updatedLogs = [newLog, ...prevLogs];
      return updatedLogs.slice(0, 1000);
    });

    // Fallback log-based refresh for v1 autogen (primary refresh for v2 is
    // handled in updateExecutionFromSSE when autoGenCandidates transitions to done)
    if (typeof message === 'string' && (
      message.includes('Auto-gen complete:') || message.includes('[Step 9/9] Pipeline complete')
    )) {
      if (acssSessionId && projectName) {
        sessionApi.createOrGetSession({
          acss_session_id: acssSessionId,
          project_name: projectName,
        }).then((resp) => {
          if (resp?.setup_state) {
            setSetupState(resp.setup_state);
          }
        }).catch((err) => {
          console.error('[ACSS] mid-flight setup_state refresh after auto-gen failed:', err);
        });
      }
    }
  }, [acssSessionId, projectName]);

  // Clear all logs
  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  // Toggle log listening
  const toggleLogListening = useCallback(() => {
    setIsLogListening((prev) => !prev);
  }, []);

  // ============ FILE ACTIONS ============
  
  // Update files map
  const updateFiles = useCallback((fileMap) => {
    setFiles((prevFiles) => ({ ...prevFiles, ...fileMap }));
  }, []);

  const value = {
    // Session State
    acssSessionId,
    projectName,
    project_cords,
    
    // Setup State
    setupState,
    polygon: setupState.polygon,
    loadProject: setupState.loadProject,
    loadCandidateGdl: setupState.loadCandidateGdl,
    defineGoal: setupState.defineGoal,
    isSetupComplete,

    // Goals (from API)
    goalOptions,
    goalsLoading,
    goalsError,
    fetchGoals,
    
    // Execution State
    currentExecutionStep,
    executionSteps,
    executionStatus,
    jobId,
    isExecutionListening,
    celeryStatus,
    
    // Logs & Files
    logs,
    files,
    
    // Session Actions
    setAcssSessionId,
    setProjectName,
    setProject_cords,
    setSetupState,
    
    // Setup Actions (Polygon)
    updatePolygon,
    startPolygonDrawing,
    cancelPolygonDrawing,
    completePolygon,
    clearPolygon,
    setBoundaryRadius,
    
    // Setup Actions (Load Project)
    updateLoadProject,
    markProjectLoaded,
    
    // Setup Actions (Candidate GDL)
    updateCandidateGdl,
    markCandidateGdlDone,
    setCandidateGdlFile,
    clearCandidateGdlFile,

    // Setup Actions (Auto-Gen Config)
    setAutoGenConfigDraft,
    submitAutoGenConfig,
    deleteAutoGenCandidate,
    
    // Setup Actions (Define Goal)
    updateDefineGoal,
    markDefineGoalDone,
    isGoalFormValid,
    setGoalType,
    updateGoalParameters,
    
    // Execution Actions
    setCurrentExecutionStep,
    updateExecutionStep,
    getExecutionStep,
    startExecution,
    setExecutionStatus,
    setJobId,
    setExecutionSteps,
    updateExecutionFromSSE,
    toggleExecutionListening,
    setIsExecutionListening,
    updateCeleryStatus,
    setCeleryStatus,
    needsReview,
    setNeedsReview,
    reviewResults,
    setReviewResults,
    
    // Log & File Actions
    addLog,
    clearLogs,
    isLogListening,
    toggleLogListening,
    updateFiles,
    
    // Constants
    SETUP_DEFINITIONS,
    EXECUTION_STEP_DEFINITIONS,
  };

  return (
    <ACSSContext.Provider value={value}>
      {children}
    </ACSSContext.Provider>
  );
}

export function useACSSContext() {
  const context = useContext(ACSSContext);
  if (!context) {
    throw new Error('useACSSContext must be used within an ACSSProvider');
  }
  return context;
}

export { SETUP_DEFINITIONS, EXECUTION_STEP_DEFINITIONS };

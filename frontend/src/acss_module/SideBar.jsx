import React, { useRef } from 'react';
import { useACSSContext } from './context/ACSSContext';
import { setupApi, sessionApi } from './api/acssApi';
import { 
  Hexagon, 
  LineChart, 
  MapPin, 
  Play, 
  CheckCircle2, 
  Database,
  Circle,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  FileSpreadsheet,
  Target,
  Calculator,
  GitBranch,
  Activity,
  RefreshCw,
  Layers,
  FileImage,
  Home,
  Radio,
  Cpu,
  Sparkles,
} from 'lucide-react';

// Import Setup component and shared utilities
import { Setup, StatusIndicator, getStatusBadge, getStatusColor, getIconColor } from './components';
import ExecutionPanel from './components/ExecutionPanel';
import ResultsPanel from './components/ResultsPanel';

// Icon mapping for execution steps (keys match backend step names)
const EXECUTION_STEP_ICONS = {
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

function Sidebar({ isCollapsed, onToggleCollapse }) {
  const {
    acssSessionId,
    projectName,
    polygon,
    loadProject,
    loadCandidateGdl,
    defineGoal,
    isSetupComplete,
    goalOptions,
    goalsLoading,
    goalsError,
    executionSteps,
    currentExecutionStep,
    startPolygonDrawing,
    cancelPolygonDrawing,
    setBoundaryRadius,
    setCandidateGdlFile,
    clearCandidateGdlFile,
    setGoalType,
    updateGoalParameters,
    markDefineGoalDone,
    markCandidateGdlDone,
    isGoalFormValid,
    executionStatus,
    runExecution,
    addLog,
    setSetupState,
  } = useACSSContext();

  // File input ref for GDL upload
  const fileInputRef = useRef(null);

  // Get setup states directly
  const loadProjectStatus = loadProject?.status || 'pending';
  const isDrawingMode = polygon?.isDrawing || false;
  const boundaryRadius = polygon?.boundaryRadius || 5;
  const polygonStatus = polygon?.status || 'pending';
  const gdlStatus = loadCandidateGdl?.status || 'pending';
  const gdlFileName = loadCandidateGdl?.fileName || null;
  const goalStatus = defineGoal?.status || 'pending';
  const goalType = defineGoal?.goalType ?? 'increase_rsrp';
  const goalParameters = defineGoal?.parameters ?? {};

  // Toggle drawing mode for polygon
  const handleToggleDrawing = () => {
    if (isDrawingMode) {
      cancelPolygonDrawing();
    } else {
      startPolygonDrawing();
    }
  };

  // Handle boundary radius change
  const handleBoundaryRadiusChange = (e) => {
    const value = parseFloat(e.target.value) || 0;
    setBoundaryRadius(value);
  };

  // Handle file selection for Candidate GDL
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setCandidateGdlFile(file);
    }
  };

  // Handle file removal for Candidate GDL
  const handleFileRemove = () => {
    clearCandidateGdlFile();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle upload new GDL file
  const handleGdlFileUpload = async () => {
    const file = loadCandidateGdl?.file;
    if (!file) {
      addLog("Error: No file selected");
      return;
    }
    try {
      const response = await setupApi.uploadGdlFile(acssSessionId, projectName, file);
      markCandidateGdlDone();
      addLog(response.message);

      // Refresh session to pick up allCandidates built by the backend
      try {
        const sessionResponse = await sessionApi.createOrGetSession({
          acss_session_id: acssSessionId,
          project_name: projectName,
        });
        if (sessionResponse.setup_state) {
          setSetupState(sessionResponse.setup_state);
        }
      } catch (refreshErr) {
        console.error('[ACSS] Failed to refresh session after GDL upload:', refreshErr);
      }
    } catch (error) {
      addLog("Error uploading GDL file: " + error.message);
    }
  };

  // Handle save goal - sends goal_type + parameters (backend-agnostic)
  const handleSaveGoal = async () => {
    const gt = defineGoal?.goalType ?? 'increase_rsrp';
    const raw = defineGoal?.parameters ?? {};
    const goalDef = goalOptions?.find((g) => g.id === gt);
    const paramSpecs = goalDef?.params ?? [];
    const parameters = {};
    for (const p of paramSpecs) {
      let v = raw[p.id];
      if (p.type === 'number') v = v === '' || v == null ? null : parseFloat(v);
      else if (p.type === 'select') v = v != null ? Number(v) : (p.options?.[0] ?? null);
          else v = v ?? null;
      parameters[p.id] = v;
    }
    try {
      const response = await setupApi.putGoal(
        acssSessionId,
        { goal_type: gt, parameters },
        projectName
      );
      markDefineGoalDone();
      addLog(response.message);
    } catch (error) {
      addLog("Error saving goal: " + error.message);
    }
  };

  // Collapsed view render
  if (isCollapsed) {
    // Setup items for collapsed view
    const setupItems = [
      { name: 'loadProject', icon: FolderOpen, status: loadProjectStatus },
      { name: 'polygon', icon: Hexagon, status: polygonStatus },
      { name: 'loadCandidateGdl', icon: FileSpreadsheet, status: gdlStatus },
      { name: 'defineGoal', icon: Target, status: goalStatus },
    ];

    return (
      <div className="h-full flex flex-col items-center py-2">
        {/* Home Button */}
        <button
          onClick={() => window.location.href = '/'}
          className="p-1.5 rounded-lg bg-muted hover:bg-black dark:hover:bg-primary/40 transition-colors"
          title="Back to Home"
        >
          <Home className="w-4 h-4 text-muted-foreground" />
        </button>
        {/* Expand Button */}
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg bg-muted hover:bg-black dark:hover:bg-primary/40 transition-colors"
          title="Expand sidebar"
        >
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        </button>

        {/* Setup Step Indicators */}
        <div className="flex flex-col items-center gap-2 mb-3 pb-3 border-b border-border">
          <span className="text-[10px] font-medium text-amber-400 uppercase">Setup</span>
          {setupItems.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.name} className="flex flex-col items-center gap-1" title={item.name}>
                <div className={`
                  w-7 h-7 rounded-lg flex items-center justify-center
                  ${item.status === 'done' ? 'bg-green-500/20' : item.status === 'running' ? 'bg-amber-400/20' : 'bg-accent/50'}
                `}>
                  <Icon className={`w-3.5 h-3.5 ${getIconColor(item.status)}`} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Execution Steps */}
        <div className="flex flex-col items-center gap-2">
          {executionSteps.map((step, index) => {
            const Icon = EXECUTION_STEP_ICONS[step.name] || Circle;
            const statusColor = getIconColor(step.status);
            
            return (
              <div key={step.name} className="flex flex-col items-center gap-1" title={step.label}>
                <div className="relative">
                  <span className={`
                    absolute -top-1 -left-1 w-3.5 h-3.5 rounded-full bg-card border border-border 
                    flex items-center justify-center text-[8px] font-medium text-muted-foreground
                  `}>
                    {index + 1}
                  </span>
                  <div className={`
                    w-8 h-8 rounded-lg flex items-center justify-center
                    ${step.status === 'done' ? 'bg-green-500/20' : step.status === 'running' ? 'bg-amber-400/20' : 'bg-accent/50'}
                  `}>
                    <Icon className={`w-4 h-4 ${statusColor}`} />
                  </div>
                </div>
                {/* Status dot */}
                <div className={`w-1.5 h-1.5 rounded-full ${getStatusColor(step.status).split(' ')[1]}`} />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold bg-gradient-to-r from-foreground to-primary bg-clip-text text-transparent">
            ASP
          </h2>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => window.location.href = '/'}
              className="p-1.5 rounded-lg bg-muted hover:bg-black dark:hover:bg-primary/40 transition-colors"
              title="Back to Home"
            >
              <Home className="w-4 h-4 text-muted-foreground" />
            </button>
            <button
              onClick={onToggleCollapse}
              className="p-1.5 rounded-lg bg-muted hover:bg-black dark:hover:bg-primary/40 transition-colors"
              title="Collapse sidebar"
            >
              <ChevronLeft className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1 font-mono truncate" title={acssSessionId}>
          Session: {acssSessionId?.slice(0, 8)}...
        </p>

        {/* Session context — project, band, tech, array type */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2.5 pt-2.5 border-t border-border">
          <div className="flex items-center gap-1.5 min-w-0">
            <FolderOpen className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] text-muted-foreground">Project</span>
            <span className="text-[10px] text-foreground font-medium truncate ml-auto">{projectName || '—'}</span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0">
            <Radio className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] text-muted-foreground">Band</span>
            <span className="text-[10px] text-foreground font-medium truncate ml-auto">{polygon?.selectedBand || '—'}</span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0">
            <Cpu className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] text-muted-foreground">Tech</span>
            <span className={`text-[10px] font-medium truncate ml-auto ${
              polygon?.technology === 'FiveG' ? 'text-purple-400' : polygon?.technology === 'LTE' ? 'text-blue-400' : 'text-foreground'
            }`}>
              {polygon?.technology === 'FiveG' ? '5G' : polygon?.technology || '—'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0">
            <Layers className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] text-muted-foreground">Array</span>
            <span className="text-[10px] text-foreground font-medium truncate ml-auto">{polygon?.arrayType?.replace(/_/g, ' ') || '—'}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* ============ SETUP SECTION ============ */}
        <Setup
          isSetupComplete={isSetupComplete}
          executionStatus={executionStatus}
          runExecution={runExecution}
          loadProjectStatus={loadProjectStatus}
          projectName={projectName}
          polygonStatus={polygonStatus}
          isDrawingMode={isDrawingMode}
          boundaryRadius={boundaryRadius}
          handleToggleDrawing={handleToggleDrawing}
          handleBoundaryRadiusChange={handleBoundaryRadiusChange}
          gdlStatus={gdlStatus}
          gdlFileName={gdlFileName}
          fileInputRef={fileInputRef}
          handleFileSelect={handleFileSelect}
          handleFileRemove={handleFileRemove}
          handleGdlFileUpload={handleGdlFileUpload}
          goalStatus={goalStatus}
          goalOptions={goalOptions}
          goalType={goalType}
          onGoalTypeChange={setGoalType}
          goalParameters={goalParameters}
          onGoalParametersChange={updateGoalParameters}
          handleSaveGoal={handleSaveGoal}
          isGoalFormValid={isGoalFormValid()}
          goalsLoading={goalsLoading}
          goalsError={goalsError}
        />

        {/* ============ EXECUTION SECTION ============ */}
        <ExecutionPanel isSetupComplete={isSetupComplete} />

        {/* ============ RESULTS SECTION ============ */}
        <ResultsPanel />
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <div className="text-xs text-muted-foreground text-center">
          {isSetupComplete 
            ? `Execution: ${currentExecutionStep ? executionSteps.findIndex(s => s.name === currentExecutionStep) + 1 : 0} of ${executionSteps.length}`
            : 'Setup in progress...'
          }
        </div>
      </div>
    </div>
  );
}

export default Sidebar;

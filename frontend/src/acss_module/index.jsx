import React, { useEffect, useState, useCallback } from 'react';
import {
  Panel,
  Group,
  Separator,
} from 'react-resizable-panels';

import Sidebar from './SideBar';
import Console from './Console';
import MapView from './map/2d/MapView';
import 'ol/ol.css';
import { useACSSContext } from './context/ACSSContext';
import { useParams } from 'react-router-dom';
import { sessionApi, executionApi } from './api/acssApi';
import AcssLoading from './AcssLoading';
import AcssError from './AcssError';
import CandidateReviewModal from './components/CandidateReviewModal';


const SIDEBAR_COLLAPSE_THRESHOLD = 50;
const CONSOLE_COLLAPSE_THRESHOLD = 40;

// Resize handle component
function ResizeHandle({ direction = 'horizontal' }) {
  const isVertical = direction === 'vertical';
  
  return (
    <Separator
      className={`
        ${isVertical ? 'h-1 cursor-row-resize' : 'w-1 cursor-col-resize'}
        bg-secondary/50 hover:bg-primary/50 
        transition-colors duration-200
        flex items-center justify-center
      `}
    >
      <div
        className={`
          ${isVertical ? 'w-8 h-1 rounded-full' : 'h-8 w-1 rounded-full'}
          bg-border hover:bg-primary
          transition-colors duration-200
        `}
      />
    </Separator>
  );
}

function ACSSModule() {
  const { project_name, acss_session_id } = useParams();
  const { 
    setAcssSessionId, 
    setProjectName, 
    setProject_cords, 
    project_cords,
    addLog,
    markProjectLoaded,
    setSetupState,
    setJobId,
    setExecutionStatus,
    setIsExecutionListening,
    updateExecutionFromSSE,
    setNeedsReview,
    setReviewResults,
  } = useACSSContext();
  
  // Collapse states for sidebar and console
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isConsoleCollapsed, setIsConsoleCollapsed] = useState(true);
  const [isInitializing, setIsInitializing] = useState(false);
  const [initError, setInitError] = useState(null);

  // Initialize session and fetch project coordinates
  const initializeSession = useCallback(async () => {
    if (!project_name || !acss_session_id) {
      return;
    }

    setIsInitializing(true);
    setInitError(null);
    addLog(`Initializing ASP session for project: ${project_name}`);

    try {
      // Call create session API
      const sessionResponse = await sessionApi.createOrGetSession({
        acss_session_id: acss_session_id,
        project_name: project_name,
      });

      
      
      // Update frontend state with project coordinates from response
      if (sessionResponse.project_cords) {
        console.log(sessionResponse.project_cords)
        setProject_cords(sessionResponse.project_cords);
      }
      if (sessionResponse.setup_state) {
         console.log(sessionResponse.setup_state)
        setSetupState(sessionResponse.setup_state);
      }
      
      // Handle execution state restoration
      if (sessionResponse.job_id) {
        setJobId(sessionResponse.job_id);
        
        // Restore execution step states if available
        if (sessionResponse.execution_status_state && Object.keys(sessionResponse.execution_status_state).length > 0) {
          updateExecutionFromSSE(sessionResponse.execution_status_state);
        }
        
        const isTerminal = ['completed', 'failed', 'cancelled'].includes(sessionResponse.status);
        const finalEvalStatus = sessionResponse.execution_status_state?.finalEvaluation?.status;

        if (!isTerminal) {
          // Auto-connect execution SSE for any non-terminal session
          const isWaitingUser = finalEvalStatus === 'waiting_user';
          if (isWaitingUser) {
            setExecutionStatus('waiting_user');
            setNeedsReview(true);
          } else {
            setExecutionStatus('running');
          }
          setIsExecutionListening(true);
          addLog(`Reconnecting to execution job: ${sessionResponse.job_id.slice(0, 8)}...`);
        } else if (sessionResponse.status === 'completed') {
          setExecutionStatus('completed');
          addLog('Previous execution completed');
        } else if (sessionResponse.status === 'failed') {
          setExecutionStatus('error');
          addLog('Previous execution failed');
        }

        // Restore review results for sessions where finalEvaluation already ran
        // if (finalEvalStatus && finalEvalStatus !== 'pending' && finalEvalStatus !== 'running') {
        //   try {
        //     const reviewData = await executionApi.getReview(acss_session_id, project_name);
        //     setReviewResults(reviewData);
        //   } catch {
        //     // Review data may not exist yet — that's fine
        //   }
        // }
      }
      
      markProjectLoaded();
      addLog(`Project loaded successfully: ${project_name}`);
      
    } catch (error) {
      
      const errorMessage = error.message || 'Failed to initialize session';
      console.error('[ASP Module] Initialization error:', error);
      setInitError(errorMessage);
      addLog(`Error: ${errorMessage}`);
    } finally {
      setIsInitializing(false);
    }
  }, [project_name, acss_session_id, setProject_cords, addLog, markProjectLoaded]);



  useEffect(() => {
    setAcssSessionId(acss_session_id);
    setProjectName(project_name);

    if (project_name && acss_session_id) {
      initializeSession();
    }
  }, []);

  // Show loading state
  if (isInitializing) {
    return <AcssLoading message="Loading ASP [Automatic Site Placement]" />;
  }

  // Show error state
  if (initError) {
    return (
      <AcssError 
        message="Failed to initialize ASP session"
        error={initError}
        onRetry={initializeSession}
      />
    );
  }

  return (
    <div className="h-screen w-full bg-background text-foreground overflow-hidden">
      {/* Candidate review modal (shown when finalEvaluation pauses) */}
      <CandidateReviewModal />
      {/* Main vertical split: Content | Console */}
      <Group orientation="vertical" className="h-full">
        {/* Top section: Sidebar + Map */}
        <Panel defaultSize={275} minSize={200}>
          <Group orientation="horizontal" className="h-full">
            {/* Sidebar — Panel when expanded, fixed strip when collapsed */}
            
              <>
                <Panel
                 defaultSize={isSidebarCollapsed ? SIDEBAR_COLLAPSE_THRESHOLD : 200} 
                 minSize={isSidebarCollapsed?SIDEBAR_COLLAPSE_THRESHOLD:200} 
                 maxSize={isSidebarCollapsed ? SIDEBAR_COLLAPSE_THRESHOLD : 400}
                >
                  <div className="h-full bg-background border-r border-border/50 overflow-hidden">
                    <Sidebar
                      isCollapsed={isSidebarCollapsed}
                      onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                    />
                  </div>
                </Panel>
                <ResizeHandle direction="horizontal" />
              </>
            
{/* 
            {isSidebarCollapsed && (
              <div
                className="h-full bg-background border-r border-border/50 overflow-hidden"
                style={{ width: SIDEBAR_COLLAPSE_THRESHOLD, flexShrink: 0 }}
              >
                <Sidebar
                  isCollapsed={true}
                  onToggleCollapse={() => setIsSidebarCollapsed(false)}
                />
              </div>
            )} */}

            {/* Map Panel */}
            <Panel defaultSize="75%" minSize="40%">
              <div className="h-full bg-background overflow-hidden">
                <MapView />
              </div>
            </Panel>
          </Group>
        </Panel>

        <ResizeHandle direction="vertical" />

        {/* Console Panel — remount on collapse so defaultSize applies */}
        <Panel
          key={isConsoleCollapsed ? 'console-collapsed' : 'console-expanded'}
          defaultSize={isConsoleCollapsed ? CONSOLE_COLLAPSE_THRESHOLD : 200}
          minSize={isConsoleCollapsed ? CONSOLE_COLLAPSE_THRESHOLD : 10}
          maxSize={isConsoleCollapsed ? CONSOLE_COLLAPSE_THRESHOLD : 500}
        >
          <div className="h-full bg-card border-t border-border/50 overflow-hidden">
            <Console
              isCollapsed={isConsoleCollapsed}
              onToggleCollapse={() => setIsConsoleCollapsed((v) => !v)}
            />
          </div>
        </Panel>
      </Group>
    </div>
  );
}

export default ACSSModule;

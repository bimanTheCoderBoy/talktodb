import React, { useState, useCallback, useEffect, useRef } from "react";
import { Signal, ChevronDown, Radio, Settings2, Pencil, Check, X, Clock, Plus, Loader2, Trash2, ShieldCheck } from "lucide-react";
import { useProjectContext } from "@/context/ProjectContext";
import { useNavigate } from "react-router-dom";
import logoWhite from "@/asset/AIRCOM-White-logo.webp";
import SitesCellsList from "./SitesCellsList";
import ProjectConfigModal from "./project_config/ProjectConfigModal";
import AuditRulesModal from "./audit_rules/AuditRulesModal";
import { v4 as uuidv4 } from 'uuid';
import { sessionApi } from "@/acss_module/api/acssApi";
import { getThreads } from "@/api";

const TopBar = ({ currentThread, sidebarOpen, selectedAgent, setThreads, onRunCoverage }) => {
  const { projectName, setProjectName } = useProjectContext();
  const navigate = useNavigate();
  const [showCellSelector, setShowCellSelector] = useState(false);
  const [showProjectConfig, setShowProjectConfig] = useState(false);
  const [showAuditRules, setShowAuditRules] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [localName, setLocalName] = useState(projectName || '');

  const startEditing = useCallback(() => {
    setLocalName(projectName || '');
    setEditingName(true);
  }, [projectName]);

  const cancelEditing = useCallback(() => {
    setEditingName(false);
    setLocalName(projectName || '');
  }, [projectName]);

    const applyName = useCallback ( () => {
    const trimmed = localName.trim();
    if (!trimmed) return;
    setEditingName(false);
    if (trimmed !== projectName) {
      setProjectName(trimmed);
    }
  }, [localName, projectName, setProjectName, setThreads]);

  const projectNameDisplay = (
    <div className={`flex items-center gap-2 px-3 py-1 border border-primary/20 rounded ${sidebarOpen ? "bg-card/20" : "bg-secondary"}`}>
      {editingName ? (
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            value={localName}
            onChange={(e) => setLocalName(e.target.value)}
            onKeyDown={async (e) => {
              if (e.key === 'Enter') {
                applyName();
                const response = await getThreads(localName);
                setThreads(response.threads || []);
              }
              if (e.key === 'Escape') cancelEditing();
            }}
            autoFocus
            className="px-2 py-0.5 text-sm bg-secondary text-foreground rounded border border-primary/40 focus:outline-none focus:border-primary w-40"
            placeholder="Project name..."
          />
          <button
            onClick={async () => {
              applyName();
              const response = await getThreads(localName);
              setThreads(response.threads || []);
            }}
            disabled={!localName.trim() || localName.trim() === projectName}
            className="p-1.5 rounded-lg hover:bg-green-500/20 text-green-400 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
            title="Save"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={cancelEditing}
            className="p-0.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            title="Cancel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 cursor-pointer group" onClick={startEditing} title="Click to edit project name">
          <p className="text-sm text-foreground font-medium">
            {projectName || "No Project"}
          </p>
          <Pencil className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
        </div>
      )}
    </div>
  );

  const handleToggleCellSelector = () => {
    setShowCellSelector(prev => !prev);
  };

  const cellSelectorButton = (
    <button
      onClick={handleToggleCellSelector}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 z-50 ${
        showCellSelector 
          ? "bg-primary text-primary-foreground" 
          : "bg-secondary border border-border text-muted-foreground hover:bg-accent hover:border-primary/50"
      }`}
      title="Select Cells for Coverage"
    >
      <Signal className="w-4 h-4" />
      <span className="text-sm font-medium">Cells</span>
      <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${showCellSelector ? "rotate-180" : ""}`} />
    </button>
  );

  const auditRulesButton = (
    <button
      onClick={() => setShowAuditRules(true)}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200
        bg-secondary border border-border text-muted-foreground hover:bg-accent hover:border-primary/50"
      title="Configure Audit Rules"
    >
      <ShieldCheck className="w-4 h-4" />
      <span className="text-sm font-medium">Audit Rules</span>
    </button>
  );

  const projectConfigButton = (
    <button
      onClick={() => setShowProjectConfig(true)}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200
        bg-secondary border border-border text-muted-foreground hover:bg-accent hover:border-primary/50"
      title="View Project Config"
    >
      <Settings2 className="w-4 h-4" />
      <span className="text-sm font-medium">Project Config</span>
    </button>
  );

  // ASP session history dropdown
  const [showAspDropdown, setShowAspDropdown] = useState(false);
  const [aspSessions, setAspSessions] = useState([]);
  const [aspSessionsLoading, setAspSessionsLoading] = useState(false);
  const aspDropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (aspDropdownRef.current && !aspDropdownRef.current.contains(e.target)) {
        setShowAspDropdown(false);
      }
    };
    if (showAspDropdown) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showAspDropdown]);

  const fetchAspSessions = useCallback(async () => {
    if (!projectName) return;
    setAspSessionsLoading(true);
    try {
      const sessions = await sessionApi.listSessions(projectName);

      setAspSessions(sessions);
    } catch { setAspSessions([]); }
    finally { setAspSessionsLoading(false); }
  }, [projectName]);

  const handleDeleteSession = useCallback(async (e, sessionId) => {
    e.stopPropagation();
    if (!projectName) return;
    try {
      await sessionApi.deleteSession(sessionId, projectName);
      setAspSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      console.error('Failed to delete session:', err);
      window.alert(`Failed to delete session: ${err?.message || 'unknown error'}`);
    }
  }, [projectName]);

  const handleToggleAspDropdown = useCallback(() => {
    const next = !showAspDropdown;
    setShowAspDropdown(next);
    if (next) fetchAspSessions();
  }, [showAspDropdown, fetchAspSessions]);

  const STATUS_COLORS = {
    completed: 'text-green-400',
    in_progress: 'text-amber-400',
    pending: 'text-gray-400',
    failed: 'text-red-400',
    cancelled: 'text-orange-400',
  };

  const acssButton = (
    <div className="relative" ref={aspDropdownRef}>
      <div className="flex items-center">
        {/* Main button — new session */}
        <button
          onClick={() => {
            const acssSessionId = uuidv4();
            setShowAspDropdown(false);
            navigate(`/asp/${projectName}/${acssSessionId}`);
          }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-l-lg transition-all duration-200
            bg-primary text-primary-foreground
            hover:bg-primary/90
            shadow-lg shadow-primary/20 hover:shadow-primary/30"
          title="New ASP Session"
        >
          <Radio className="w-4 h-4" />
          <span className="text-sm font-medium">ASP</span>
        </button>
        {/* Dropdown toggle */}
        <button
          onClick={handleToggleAspDropdown}
          className="flex items-center px-1.5 py-1.5 rounded-r-lg border-l border-primary-foreground/20 transition-all duration-200
            bg-primary text-primary-foreground
            hover:bg-primary/90
            shadow-lg shadow-primary/20 hover:shadow-primary/30"
          title="Previous ASP Sessions"
        >
          <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${showAspDropdown ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Dropdown panel */}
      {showAspDropdown && (
        // <div className="absolute right-0 top-full mt-1 w-80 bg-slate-800 border border-slate-600/50 rounded-lg shadow-2xl shadow-black/50 z-[9999] overflow-hidden">
        <div className="absolute right-0 top-full mt-1 w-80 bg-popover border border-border rounded-lg shadow-2xl shadow-black/50 z-[9999] overflow-hidden">
          {/* Header */}
          {/* <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/50 bg-slate-900/50"> */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card/50">
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-primary" />
              {/* <span className="text-xs font-semibold text-white">Previous Sessions</span> */}
              <span className="text-xs font-semibold text-foreground">Previous Sessions</span>
            </div>
            <button
              onClick={() => {
                const acssSessionId = uuidv4();
                setShowAspDropdown(false);
                navigate(`/asp/${projectName}/${acssSessionId}`);
              }}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium
                bg-primary/20 text-primary hover:bg-primary/30 transition-colors"
            >
              <Plus className="w-3 h-3" />
              New
            </button>
          </div>

          {/* Session list */}
          <div className="max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-transparent">
            {aspSessionsLoading && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
                <span className="ml-2 text-xs text-muted-foreground">Loading...</span>
              </div>
            )}

            {!aspSessionsLoading && aspSessions.length === 0 && (
              <div className="py-4 text-center text-xs text-muted-foreground">No previous sessions for this project</div>
            )}

            {!aspSessionsLoading && aspSessions.map((session) => {
              const createdAt = session.created_at ? new Date(session.created_at) : null;
              const timeStr = createdAt ? createdAt.toLocaleString('en-GB', {
                day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
              }) : '—';
              const statusColor = STATUS_COLORS[session.status] || 'text-gray-400';

              return (
                <div
                  key={session.id}
                  // className="flex items-center hover:bg-slate-700/50 border-b border-slate-700/30 last:border-b-0 transition-colors"
                  className="flex items-center hover:bg-secondary border-b border-border/30 last:border-b-0 transition-colors"
                >
                  <button
                    onClick={() => {
                      setShowAspDropdown(false);
                      navigate(`/asp/${session.project_name}/${session.id}`);
                    }}
                    className="flex-1 text-left px-3 py-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-muted-foreground">{String(session.id).slice(0, 8)}...</span>
                      <span className={`text-[10px] font-medium capitalize ${statusColor}`}>{session.status}</span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className="text-[10px] text-muted-foreground">{timeStr}</span>
                      {session.execution_status_state && (() => {
                        const steps = Object.values(session.execution_status_state);
                        const done = steps.filter((s) => s.status === 'done').length;
                        return done > 0 ? (
                          <span className="text-[10px] text-muted-foreground">{done}/{steps.length} steps</span>
                        ) : null;
                      })()}
                    </div>
                  </button>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="px-2 py-2 text-muted-foreground hover:text-red-400 transition-colors"
                    title="Delete session"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      <div className="flex flex-col">
        <div
          className={`flex w-full justify-between items-center mb-4 py-2 px-6 border-b transition-all duration-200 ${
            sidebarOpen
              ? "border-primary/20 bg-transparent"
              : "border-border bg-card"
          }`}
        >
          {sidebarOpen ? (
            <>
              <div>
                <p className="text-sm text-primary font-medium">Chat</p>
                <p className="text-xs text-muted-foreground mt-1 truncate max-w-xs" title={currentThread?.metadata?.thread_title || "New Chat"}>
                  {currentThread?.metadata?.thread_title || "New Chat"}
                </p>
              </div>
              <div className="flex-1 flex justify-end items-center gap-4">
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <span className="text-sm text-foreground font-medium whitespace-nowrap">Project :</span>
                  {projectNameDisplay}
                </div>
                {projectConfigButton}
                {/* Hidden until next release: Audit Rules for db_agent
                {selectedAgent === "db_agent" && auditRulesButton}
                */}
                {selectedAgent === "agent" && cellSelectorButton}
                {acssButton}
              </div>
            </>
          ) : (
            <>
              <div className="flex-shrink-0 ml-6">
                <p className="text-sm text-primary font-medium">Chat</p>
                <p className="text-xs text-muted-foreground mt-1 truncate max-w-xs" title={currentThread?.metadata?.thread_title || "New Chat"}>
                  {currentThread?.metadata?.thread_title || "New Chat"}
                </p>
              </div>
              <div className="flex-1 flex justify-center items-center">
                <img
                  src={logoWhite}
                  alt="TEOCO Logo"
                  // className="h-8 w-auto object-contain"
                  className="h-8 w-auto object-contain dark:invert-0 invert"
                />
              </div>
              <div className="flex-shrink-0 flex justify-end items-center gap-4">
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <span className="text-sm text-foreground font-medium whitespace-nowrap">Project :</span>
                  {projectNameDisplay}
                </div>
                {projectConfigButton}
                {/* Hidden until next release — uncomment to restore Audit Rules for db_agent */}
                {/* {selectedAgent === "db_agent" && auditRulesButton} */}
                {selectedAgent === "agent" && cellSelectorButton}
                {acssButton}
              </div>
            </>
          )}
        </div>
      </div>

      {selectedAgent === "agent" && showCellSelector && (
        <SitesCellsList 
          onClose={() => setShowCellSelector(false)}
          onRunCoverage={(cellIds) => {
            onRunCoverage?.(cellIds);
            setShowCellSelector(false);
          }}
        />
      )}

      {/* Read-only Project Config Modal */}
      <ProjectConfigModal
        isOpen={showProjectConfig}
        onClose={() => setShowProjectConfig(false)}
        projectName={projectName}
        readOnly={true}
      />

      <AuditRulesModal
        isOpen={showAuditRules}
        onClose={() => setShowAuditRules(false)}
        projectName={projectName}
      />
    </>
  );
};

export default TopBar;

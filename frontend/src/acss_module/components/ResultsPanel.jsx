import React, { useState } from 'react';
import { useACSSContext } from '../context/ACSSContext';
import {
  BarChart3, ChevronDown, ChevronUp, Star, Check,
  Copy, FolderOpen, Trophy, Users, X,
} from 'lucide-react';

const REPORT_PATH_KEYS = new Set(['Report Directory', 'Report PNG', 'Report Stats']);

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

function detectGoalType(details) {
  if (!details) return null;
  if ('X Value (%)' in details || 'Goal Satisfied' in details || 'Avg Absolute Gain (dB)' in details) return 'goal1';
  if ('Threshold (dBm)' in details || '% Meets Threshold (Best)' in details || 'Meets Threshold (All)' in details) return 'goal2';
  return null;
}

function formatDetailValue(val) {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toFixed(4);
  }
  return String(val);
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  };
  return (
    <button onClick={handleCopy} title="Copy path" className="ml-1 p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0">
      {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
    </button>
  );
}

function CandidateCard({ candidate, isSelected, defaultExpanded }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const sites = candidate.candidate_name.split('|');
  const details = candidate.result_details || {};
  const goalType = detectGoalType(details);
  const orderedKeys = goalType === 'goal1' ? GOAL1_KEYS : goalType === 'goal2' ? GOAL2_KEYS : null;

  let kpiEntries;
  if (orderedKeys) {
    const shown = new Set(orderedKeys);
    const ordered = orderedKeys.filter((k) => k in details).map((k) => [k, details[k]]);
    const extras = Object.entries(details).filter(([k]) => !shown.has(k) && !REPORT_PATH_KEYS.has(k));
    kpiEntries = [...ordered, ...extras];
  } else {
    kpiEntries = Object.entries(details).filter(([k]) => !REPORT_PATH_KEYS.has(k));
  }

  const reportEntries = Object.entries(details).filter(([k]) => REPORT_PATH_KEYS.has(k) && details[k]);
  const sectionLabel = goalType === 'goal1' ? 'Signal Gain' : goalType === 'goal2' ? 'Threshold Compliance' : 'Stats';

  return (
    <div className={`rounded-lg border transition-all ${
      isSelected
        ? 'bg-primary/20 border-primary ring-1 ring-primary/60 shadow-md shadow-primary/20'
        : 'bg-card border-border opacity-80'
    }`}>
      {/* Card header - always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-2.5 flex items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2 min-w-0">
          {isSelected && <Trophy className="w-3.5 h-3.5 text-sky-300 shrink-0" />}
          <span className={`text-xs font-medium truncate ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>
            {sites.length} site{sites.length > 1 ? 's' : ''}
          </span>
          {candidate.is_tied && (
            <span className="flex items-center gap-0.5 px-1 py-0.5 text-[9px] font-medium rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
              <Star className="w-2.5 h-2.5" />
              Best
            </span>
          )}
          <span className={`px-1.5 py-0.5 text-[10px] font-mono rounded-full shrink-0 ${
            isSelected ? 'bg-sky-400/20 text-sky-300' : 'bg-secondary text-muted-foreground'
          }`}>
            {candidate.goal_value?.toFixed(4)}
          </span>
        </div>
        {expanded ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-2">
          {/* Site tags */}
          <div className="flex flex-wrap gap-1">
            {sites.map((site) => (
              <span
                key={site}
                className={`px-1.5 py-0.5 text-[9px] font-mono rounded ${
                  isSelected ? 'bg-secondary text-foreground' : 'bg-secondary text-muted-foreground'
                }`}
              >
                {site}
              </span>
            ))}
          </div>

          {/* KPI grid */}
          {kpiEntries.length > 0 && (
            <div className={`pt-1.5 border-t ${isSelected ? 'border-primary/30' : 'border-border'}`}>
              <p className={`text-[9px] font-medium mb-1 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{sectionLabel}</p>
              <div className="grid grid-cols-1 gap-y-0.5">
                {kpiEntries.map(([label, value]) => (
                  <div key={label} className="flex justify-between text-[9px]">
                    <span className={`truncate mr-2 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</span>
                    <span className={`font-mono shrink-0 ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{formatDetailValue(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Report paths */}
          {reportEntries.length > 0 && (
            <div className="pt-1.5 border-t border-border">
              <div className="flex items-center gap-1 text-[9px] text-muted-foreground mb-1">
                <FolderOpen className="w-3 h-3" />
                <span>Report Files</span>
              </div>
              {reportEntries.map(([label, path]) => (
                <div key={label} className="flex items-center text-[9px] gap-1">
                  <span className="text-muted-foreground shrink-0">{label}:</span>
                  <span className="font-mono text-muted-foreground truncate flex-1 select-all" title={path}>{path}</span>
                  <CopyBtn text={path} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultsPanel() {
  const { reviewResults, executionStatus } = useACSSContext();
  const [collapsed, setCollapsed] = useState(false);

  if (!reviewResults) return null;

  const candidates = reviewResults.all_candidates || [];
  const selection = reviewResults.selection || {};
  const selectedNames = new Set(selection.selected_candidate_names || []);
  const hasSelection = selectedNames.size > 0;

  // Separate selected and other candidates
  const selectedCandidates = candidates.filter((c) => selectedNames.has(c.candidate_name));
  const otherCandidates = candidates.filter((c) => !selectedNames.has(c.candidate_name));

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Results</span>
        </div>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="px-2 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 transition-colors bg-secondary text-muted-foreground hover:text-foreground"
        >
          {collapsed ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronUp className="w-2.5 h-2.5" />}
          {collapsed ? 'Show' : 'Hide'}
        </button>
      </div>

      {!collapsed && (
        <div className="space-y-2">
          {/* Summary stats */}
          <div className="p-2.5 rounded-lg bg-secondary border border-border">
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>Max Goal Value</span>
              <span className="text-primary font-mono font-medium">
                {reviewResults.max_goal_value?.toFixed(4) ?? 'N/A'}
              </span>
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
              <span>Total Evaluated</span>
              <span className="font-mono text-foreground">{reviewResults.total_evaluated ?? 0}</span>
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
              <span>Best (Tied)</span>
              <span className="font-mono text-foreground">{candidates.filter((c) => c.is_tied).length}</span>
            </div>
            {hasSelection && (
              <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                <span>Selected</span>
                <span className="font-mono text-emerald-400">{selectedNames.size} candidate{selectedNames.size > 1 ? 's' : ''}</span>
              </div>
            )}
            {selection.status === 'confirmed' && (
              <div className="mt-1.5 px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-[9px] text-emerald-400 text-center">
                Selection Confirmed
              </div>
            )}
            {executionStatus === 'completed' && !hasSelection && (
              <div className="mt-1.5 px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20 text-[9px] text-orange-400 text-center">
                Closed Without Selection
              </div>
            )}
          </div>

          {/* Selected candidates */}
          {selectedCandidates.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 px-1">
                <Trophy className="w-3 h-3 text-primary" />
                <span className="text-[10px] font-medium text-primary">Selected Candidates</span>
              </div>
              {selectedCandidates.map((c) => (
                <CandidateCard key={c.candidate_name} candidate={c} isSelected={true} defaultExpanded={true} />
              ))}
            </div>
          )}

          {/* Other candidates */}
          {otherCandidates.length > 0 && (
            <OtherCandidatesSection candidates={otherCandidates} />
          )}
        </div>
      )}
    </div>
  );
}

function OtherCandidatesSection({ candidates }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 px-1 py-1 w-full text-left"
      >
        <Users className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] font-medium text-muted-foreground">
          Other Candidates ({candidates.length})
        </span>
        {expanded ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
      </button>
      {expanded && (
        <div className="space-y-1.5 mt-1">
          {candidates.map((c) => (
            <CandidateCard key={c.candidate_name} candidate={c} isSelected={false} defaultExpanded={false} />
          ))}
        </div>
      )}
    </div>
  );
}

export default ResultsPanel;

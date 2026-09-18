import React, { useState } from 'react';
import { FileSpreadsheet, Upload, Trash2 } from 'lucide-react';
import StatusIndicator from './StatusIndicator';
import LoadingButton from '../../LoadingButton';
import AutoGenPanel from './AutoGenPanel';
import { useACSSContext } from '../../context/ACSSContext';

function LoadCandidateGdlStep({
  status,
  fileName,
  fileInputRef,
  onFileSelect,
  onFileRemove,
  onUpload,
  isLocked = false,
  showAutoGenOption = false,
}) {
  const { loadCandidateGdl } = useACSSContext();
  const [mode, setMode] = useState(() => {
    if (showAutoGenOption) return 'autogen';
    return 'upload';
  });

  return (
    <div className={`
      relative p-3 rounded-lg transition-all duration-200
      ${status === 'done'
        ? 'bg-card/30 border border-transparent'
        : 'bg-muted/50 border border-border dark:bg-amber-500/10 dark:border-amber-500/30'
      }
    `}>
      <div className="flex items-center gap-3">
        <div className={`
          p-2 rounded-lg
          ${status === 'done' ? 'bg-green-500/20' : 'bg-muted dark:bg-amber-500/20'}
        `}>
          <FileSpreadsheet className={`w-4 h-4 ${status === 'done' ? 'text-green-400' : 'text-muted-foreground dark:text-amber-400'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground">Load Candidate GDL</span>
            <StatusIndicator status={status} />
          </div>

          {/* Mode toggle */}
          {showAutoGenOption && !isLocked && (
            <div className="flex mt-2 rounded-md overflow-hidden border border-border w-fit">
              <button
                onClick={() => setMode('upload')}
                className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  mode === 'upload'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-muted-foreground hover:text-foreground'
                }`}
              >
                Upload GDL
              </button>
              <button
                onClick={() => setMode('autogen')}
                className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-border ${
                  mode === 'autogen'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card text-muted-foreground hover:text-foreground'
                }`}
              >
                Auto-generate
              </button>
            </div>
          )}

          {/* Auto-generate mode */}
          {showAutoGenOption && mode === 'autogen' ? (
            <AutoGenPanel isLocked={isLocked} />
          ) : isLocked ? (
            <div className="mt-1">
              {fileName && (
                <span className="text-[10px] text-muted-foreground truncate block" title={fileName}>
                  {fileName}
                </span>
              )}
              {loadCandidateGdl?.autoGenConfig && (
                <span className="text-[10px] text-muted-foreground block">
                  Auto-gen: N={loadCandidateGdl.autoGenConfig.n}, threshold={loadCandidateGdl.autoGenConfig.threshold_dbm} dBm
                </span>
              )}
            </div>
          ) : fileName ? (
            <div className="mt-2 flex justify-between gap-2">
              <div>
                <LoadingButton
                  name="Upload Selected File"
                  onClick={onUpload}
                  icon={Upload}
                  variant="primary"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground truncate flex-1" title={fileName}>
                  {fileName}
                </span>
                <button
                  onClick={onFileRemove}
                  className="p-1 rounded hover:bg-red-500/20 transition-colors"
                  title="Remove file"
                >
                  <Trash2 className="w-3 h-3 text-red-400" />
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={onFileSelect}
                className="hidden"
                id="gdl-file-input"
              />
              <label
                htmlFor="gdl-file-input"
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5
                  rounded-lg font-medium text-xs transition-all duration-200
                  bg-primary hover:bg-primary/90 text-primary-foreground cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5" />
                Select CSV/Excel File
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LoadCandidateGdlStep;

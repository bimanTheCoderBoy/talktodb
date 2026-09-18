import React from 'react';
import { FolderOpen } from 'lucide-react';
import StatusIndicator, { getStatusBadge } from './StatusIndicator';

function LoadProjectStep({ status, projectName }) {
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
          <FolderOpen className={`w-4 h-4 ${status === 'done' ? 'text-green-400' : 'text-muted-foreground dark:text-amber-400'}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground">Load Project</span>
            <StatusIndicator status={status} />
          </div>
          <div className="mt-1">
            {status === 'done' ? (
              <span className="text-[10px] text-muted-foreground truncate block" title={projectName}>
                {projectName || 'Project loaded'}
              </span>
            ) : (
              <span className={`
                inline-flex items-center px-2 py-0.5 text-[10px] font-medium 
                rounded-full border capitalize
                ${getStatusBadge(status)}
              `}>
                Loading...
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoadProjectStep;

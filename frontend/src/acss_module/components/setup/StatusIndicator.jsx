import React from 'react';
import { Loader2, CheckCircle2, AlertCircle, Circle } from 'lucide-react';

// Status indicator component
function StatusIndicator({ status }) {
  switch (status) {
    case 'running':
      return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
    case 'done':
      return <CheckCircle2 className="w-4 h-4 text-green-500" />;
    case 'error':
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    case 'pending':
    default:
      return <Circle className="w-4 h-4 text-muted-foreground" />;
  }
}

// Get status badge styling
export function getStatusBadge(status) {
  switch (status) {
    case 'running':
      return 'bg-primary/20 text-primary border-primary/30';
    case 'done':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'error':
      return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'pending':
    default:
      return 'bg-secondary/50 text-muted-foreground border-border';
  }
}

// Get status color for collapsed view
export function getStatusColor(status) {
  switch (status) {
    case 'running':
      return 'text-muted-foreground bg-muted-foreground dark:text-amber-400 dark:bg-amber-400';
    case 'done':
      return 'text-green-500 bg-green-500';
    case 'error':
      return 'text-red-500 bg-red-500';
    case 'pending':
    default:
      return 'text-muted-foreground bg-muted-foreground';
  }
}

// Get icon color for collapsed view
export function getIconColor(status) {
  switch (status) {
    case 'running':
      return 'text-muted-foreground dark:text-amber-400';
    case 'done':
      return 'text-green-500';
    case 'error':
      return 'text-red-500';
    case 'pending':
    default:
      return 'text-muted-foreground';
  }
}

export default StatusIndicator;

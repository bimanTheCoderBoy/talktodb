import React, { useRef, useEffect } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import keycloak from '../keycloak';
import { useACSSContext } from './context/ACSSContext';
import { Terminal, ChevronUp, ChevronDown, Play, Square } from 'lucide-react';

function Console({ isCollapsed, onToggleCollapse }) {
  const { logs, addLog, clearLogs, isLogListening, toggleLogListening, acssSessionId } = useACSSContext();
  const scrollContainerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const connectLogSSE = () => {
      if (!isLogListening || !acssSessionId) return;

      const LOG_URL = `${import.meta.env.VITE_ACSS_API_URL}/api/v1/redis/logs/${acssSessionId}`;
      const ctrl = new AbortController();
      abortControllerRef.current = ctrl;

      fetchEventSource(LOG_URL, {
        signal: ctrl.signal,
        headers: {
          Authorization: `Bearer ${keycloak.token}`,
        },
        onmessage(event) {
          addLog(event.data);
        },
        onerror() {
          console.warn('[Log SSE] Connection error — will auto-reconnect in 3s');
          reconnectTimerRef.current = setTimeout(connectLogSSE, 3000);
        },
        openWhenHidden: true,
      });
    };

    connectLogSSE();

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
  }, [isLogListening, acssSessionId, addLog]);

  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [logs]);

  // Add initial log on mount
  useEffect(() => {
    addLog('ASP Module initialized');
  }, []);

  // Parse log to extract timestamp and message
  const parseLog = (log) => {
    const match = log.match(/^\[(\d{2}:\d{2}:\d{2})\]\s(.*)$/);
    if (match) {
      return { timestamp: match[1], message: match[2] };
    }
    return { timestamp: '', message: log };
  };

  // Collapsed view - only show header
  if (isCollapsed) {
    return (
      <div className="h-full flex items-center justify-between px-4 py-2 bg-card/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-muted-foreground">Console</span>
          {isLogListening && (
            <span className="px-1.5 py-0.5 text-[10px] bg-secondary/50 text-muted-foreground rounded-full">
              {logs.length} logs
            </span>
          )}
        </div>

        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg bg-secondary/50 hover:bg-accent transition-colors"
          title="Expand console"
        >
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Console Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-muted-foreground">Console</span>
          {isLogListening && (
            <span className="px-1.5 py-0.5 text-[10px] bg-secondary/50 text-muted-foreground rounded-full">
              {logs.length} logs
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle listening button */}
          <button
            onClick={toggleLogListening}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${isLogListening
              ? 'bg-green-600/20 text-green-700 dark:text-green-400 hover:bg-green-600/30'
              : 'bg-secondary/50 text-muted-foreground hover:bg-accent'
              }`}
            title={isLogListening ? 'Stop listening' : 'Start listening'}
          >
            {isLogListening ? (
              <>
                <Square className="w-3 h-3" />
                <span>Running</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3" />
                <span>Start</span>
              </>
            )}
          </button>

          {/* Clear logs button */}
          <button
            onClick={clearLogs}
            className="px-2 py-1 rounded-lg text-xs font-medium bg-secondary/50 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            title="Clear logs"
          >
            Clear
          </button>

          {/* Collapse button */}
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg bg-secondary/50 hover:bg-accent transition-colors"
            title="Collapse console"
          >
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Log Messages */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-3 font-mono text-xs"
        style={{ backgroundColor: 'var(--card)' }}
      >
        {!isLogListening ? (
          <div className="text-muted-foreground text-center py-4">
            Log listening paused. Click "Start" to resume.
          </div>
        ) : logs.length === 0 ? (
          <div className="text-muted-foreground text-center py-4">
            No logs yet...
          </div>
        ) : (
          <div className="space-y-1">
            {/* Display logs in reverse order (newest at bottom for auto-scroll) */}
            {[...logs].reverse().map((log, index) => {
              const { timestamp, message } = parseLog(log);
              return (
                <div
                  key={`${timestamp}-${index}`}
                  className="flex gap-2 hover:bg-card/30 px-2 py-0.5 rounded"
                >
                  <span className="text-muted-foreground shrink-0">
                    [{timestamp}]
                  </span>
                  <span className="text-muted-foreground break-all">
                    {message}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="px-4 py-1.5 border-t border-border bg-card/20 text-[10px] text-muted-foreground flex items-center justify-between">
        <span>Max 1000 lines</span>
        <span>{isLogListening ? 'Listening...' : 'Paused'}</span>
      </div>
    </div>
  );
}

export default Console;

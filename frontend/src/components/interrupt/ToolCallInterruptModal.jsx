import React, { useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Hammer, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";

/**  This page will chnage or removed in future , this is only for demo testing*/ 
const STUB_NOT_BUILT_MESSAGE =
  "Connector and frontend execution not built yet.";

/** JSON resume payload until real client-side tool execution exists. */
export function toolCallInterruptStubResume() {
  return JSON.stringify({
    success: false,
    error: STUB_NOT_BUILT_MESSAGE,
  });
}

function formatToolCallContent(content) {
  if (content == null) return "";
  if (typeof content === "object") {
    return JSON.stringify(content, null, 2);
  }
  const raw = String(content);
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export default function ToolCallInterruptModal({
  open,
  content,
  isLoading = false,
  onUnderstood,
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const formattedContent = useMemo(() => formatToolCallContent(content), [content]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tool-call-interrupt-title"
    >
      <div
        className="absolute inset-0 bg-black/45 dark:bg-black/60 backdrop-blur-[2px]"
        aria-hidden
      />

      <div className="relative w-full max-w-md rounded-2xl border border-border bg-popover shadow-2xl shadow-black/30 overflow-hidden">
        <div className="flex items-start gap-3 px-4 pt-4 pb-2 border-b border-border/80 bg-secondary/40">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/15 ring-1 ring-primary/25">
            <Wrench className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <h2
              id="tool-call-interrupt-title"
              className="text-sm font-semibold text-foreground"
            >
              Frontend tool requested
            </h2>
            <p className="mt-1 text-xs text-muted-foreground leading-snug">
              The agent paused to run a client-side tool.
            </p>
          </div>
        </div>

        <div className="px-4 py-3 space-y-3">
          <pre className="max-h-[220px] overflow-auto rounded-lg border border-border bg-muted/50 p-3 text-xs text-foreground font-mono whitespace-pre-wrap wrap-break-word">
            {formattedContent || "(no payload)"}
          </pre>

          <div className="flex gap-2 rounded-lg border border-amber-500/35 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-950 dark:text-amber-100">
            <Hammer className="h-4 w-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
            <p>
              <span className="font-semibold">NOTE:</span> connector and frontend execution not built yet.
            </p>
          </div>
        </div>

        <div className="px-4 pb-4 flex justify-end">
          <Button
            type="button"
            disabled={isLoading}
            onClick={() => onUnderstood?.()}
            className="min-w-[7rem]"
          >
            Understood
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}

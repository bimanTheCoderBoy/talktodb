import React from "react";
import { LazyMDResponse } from "@/components/ui/shadcn-io/ai/lazy-md-response";
import { Button } from "@/components/ui/button";
import { CircleHelp, ShieldCheck, ShieldX } from "lucide-react";
import { trimLargeTables } from "@/services/downloadService.js";

const HUMAN_INTERRUPT_TYPES = ["ASK_HUMAN", "ASK_HUMAN_BINARY"];

function stringifyInterruptContent(content) {
  return typeof content === "string" ? content : JSON.stringify(content, null, 2);
}

export default function InterruptCard({
  type,
  content,
  isLoading = false,
  onApprove,
  onDeny,
}) {
  if (!HUMAN_INTERRUPT_TYPES.includes(type)) {
    return null;
  }

  const formattedContent = stringifyInterruptContent(content);
  const trimmedContent = trimLargeTables(formattedContent,200);
  const isBinaryPrompt = type === "ASK_HUMAN_BINARY";
  const promptTitle = isBinaryPrompt ? "Approval Required" : "Agent Asking You";

  return (
    <div className="relative max-h-[500px] overflow-y-scroll rounded-xl border border-gray-300 dark:border-teoco-real-blue/30 bg-gray-100 dark:bg-teoco-navy-blue/40 p-4 shadow-lg shadow-black/5 dark:shadow-black/20">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-gray-200/50 dark:from-teoco-real-blue/10 via-transparent to-transparent" />
      <div className="relative flex items-start gap-3 min-w-0">
        <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-200 dark:bg-teoco-real-blue/20 ring-1 ring-gray-300 dark:ring-teoco-real-blue/30">
          {isBinaryPrompt ? (
            <ShieldCheck className="h-4 w-4 text-gray-600 dark:text-teoco-real-blue" />
          ) : (
            <CircleHelp className="h-4 w-4 text-gray-600 dark:text-teoco-real-blue" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-foreground">
              {promptTitle}
            </div>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              interrupt
            </div>
          </div>

          <div className="mt-2 rounded-lg border border-gray-200 dark:border-blue-500/20 bg-gray-50 dark:bg-secondary/20 p-3">
            <LazyMDResponse className="wrap-anywhere">{trimmedContent}</LazyMDResponse>
          </div>

      {isBinaryPrompt && (
        <div className="mt-3 flex items-center justify-end gap-2">
          <Button
            type="button"
            onClick={() => onApprove?.()}
            disabled={isLoading}
            className="bg-emerald-500 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
          >
            <ShieldCheck className="mr-2 h-4 w-4" />
            Approve
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => onDeny?.()}
            disabled={isLoading}
            className="border-red-500/80 text-red-600 dark:text-red-400 hover:bg-red-500/10 hover:text-red-500 dark:hover:text-red-700"
          >
            <ShieldX className="mr-2 h-4 w-4" />
            Deny
          </Button>
        </div>
      )}
        </div>
      </div>
    </div>
  );
}

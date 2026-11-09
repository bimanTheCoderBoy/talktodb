import { useCallback, useEffect, useRef, useState } from "react";
import { getFrontendTool } from "./registry.js";
import { parseToolCallInterruptContent } from "./parseInterruptPayload.js";

function errorMessage(err) {
  return err instanceof Error ? err.message : String(err);
}

function isAbortError(err) {
  return (
    (err instanceof Error && err.name === "AbortError") ||
    (err instanceof DOMException && err.name === "AbortError")
  );
}

/**
 * Handles LangGraph tool_call interrupts via Frontend ToolCalls (no server resume on failure).
 * Call `runEngine(interrupt)` when the stream reports a tool_call interrupt.
 */
export function useFrontendToolCallInterrupt({
  submit,
  setToolProgress,
  setStreamErrorText,
  streamContext,
  stopSignal,
}) {
  const [isFrontendExecuting, setIsFrontendExecuting] = useState(false);
  const activeRunRef = useRef(null);

  useEffect(() => {
    if (!stopSignal) {
      return;
    }
    activeRunRef.current?.abort();
    activeRunRef.current = null;
    setIsFrontendExecuting(false);
    setToolProgress(null);
  }, [stopSignal, setToolProgress]);

  const runEngine = useCallback(
    async (interrupt) => {
      if (interrupt?.value?.type !== "tool_call" || interrupt?.value == null) {
        setStreamErrorText("Interrupt type is not tool_call.");
        return;
      }
      if (!streamContext?.thread_id || !submit) {
        return;
      }

      let cancelled = false;
      const abortController = new AbortController();
      const runControl = {
        abort() {
          cancelled = true;
          abortController.abort();
        },
      };
      activeRunRef.current = runControl;

      setIsFrontendExecuting(true);
      setStreamErrorText("");

      try {
        let payload;
        try {
          payload = parseToolCallInterruptContent(interrupt.value.content);
        } catch (err) {
          setStreamErrorText(errorMessage(err));
          return;
        }

        const { tool_call_id, tool_name, tool_args } = payload;
        void tool_call_id;

        const entry = getFrontendTool(tool_name);
        if (!entry) {
          setStreamErrorText(`No Frontend handler registered for tool "${tool_name}".`);
          return;
        }

        const argResult = entry.validateInput(tool_args ?? {});
        if (!argResult.ok) {
          setStreamErrorText(argResult.error ?? "Tool argument validation failed.");
          return;
        }

        setToolProgress({
          step: "frontend",
          status: "running",
          message: "Frontend tool is calling…",
        });

        let raw;
        try {
          raw = await entry.execute(tool_args ?? {}, abortController.signal);
        } catch (err) {
          if (cancelled || isAbortError(err)) {
            return;
          }
          setStreamErrorText(errorMessage(err));
          return;
        }
        if (cancelled) {
          return;
        }

        setToolProgress({
          step: "frontend",
          status: "running",
          message: "Validating tool call and result…",
        });

        let validated;
        try {
          validated = entry.validateOutput(raw);
        } catch (err) {
          setStreamErrorText(errorMessage(err));
          return;
        }

        if (!validated.ok) {
          setStreamErrorText(validated.error ?? "Tool output validation failed.");
          return;
        }

        await submit(undefined, {
          command: { resume: JSON.stringify(validated.value) },
          streamResumable: true,
          context: streamContext,
        });
      } catch (err) {
        if (cancelled || isAbortError(err)) {
          return;
        }
        setStreamErrorText(errorMessage(err));
      } finally {
        if (activeRunRef.current === runControl) {
          activeRunRef.current = null;
        }
        if (!cancelled) {
          setIsFrontendExecuting(false);
          setTimeout(() => {
            setToolProgress(null);
          }, 200);
        }
      }
    },
    [submit, streamContext, setStreamErrorText, setToolProgress],
  );

  useEffect(() => {
    return () => {
      activeRunRef.current?.abort();
    };
  }, [streamContext?.thread_id]);

  return { isFrontendExecuting, runEngine };
}

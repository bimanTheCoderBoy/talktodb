import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import MessageRowMapLink from "./MessageRowMapLink";
import MessageRowAIStreaming from "./MessageRowAIStreaming";
import MessageRowToolCall from "./MessageRowToolCall";
import MessageRowTool from "./MessageRowTool";
import MessageRowHuman from "./MessageRowHuman";
import MessageRowAI from "./MessageRowAI";
import ToolProgressRow from "./ToolProgressRow";
import LoadingRow from "./LoadingRow";
import { buildHumanNavEntries } from "./ChatMessageNavigator";

// --- Height estimates per message type (px) ---
// Used as initial guess before measureElement captures actual height.
// Tool results default to collapsed (~120px), AI responses vary with content.
const HEIGHT_ESTIMATES = {
  human: 80,
  ai_streaming: 150,
  ai_toolcall: 60,
  ai_maplink: 70,
  ai_named: 200,
  tool: 120,
  fallback: 100,
};

function estimateHeight(message) {
  if (!message) return HEIGHT_ESTIMATES.fallback;
  if (message.type === "human") return HEIGHT_ESTIMATES.human;
  if (message.type === "tool") return HEIGHT_ESTIMATES.tool;
  if (message.type === "ai") {
    if (message.name === "GO_TO_MAP_LINK") return HEIGHT_ESTIMATES.ai_maplink;
    if (message.tool_calls?.length > 0) return HEIGHT_ESTIMATES.ai_toolcall;
    if (message.name == null) return HEIGHT_ESTIMATES.ai_streaming;
    return HEIGHT_ESTIMATES.ai_named;
  }
  return HEIGHT_ESTIMATES.fallback;
}

// --- Message type renderer (memoized to avoid re-evaluation on parent re-render) ---
const MessageRenderer = React.memo(function MessageRenderer({ message, isLoading, onCopy, citationMap }) {
  if (message.type === "ai" && message.name === "GO_TO_MAP_LINK") {
    return <MessageRowMapLink content={message.content} />;
  }
  if (message.type === "ai" && message.name == null) {
    return <MessageRowAIStreaming message={message} />;
  }
  if (message.type === "ai" && message.tool_calls?.length > 0) {
    return <MessageRowToolCall toolCalls={message.tool_calls} />;
  }
  if (message.type === "tool") {
    return <MessageRowTool message={message} onCopy={onCopy} />;
  }
  if (message.type === "human") {
    return <MessageRowHuman content={message.content} />;
  }
  return <MessageRowAI message={message} onCopy={onCopy} citationMap={citationMap} />;
});

// --- Find nearest scrollable ancestor (StickToBottom doesn't forward refs) ---
function useScrollParent(ref) {
  const [scrollElement, setScrollElement] = useState(null);
  useEffect(() => {
    if (!ref.current) return;
    let el = ref.current.parentElement;
    while (el) {
      const { overflowY } = getComputedStyle(el);
      if (overflowY === "auto" || overflowY === "scroll") {
        setScrollElement(el);
        return;
      }
      el = el.parentElement;
    }
  }, [ref]);
  return scrollElement;
}

// --- Main virtualized message list ---
const StreamingMessageList = React.memo(function StreamingMessageList({
  messages,
  isLoading,
  toolProgress,
  onCopy,
  onNavStateChange,
}) {
  // --- Find the scroll container (StickToBottom's overflow-y:auto div) ---
  const containerRef = useRef(null);
  const scrollElement = useScrollParent(containerRef);

  // --- Filter + deduplicate (runs on full array, cheap string comparisons) ---
  const visibleMessages = useMemo(() => {
    if (!Array.isArray(messages)) return [];
    const deduped = [];
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      if (!msg) continue;

      // Skip IGNORE and empty AI messages
      if (msg.type === "ai" && (msg.name === "IGNORE" || msg.content === "")) continue;

      // Skip stale streaming messages (no reasoning, not currently loading)
      if (msg.type === "ai" && msg.name == null) {
        const hasRealReasoning =
          msg.additional_kwargs?.reasoning && msg.additional_kwargs.reasoning !== "";
        if (!isLoading && !hasRealReasoning) continue;
      }

      // Skip consecutive duplicates (same type + content)
      const prev = deduped[deduped.length - 1];
      if (
        prev &&
        prev.type === msg.type &&
        prev.content === msg.content &&
        msg.content !== "" &&
        msg.content != null
      ) {
        continue;
      }

      deduped.push(msg);
    }
    return deduped;
  }, [messages, isLoading]);

  // --- Merge all doc_retrieval_tool citation maps into one lookup ---
  const citationMap = useMemo(() => {
    let map = null;
    for (const msg of visibleMessages) {
      if (msg.type === "tool" && msg.name === "doc_retrieval_tool" && msg.artifact) {
        try {
          const parsed = typeof msg.artifact === "string" ? JSON.parse(msg.artifact) : msg.artifact;
          const cm = parsed?.citation_map;
          if (cm) {
            if (!map) map = { ...cm };
            else Object.assign(map, cm);
          }
        } catch { /* skip malformed artifacts */ }
      }
    }
 
    return map;
  }, [visibleMessages]);

  // --- Extra space for ToolProgress + Loading rows below the virtual list ---
  const toolProgressHeight = toolProgress ? 60 : 0;
  const loadingHeight = isLoading ? 80 : 0;
  const extraBottomHeight = toolProgressHeight + loadingHeight;

  // --- Virtualizer ---
  const virtualizer = useVirtualizer({
    count: visibleMessages.length,
    getScrollElement: () => scrollElement,
    estimateSize: (index) => estimateHeight(visibleMessages[index]),
    overscan: 5,
  });

  // --- Auto-scroll to bottom when new messages arrive during streaming ---
  const prevCount = useRef(visibleMessages.length);
  useEffect(() => {
    if (visibleMessages.length > prevCount.current && isLoading) {
      virtualizer.scrollToIndex(visibleMessages.length - 1, { align: "end" });
    }
    prevCount.current = visibleMessages.length;
  }, [visibleMessages.length, isLoading, virtualizer]);

  // --- Shared measure callback (virtualizer reads data-index from the element) ---
  const measureRef = useCallback(
    (el) => {
      if (el) virtualizer.measureElement(el);
    },
    [virtualizer]
  );

  const virtualItems = virtualizer.getVirtualItems();
  const totalVirtualHeight = virtualizer.getTotalSize();

  const navEntries = useMemo(
    () => buildHumanNavEntries(visibleMessages),
    [visibleMessages]
  );

  const [activeNavIndex, setActiveNavIndex] = useState(null);

  // // Track which human turn is nearest the top of the viewport
  // useEffect(() => {
  //   if (!navEntries.length || !virtualItems.length) {
  //     setActiveNavIndex(null);
  //     return;
  //   }
  //   const firstVisible = virtualItems[0]?.index ?? 0;
  //   let best = navEntries[0].index;
  //   for (const e of navEntries) {
  //     if (e.index <= firstVisible) best = e.index;
  //     else break;
  //   }
  //   setActiveNavIndex(best);
  // }, [virtualItems, navEntries]);
  // Track which human turn is nearest the top of the viewport
useEffect(() => {
  if (!scrollElement || !navEntries.length) {
    setActiveNavIndex(null);
    return;
  }

  const handleScroll = () => {
    const scrollTop = scrollElement.scrollTop;
    let best = navEntries[0].index;
    for (const e of navEntries) {
      const itemOffset = virtualizer.getOffsetForIndex(e.index, "start")?.[0] ?? 0;
      if (itemOffset <= scrollTop + 50) {
        best = e.index;
      } else {
        break;
      }
    }
    setActiveNavIndex(best);
  };

  handleScroll(); // run once immediately
  scrollElement.addEventListener("scroll", handleScroll, { passive: true });
  return () => scrollElement.removeEventListener("scroll", handleScroll);
}, [scrollElement, navEntries, virtualizer]);

  const handleNavJump = useCallback(
    (index) => {
      virtualizer.scrollToIndex(index, { align: "start", behavior: "smooth" });
      setActiveNavIndex(index);
    },
    [virtualizer]
  );

  // Lift navigator state to parent so the rail can sit at extreme-right of chat pane
  useEffect(() => {
    if (!onNavStateChange) return;
    onNavStateChange({
      entries: navEntries,
      activeIndex: activeNavIndex,
      jump: handleNavJump,
    });
  }, [navEntries, activeNavIndex, handleNavJump, onNavStateChange]);

  return (
    <div
      ref={containerRef}
      style={{
        height: `${totalVirtualHeight + extraBottomHeight}px`,
        width: "100%",
        position: "relative",
      }}
    >
      {/* --- Virtualized messages --- */}
      {virtualItems.map((virtualRow) => {
        const message = visibleMessages[virtualRow.index];
        if (!message) return null;

        const key = message.id
          ? `${message.id}-${virtualRow.index}`
          : `${message.type}-${message.name ?? "msg"}-${virtualRow.index}`;

        return (
          <div
            key={key}
            data-index={virtualRow.index}
            data-msg-type={message.type}
            ref={measureRef}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <div className="w-full max-w-6xl min-w-0 mx-auto">
              <MessageRenderer message={message} isLoading={isLoading} onCopy={onCopy} citationMap={citationMap} />
            </div>
          </div>
        );
      })}

      {/* --- Tool progress (positioned after virtual list) --- */}
      {toolProgress && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            transform: `translateY(${totalVirtualHeight}px)`,
          }}
        >
          <div className="w-full max-w-6xl min-w-0 mx-auto">
            <ToolProgressRow step={toolProgress.step} message={toolProgress.message} />
          </div>
        </div>
      )}

      {/* --- Loading indicator (positioned after tool progress) --- */}
      {isLoading && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            transform: `translateY(${totalVirtualHeight + toolProgressHeight}px)`,
          }}
        >
          <div className="w-full max-w-6xl min-w-0 mx-auto">
            <LoadingRow />
          </div>
        </div>
      )}
    </div>
  );
});

export default StreamingMessageList;

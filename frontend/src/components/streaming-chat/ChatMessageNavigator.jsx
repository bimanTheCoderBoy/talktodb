import React, { useState, useCallback, useEffect, useRef } from "react";

function previewText(content, max = 64) {
  const raw =
    typeof content === "string"
      ? content
      : content == null
        ? ""
        : JSON.stringify(content);
  const oneLine = raw.replace(/\s+/g, " ").trim();
  if (!oneLine) return "Message";
  return oneLine.length > max ? `${oneLine.slice(0, max)}…` : oneLine;
}

/**
 * Compact right-edge navigator (light ticks, extreme right).
 * Native scrollbar is hidden on `.chat-pane-scroll` so only this rail shows.
 */
const ChatMessageNavigator = React.memo(function ChatMessageNavigator({
  entries,
  activeIndex,
  onJump,
}) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef(null);

  const clearClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearClose();
    closeTimer.current = setTimeout(() => setOpen(false), 140);
  };

  useEffect(() => () => clearClose(), []);

  const handleJump = useCallback(
    (index) => {
      onJump?.(index);
    },
    [onJump]
  );

  if (!entries?.length) return null;

  // Keep rail compact like ChatGPT (short stack near mid-right, not full-height spread)
  const ticks = entries.slice(0, 18);

  return (
    <div className="pointer-events-none absolute inset-y-0 right-0 z-50">
      <div
        className="pointer-events-auto absolute top-1/2 right-0 -translate-y-1/2 flex items-center"
        onMouseEnter={() => {
          clearClose();
          setOpen(true);
        }}
        onMouseLeave={scheduleClose}
      >
        {/* Compact light tick stack — flush to extreme right edge */}
        <div
          className={`flex flex-col items-end justify-center gap-[3px] py-1 pr-[2px] pl-3 transition-opacity duration-100 ${
            open ? "opacity-0 pointer-events-none" : "opacity-100"
          }`}
        >
          {ticks.map((e) => {
            const active = e.index === activeIndex;
            return (
              <button
                key={`tick-${e.index}`}
                type="button"
                title={e.label}
                onClick={() => handleJump(e.index)}
                className={`block rounded-full transition-[width,opacity,background-color] duration-100 ${
                  active
                    ? "h-[1.5px] w-[9px] bg-foreground/80"
                    : "h-[1px] w-[6px] bg-foreground/25 hover:bg-foreground/55 hover:w-[9px]"
                }`}
              />
            );
          })}
        </div>

        {/* Hover panel from extreme right */}
        <div
          className={`absolute right-0 top-1/2 -translate-y-1/2 transition-all duration-150 origin-right ${
            open
              ? "opacity-100 translate-x-0 pointer-events-auto"
              : "opacity-0 translate-x-1 pointer-events-none"
          }`}
          onMouseEnter={clearClose}
          onMouseLeave={scheduleClose}
        >
          <div className="w-[240px] max-h-[min(60vh,26rem)] flex flex-col rounded-xl border border-border bg-popover/95 shadow-xl shadow-black/30 backdrop-blur-md overflow-hidden">
            <div className="flex-1 overflow-y-auto overscroll-contain py-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
              {entries.map((e) => {
                const selected = e.index === activeIndex;
                return (
                  <button
                    key={`nav-${e.index}`}
                    type="button"
                    onClick={() => handleJump(e.index)}
                    className={`w-full text-left px-3 py-2 text-[12.5px] leading-snug transition-colors ${
                      selected
                        ? "bg-primary/10 text-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                    title={e.label}
                  >
                    <span className="line-clamp-2">{e.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

export function buildHumanNavEntries(visibleMessages) {
  if (!Array.isArray(visibleMessages)) return [];
  const out = [];
  for (let i = 0; i < visibleMessages.length; i++) {
    const msg = visibleMessages[i];
    if (msg?.type !== "human") continue;
    out.push({ index: i, label: previewText(msg.content) });
  }
  return out;
}

export default ChatMessageNavigator;

import React, { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MessageSquare, Search, X } from "lucide-react";

/**
 * Plus–style centered search modal for chats.
 */
export default function ChatSearchModal({
  open,
  onClose,
  threads = [],
  currentThreadId,
  onSelect,
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const results = useMemo(() => {
    const list = Array.isArray(threads) ? threads : [];
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((thread) => {
      const title = (thread?.metadata?.thread_title || "New Chat").toLowerCase();
      const id = String(thread?.thread_id || "").toLowerCase();
      return title.includes(q) || id.includes(q);
    });
  }, [threads, query]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[12vh] px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Search chats"
    >
      {/* Backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-black/40 dark:bg-black/55 backdrop-blur-[2px]"
        aria-label="Close search"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-[640px] rounded-2xl border border-border bg-popover shadow-2xl shadow-black/30 overflow-hidden">
        {/* Search input row */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
          <Search className="w-5 h-5 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats..."
            className="flex-1 bg-transparent text-[15px] text-foreground placeholder:text-muted-foreground outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-[min(52vh,420px)] overflow-y-auto py-2 [scrollbar-width:thin]">
          <p className="px-4 pt-1 pb-2 text-[12px] font-medium text-muted-foreground">
            {query.trim() ? "Results" : "Recent chats"}
          </p>

          {results.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No chats found
            </div>
          ) : (
            <ul className="px-1.5 pb-1">
              {results.map((thread) => {
                const title = thread?.metadata?.thread_title || "New Chat";
                const active = currentThreadId === thread.thread_id;
                return (
                  <li key={thread.thread_id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect?.(thread);
                        onClose?.();
                      }}
                      className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                        active
                          ? "bg-primary/10 text-foreground"
                          : "text-foreground/80 hover:bg-accent hover:text-foreground"
                      }`}
                    >
                      <MessageSquare className="w-4 h-4 text-muted-foreground shrink-0" />
                      <span className="truncate text-[14px]">{title}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

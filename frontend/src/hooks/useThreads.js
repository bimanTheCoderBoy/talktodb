import { useState, useEffect, useMemo, useCallback } from "react";
import { getThreads, deleteThread, update_thread_title, update_thread_pinned } from "@/api";

const LS_PINNED_COLLAPSED = "talkToDB.sidebar.pinnedCollapsed";
const LS_CHATS_COLLAPSED = "talkToDB.sidebar.chatsCollapsed";
const LS_CHATS_EXPANDED = "talkToDB.sidebar.chatsExpanded";
const CHATS_PREVIEW_COUNT = 8;

function readBool(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    if (v == null) return fallback;
    return v === "1" || v === "true";
  } catch {
    return fallback;
  }
}

function writeBool(key, value) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

function sortThreads(list) {
  return [...(list || [])].sort((a, b) => {
    const ap = a?.metadata?.pinned ? 1 : 0;
    const bp = b?.metadata?.pinned ? 1 : 0;
    if (ap !== bp) return bp - ap;
    const at = a?.metadata?.pinned_at || 0;
    const bt = b?.metadata?.pinned_at || 0;
    if (ap && bp && at !== bt) return bt - at;
    const ac = a?.updated_at || a?.created_at || "";
    const bc = b?.updated_at || b?.created_at || "";
    return String(bc).localeCompare(String(ac));
  });
}

export function useThreads({ threadTitle, threads, setThreads, currentThread, setCurrentThread }) {
  const [loading, setLoading] = useState(true);
  const [editingThreadId, setEditingThreadId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [pinnedCollapsed, setPinnedCollapsed] = useState(() => readBool(LS_PINNED_COLLAPSED, false));
  const [chatsCollapsed, setChatsCollapsed] = useState(() => readBool(LS_CHATS_COLLAPSED, false));
  const [chatsExpanded, setChatsExpanded] = useState(() => readBool(LS_CHATS_EXPANDED, false));

  useEffect(() => {
    if (!editingThreadId) return;
    const handleClickOutside = (e) => {
      if (!e.target.closest("[data-edit-thread]")) {
        setEditingThreadId(null);
        setEditValue("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [editingThreadId]);

  const fetchThreads = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getThreads();
      setThreads(sortThreads(response.threads || []));
    } catch (error) {
      console.error("Error fetching threads:", error);
      setThreads([]);
    } finally {
      setLoading(false);
    }
  }, [setThreads]);

  useEffect(() => {
    fetchThreads();
  }, [threadTitle, fetchThreads]);

  const handleThreadSelect = useCallback(
    (thread) => {
      setCurrentThread(thread);
    },
    [setCurrentThread]
  );

  const handleDeleteThread = useCallback(
    async (threadId, e) => {
      e.stopPropagation();
      try {
        await deleteThread(threadId);
        setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
        if (currentThread?.thread_id === threadId) {
          setCurrentThread(null);
        }
      } catch (error) {
        console.error("Error deleting thread:", error);
      }
    },
    [currentThread, setCurrentThread, setThreads]
  );

  const handleEditThread = useCallback((thread, e) => {
    e.stopPropagation();
    setEditingThreadId(thread.thread_id);
    setEditValue(thread?.metadata?.thread_title || "New Chat");
  }, []);

  const handleSaveEdit = useCallback(
    async (threadId, e) => {
      e.stopPropagation();
      try {
        const thread = threads.find((t) => t.thread_id === threadId);
        await update_thread_title(threadId, editValue.trim() || "New Chat", thread?.metadata);
        setThreads((prev) =>
          prev.map((t) =>
            t.thread_id === threadId
              ? { ...t, metadata: { ...t.metadata, thread_title: editValue.trim() || "New Chat" } }
              : t
          )
        );
        if (currentThread?.thread_id === threadId) {
          setCurrentThread({
            ...currentThread,
            metadata: { ...currentThread.metadata, thread_title: editValue.trim() || "New Chat" },
          });
        }
        setEditingThreadId(null);
        setEditValue("");
      } catch (error) {
        console.error("Error updating thread title:", error);
      }
    },
    [threads, editValue, currentThread, setCurrentThread, setThreads]
  );

  const handleCancelEdit = useCallback((e) => {
    e.stopPropagation();
    setEditingThreadId(null);
    setEditValue("");
  }, []);

  const handlePinThread = useCallback(
    async (thread, e) => {
      e.stopPropagation();
      const nextPinned = !thread?.metadata?.pinned;
      try {
        await update_thread_pinned(thread.thread_id, nextPinned, thread?.metadata || {});
        setThreads((prev) =>
          sortThreads(
            prev.map((t) =>
              t.thread_id === thread.thread_id
                ? {
                    ...t,
                    metadata: {
                      ...t.metadata,
                      pinned: nextPinned,
                      pinned_at: nextPinned ? Date.now() : null,
                    },
                  }
                : t
            )
          )
        );
        if (currentThread?.thread_id === thread.thread_id) {
          setCurrentThread({
            ...currentThread,
            metadata: {
              ...currentThread.metadata,
              pinned: nextPinned,
              pinned_at: nextPinned ? Date.now() : null,
            },
          });
        }
      } catch (error) {
        console.error("Error pinning thread:", error);
      }
    },
    [currentThread, setCurrentThread, setThreads]
  );

  const isPinned = (thread) => !!thread?.metadata?.pinned;
  const pinnedThreads = threads.filter(isPinned);
  const recentThreads = threads.filter((t) => !isPinned(t));

  const visibleRecentThreads = useMemo(() => {
    if (chatsExpanded || recentThreads.length <= CHATS_PREVIEW_COUNT) return recentThreads;
    return recentThreads.slice(0, CHATS_PREVIEW_COUNT);
  }, [recentThreads, chatsExpanded]);

  const togglePinnedCollapsed = () => {
    setPinnedCollapsed((prev) => {
      const next = !prev;
      writeBool(LS_PINNED_COLLAPSED, next);
      return next;
    });
  };
  const toggleChatsCollapsed = () => {
    setChatsCollapsed((prev) => {
      const next = !prev;
      writeBool(LS_CHATS_COLLAPSED, next);
      return next;
    });
  };
  const toggleChatsExpanded = () => {
    setChatsExpanded((prev) => {
      const next = !prev;
      writeBool(LS_CHATS_EXPANDED, next);
      return next;
    });
  };

  return {
    loading,
    fetchThreads,
    editingThreadId,
    editValue,
    setEditValue,
    pinnedCollapsed,
    chatsCollapsed,
    chatsExpanded,
    pinnedThreads,
    recentThreads,
    visibleRecentThreads,
    handleThreadSelect,
    handleDeleteThread,
    handleEditThread,
    handleSaveEdit,
    handleCancelEdit,
    handlePinThread,
    togglePinnedCollapsed,
    toggleChatsCollapsed,
    toggleChatsExpanded,
  };
}

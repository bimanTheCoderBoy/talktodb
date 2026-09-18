import React from "react";
import { RefreshCw, MessageSquare, ChevronDown } from "lucide-react";
import { SidebarGroup, SidebarGroupContent, SidebarMenu } from "@/components/ui/sidebar";
import ThreadItem from "./ThreadItem";

function SectionHeader({ label, count, collapsed, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-full flex items-center gap-1.5 px-1 py-1 mb-1 rounded-md text-left group/section hover:bg-accent transition-colors"
      title={collapsed ? `Show ${label}` : `Hide ${label}`}
    >
      <ChevronDown
        className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${collapsed ? "-rotate-90" : "rotate-0"}`}
      />
      <span className="text-[11px] font-medium text-muted-foreground group-hover/section:text-foreground">
        {label}
      </span>
      {typeof count === "number" && (
        <span className="ml-auto text-[10px] text-muted-foreground/70 tabular-nums">{count}</span>
      )}
    </button>
  );
}

export default function ThreadList({
  loading,
  threads,
  pinnedThreads,
  recentThreads,
  visibleRecentThreads,
  currentThread,
  editingThreadId,
  editValue,
  setEditValue,
  pinnedCollapsed,
  chatsCollapsed,
  chatsExpanded,
  onSelect,
  onEdit,
  onSaveEdit,
  onCancelEdit,
  onDelete,
  onPin,
  togglePinnedCollapsed,
  toggleChatsCollapsed,
  toggleChatsExpanded,
}) {
  const threadItemProps = (thread) => ({
    thread,
    isActive: currentThread?.thread_id === thread.thread_id,
    editingThreadId,
    editValue,
    setEditValue,
    onSelect,
    onEdit,
    onSaveEdit,
    onCancelEdit,
    onDelete,
    onPin,
  });

  return (
    <SidebarGroup className="flex-1 min-h-0 px-4 pb-4 overflow-hidden">
      <SidebarGroupContent className="h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain scrollbar-thin scrollbar-thumb-muted-foreground/30 scrollbar-track-transparent">
        <SidebarMenu className="space-y-1">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="flex flex-col items-center gap-2">
                <RefreshCw className="w-5 h-5 text-primary animate-spin" />
                <span className="text-muted-foreground text-xs">Loading chats...</span>
              </div>
            </div>
          ) : threads.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 px-2">
              <div className="w-12 h-12 mb-3 rounded-xl bg-secondary border border-border flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground text-sm text-center mb-1">No chats yet</p>
              <p className="text-muted-foreground/70 text-xs text-center">Click + to start a new conversation</p>
            </div>
          ) : (
            <>
              {pinnedThreads.length > 0 && (
                <div className="mb-3">
                  <SectionHeader label="Pinned" count={pinnedThreads.length} collapsed={pinnedCollapsed} onToggle={togglePinnedCollapsed} />
                  <div className={`space-y-1 transition-all duration-200 ${pinnedCollapsed ? "max-h-0 opacity-0 overflow-hidden pointer-events-none" : "overflow-visible opacity-100"}`}>
                    {pinnedThreads.map(t => <ThreadItem key={t.thread_id} {...threadItemProps(t)} />)}
                  </div>
                </div>
              )}
              {recentThreads.length > 0 && (
                <div>
                  <SectionHeader label="Chats" count={recentThreads.length} collapsed={chatsCollapsed} onToggle={toggleChatsCollapsed} />
                  <div className={`transition-all duration-200 ${chatsCollapsed ? "max-h-0 opacity-0 overflow-hidden pointer-events-none" : "overflow-visible opacity-100"}`}>
                    <div className="space-y-1">
                      {visibleRecentThreads.map(t => <ThreadItem key={t.thread_id} {...threadItemProps(t)} />)}
                    </div>
                    {recentThreads.length > 8 && (
                      <button
                        type="button"
                        onClick={toggleChatsExpanded}
                        className="mt-1.5 w-full px-2 py-1.5 text-left text-[11px] text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary/40 transition-colors"
                      >
                        {chatsExpanded ? "Show less" : `Show more (${recentThreads.length - 8})`}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
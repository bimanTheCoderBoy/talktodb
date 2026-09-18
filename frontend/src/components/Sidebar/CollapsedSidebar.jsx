import React, { useState, useRef } from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Plus, Search, Pin, MessageSquare } from "lucide-react";
import UserCard from "@/auth/UserCard";

export default function CollapsedSidebar({ threads, currentThread, setCurrentThread, addNewThread, setSidebarOpen, onSearchOpen }) {
  const [pinHovered, setPinHovered] = useState(false);
  const pinBtnRef = useRef(null);
  const pinnedCount = threads.filter(t => t?.metadata?.pinned).length;

  return (
    <div className="flex flex-col items-center gap-3 pt-4 pb-4 h-full border-r border-sidebar-border">
      {/* Open sidebar */}
      <div className="relative group/trigger">
        <SidebarTrigger
          className="cursor-pointer p-2 rounded-xl shadow-lg transition-all duration-200 hover:scale-105 h-8 w-8 bg-secondary text-muted-foreground hover:text-primary-foreground hover:bg-primary"
          onClick={() => setSidebarOpen(true)}
        />
        <span className="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 text-[11px] font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 pointer-events-none group-hover/trigger:opacity-100 transition-opacity z-[70]">
          Open Sidebar
        </span>
      </div>

      {/* New chat */}
      <div className="relative group/btn">
        <button onClick={addNewThread} className="p-2 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer transition-all duration-200 shadow-lg shadow-primary/20 hover:shadow-primary/30 hover:scale-105 h-8 w-8 flex items-center justify-center" title="New Chat">
          <Plus className="w-4 h-4" />
        </button>
        <span className="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 text-[11px] font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 pointer-events-none group-hover/btn:opacity-100 transition-opacity z-[70]">
          New Chat
        </span>
      </div>

      {/* Search */}
      <div className="relative group/btn">
        <button onClick={onSearchOpen} className="p-2 rounded-xl bg-secondary border border-border hover:bg-accent hover:text-foreground text-muted-foreground cursor-pointer transition-all duration-200 hover:scale-105 hover:shadow-lg h-8 w-8 flex items-center justify-center" title="Search Chats">
          <Search className="w-4 h-4" />
        </button>
        <span className="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 text-[11px] font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 pointer-events-none group-hover/btn:opacity-100 transition-opacity z-[70]">
          Search Chats
        </span>
      </div>

      {/* Pinned chats flyout */}
      <div className="relative group/btn" onMouseEnter={() => setPinHovered(true)} onMouseLeave={() => setPinHovered(false)}>
        <button ref={pinBtnRef} className="p-2 rounded-xl bg-secondary border border-border hover:bg-accent hover:text-foreground text-muted-foreground cursor-pointer transition-all duration-200 hover:scale-105 hover:shadow-lg h-8 w-8 flex items-center justify-center relative">
          <Pin className="w-4 h-4" />
          {pinnedCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 text-[9px] font-bold bg-primary text-primary-foreground rounded-full flex items-center justify-center">
              {pinnedCount}
            </span>
          )}
        </button>

        {pinHovered && pinBtnRef.current && (() => {
          const rect = pinBtnRef.current.getBoundingClientRect();
          return (
            <div className="fixed w-64 max-h-80 z-[9999]" style={{ left: `${rect.right}px`, top: `${rect.top}px`, paddingLeft: "8px" }}>
              <div className="bg-popover border border-border rounded-xl shadow-xl overflow-hidden">
                <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                  <Pin className="w-3.5 h-3.5 text-primary fill-primary" />
                  <span className="text-xs font-semibold text-foreground">Pinned Chats</span>
                  <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{pinnedCount}</span>
                </div>
                <div className="overflow-y-auto max-h-64 py-1">
                  {pinnedCount === 0 ? (
                    <p className="px-3 py-4 text-xs text-muted-foreground text-center">No pinned chats</p>
                  ) : (
                    threads.filter(t => t?.metadata?.pinned).map(thread => (
                      <button
                        key={thread.thread_id}
                        onClick={() => setCurrentThread(thread)}
                        className={`w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-accent transition-colors text-sm ${
                          currentThread?.thread_id === thread.thread_id ? "bg-primary/10 text-foreground font-medium" : "text-foreground/80"
                        }`}
                      >
                        <MessageSquare className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                        <span className="truncate">{thread?.metadata?.thread_title || "New Chat"}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      <div className="flex-1" />
      <UserCard />
    </div>
  );
}
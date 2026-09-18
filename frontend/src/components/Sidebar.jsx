import React, { useState, useEffect } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { useTheme } from "next-themes";
import { Plus, RefreshCw, Sparkles, Search, MonitorCog } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
} from "@/components/ui/sidebar";
import logoRaNora from "@/asset/raNora-icon-coloured-text.png";
import { ThemeToggle } from "./ThemeToggle";
import UserCard from "@/auth/UserCard";
import keycloak from "@/keycloak";
import { useProjectContext } from "../context/ProjectContext";
import ChatSearchModal from "./ChatSearchModal";
import { useThreads } from "../hooks/useThreads";
import ThreadList from "./Sidebar/ThreadList";
import CollapsedSidebar from "./Sidebar/CollapsedSidebar";

export default function SidebarApp({ sidebarOpen, setSidebarOpen, currentThread, setCurrentThread, threadTitle, addNewThread, threads, setThreads, sidebarWidth }) {
  const { theme } = useTheme();
  const [searchOpen, setSearchOpen] = useState(false);
  const isAdmin = keycloak.tokenParsed?.realm_access?.roles.includes("CONFIG_MANAGEMENT");
  const projectName = useProjectContext().projectName;

  const {
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
  } = useThreads({ projectName, threadTitle, threads, setThreads, currentThread, setCurrentThread });

  // Ctrl/Cmd+K opens search
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <SidebarProvider className="h-screen w-full">
      <div className={`h-screen bg-sidebar text-sidebar-foreground transition-all duration-300 relative overflow-visible ${sidebarOpen ? "min-w-64 w-full" : "w-12"}`}>
        
        {/* === OPEN SIDEBAR === */}
        {sidebarOpen && (
          <Sidebar className="w-full h-screen z-[60] transition-all duration-0" style={{ width: sidebarWidth }}>
            <SidebarContent className="flex flex-col h-full overflow-hidden bg-sidebar border-r border-sidebar-border">
              
              {/* Brand */}
              <SidebarGroup className="flex-shrink-0 border-b border-border py-5 px-4">
                <div className="flex flex-col items-center gap-3">
                  <img src={logoRaNora} alt="" className="h-12 w-auto object-contain dark:drop-shadow-md" />
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-medium bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 rounded-full">
                    <span className="w-1.5 h-1.5 bg-amber-500 dark:bg-amber-400 rounded-full animate-pulse" />
                    raNora v1.5.2
                  </span>
                </div>
              </SidebarGroup>

              {/* Chat header */}
              <SidebarGroup className="flex-shrink-0 px-4 pt-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <SidebarGroupLabel className="text-muted-foreground font-semibold text-xs uppercase tracking-wider">
                      Chats
                    </SidebarGroupLabel>
                    <span className="px-1.5 py-0.5 text-[10px] bg-secondary text-muted-foreground rounded-full">
                      {threads.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                  <button onClick={() => setSearchOpen(true)} title="Search chats" className="z-[80] p-1.5 rounded-lg bg-secondary border border-border text-muted-foreground hover:bg-accent hover:text-foreground hover:scale-105 hover:shadow-lg cursor-pointer transition-all duration-200">
                    <Search className="w-4 h-4" />
                  </button>

                  <button onClick={addNewThread} title="New Chat" className="group p-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 hover:scale-105 cursor-pointer transition-all duration-200 shadow-lg shadow-primary/20 hover:shadow-primary/30">
                    <Plus className="w-4 h-4" />
                  </button>

                  <button onClick={fetchThreads} disabled={loading} title="Refresh" className="p-1.5 rounded-lg bg-secondary border border-border text-muted-foreground hover:bg-accent hover:text-foreground hover:scale-105 hover:shadow-lg cursor-pointer transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:shadow-none">
                    <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                  </button>
                </div>
                </div>
              </SidebarGroup>

              {/* Thread List */}
              <ThreadList
                loading={loading}
                threads={threads}
                pinnedThreads={pinnedThreads}
                recentThreads={recentThreads}
                visibleRecentThreads={visibleRecentThreads}
                currentThread={currentThread}
                editingThreadId={editingThreadId}
                editValue={editValue}
                setEditValue={setEditValue}
                pinnedCollapsed={pinnedCollapsed}
                chatsCollapsed={chatsCollapsed}
                chatsExpanded={chatsExpanded}
                onSelect={handleThreadSelect}
                onEdit={handleEditThread}
                onSaveEdit={handleSaveEdit}
                onCancelEdit={handleCancelEdit}
                onDelete={handleDeleteThread}
                onPin={handlePinThread}
                togglePinnedCollapsed={togglePinnedCollapsed}
                toggleChatsCollapsed={toggleChatsCollapsed}
                toggleChatsExpanded={toggleChatsExpanded}
              />
            </SidebarContent>

            <ChatSearchModal open={searchOpen} onClose={() => setSearchOpen(false)} threads={threads} currentThreadId={currentThread?.thread_id} onSelect={handleThreadSelect} />

            {/* Footer */}
            <div className="flex flex-col justify-between px-2 py-1.5 border-t border-sidebar-border bg-sidebar z-[60]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-primary/60" />
                  <p className="text-muted-foreground text-[10px]">
                    Powered by{" "}
                    <a href="https://www.teoco.com/" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-700 font-medium transition-colors">
                      TEOCO
                    </a>
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <ThemeToggle />
                  {isAdmin && (
                    <button onClick={() => { window.location.href = "/admin/set-up/config"; }} title="Configure project for users (admin only)" className="p-1 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-200 cursor-pointer">
                      <MonitorCog className="w-6 h-6" />
                    </button>
                  )}
                  <UserCard />
                </div>
              </div>
            </div>
          </Sidebar>
        )}

        {/* === COLLAPSED SIDEBAR === */}
        {!sidebarOpen && (
          <CollapsedSidebar
            threads={threads}
            currentThread={currentThread}
            setCurrentThread={setCurrentThread}
            addNewThread={addNewThread}
            setSidebarOpen={setSidebarOpen}
            onSearchOpen={() => setSearchOpen(true)}
          />
        )}

        {/* Close trigger (visible when open) */}
        {sidebarOpen && (
          <div className="absolute top-2 right-2 z-[60]">
            <div className="relative group/trigger">
              <SidebarTrigger className="cursor-pointer p-2 rounded-xl shadow-lg transition-all duration-200 hover:scale-105 h-8 w-8 bg-secondary text-muted-foreground hover:text-primary-foreground hover:bg-primary shadow-primary/10 hover:shadow-primary/30" onClick={() => setSidebarOpen(false)} />
              <span className="absolute left-1/2 -translate-x-1/2 top-full mt-1.5 px-2 py-1 text-[11px] font-medium bg-popover text-popover-foreground border border-border rounded-md shadow-md whitespace-nowrap opacity-0 pointer-events-none group-hover/trigger:opacity-100 transition-opacity duration-200 z-[40]">
                Close Sidebar
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Search modal for collapsed state */}
      {!sidebarOpen && (
        <ChatSearchModal open={searchOpen} onClose={() => setSearchOpen(false)} threads={threads} currentThreadId={currentThread?.thread_id} onSelect={(thread) => { setCurrentThread(thread); setSearchOpen(false); }} />
      )}
    </SidebarProvider>
  );
}
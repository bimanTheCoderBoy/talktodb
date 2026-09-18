import React from "react";
import { Pencil, Check, X, Trash2, Pin } from "lucide-react";
import { SidebarMenuItem, SidebarMenuButton } from "@/components/ui/sidebar";

function NewsScrollTitle({ text }) {
  return (
    <span className="relative block min-w-0 flex-1 overflow-hidden group/title" title={text}>
      <span className="inline-block whitespace-nowrap text-sm font-medium group-hover/title:animate-news-scroll">
        {text}
      </span>
    </span>
  );
}

export default function ThreadItem({
  thread,
  isActive,
  editingThreadId,
  editValue,
  setEditValue,
  onSelect,
  onEdit,
  onSaveEdit,
  onCancelEdit,
  onDelete,
  onPin,
}) {
  const isPinned = !!thread?.metadata?.pinned;
  const isEditing = editingThreadId === thread.thread_id;

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild className="h-auto">
        <div
          {...(isEditing && { "data-edit-thread": true })}
          className={`w-full text-left px-3 py-2.5 rounded-xl cursor-pointer flex items-center justify-between group overflow-hidden transition-all duration-200 ${
            isActive
              ? "bg-primary/25 border border-primary/70 text-foreground shadow-lg shadow-primary/25"
              : "bg-secondary/30 hover:bg-secondary/60 text-foreground/80 border border-transparent hover:border-border"
          }`}
          onClick={() => !isEditing && onSelect(thread)}
        >
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            {isActive ? (
              <div className="w-2 h-2 bg-primary rounded-full animate-pulse flex-shrink-0" />
            ) : (
              <div className="w-2 h-2 bg-muted-foreground/40 rounded-full flex-shrink-0" />
            )}
            {isEditing ? (
              <input
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onSaveEdit(thread.thread_id, e);
                  else if (e.key === "Escape") onCancelEdit(e);
                }}
                onClick={(e) => e.stopPropagation()}
                className="w-full min-w-0 bg-secondary border border-primary/50 rounded px-2 py-1 text-sm text-foreground text-left focus:outline-none focus:ring-2 focus:ring-primary/50"
                autoFocus
              />
            ) : (
              <NewsScrollTitle text={thread?.metadata?.thread_title || "New Chat"} />
            )}
          </div>

          <div className="flex items-center gap-1 flex-shrink-0 ml-2">
            {!isEditing && (
              <button
                onClick={(e) => onPin(thread, e)}
                className={`p-1.5 rounded-lg transition-all duration-200 ${
                  isPinned
                    ? "opacity-100 hover:bg-primary/20"
                    : "opacity-0 group-hover:opacity-100 hover:bg-primary/20"
                }`}
                title={isPinned ? "Unpin chat" : "Pin chat"}
              >
                <Pin className={`w-3.5 h-3.5 ${isPinned ? "text-primary fill-primary" : "text-muted-foreground"}`} />
              </button>
            )}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all duration-200">
              {isEditing ? (
                <>
                  <button onClick={(e) => onSaveEdit(thread.thread_id, e)} className="hover:bg-green-500/20 p-1.5 rounded-lg transition-all duration-200" title="Save">
                    <Check className="w-3.5 h-3.5 text-green-400" />
                  </button>
                  <button onClick={onCancelEdit} className="hover:bg-gray-500/20 p-1.5 rounded-lg transition-all duration-200" title="Cancel">
                    <X className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                </>
              ) : (
                <>
                  <button onClick={(e) => onEdit(thread, e)} className="hover:bg-primary/20 p-1.5 rounded-lg transition-all duration-200" title="Edit chat name">
                    <Pencil className="w-3.5 h-3.5 text-primary" />
                  </button>
                  <button onClick={(e) => onDelete(thread.thread_id, e)} className="hover:bg-red-500/20 p-1.5 rounded-lg transition-all duration-200" title="Delete chat">
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
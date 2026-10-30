import React from "react";
import BrandMark from "./BrandMark";

const TopBar = ({ currentThread, sidebarOpen }) => {
  const title = currentThread?.metadata?.thread_title || "New chat";

  return (
    <div
      className={`flex w-full items-center justify-between mb-4 py-2 px-6 border-b transition-all duration-200 ${
        sidebarOpen ? "border-primary/20 bg-transparent" : "border-border bg-card"
      }`}
    >
      <div className="min-w-0">
        <p className="text-sm text-primary font-medium">Chat</p>
        <p className="text-xs text-muted-foreground mt-1 truncate max-w-md" title={title}>
          {title}
        </p>
      </div>
      {!sidebarOpen && <BrandMark size="sm" className="shrink-0" />}
    </div>
  );
};

export default TopBar;

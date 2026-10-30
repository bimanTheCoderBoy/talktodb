import React from "react";

/** Simple pulse ring loader for inline and full-page use. */
export default function AppLoader({ className = "h-8 w-8" }) {
  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      role="status"
      aria-label="Loading"
    >
      <span className="absolute inset-0 rounded-full border-2 border-primary/20" />
      <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary animate-spin" />
      <span className="h-2 w-2 rounded-full bg-primary/80 animate-pulse" />
    </div>
  );
}

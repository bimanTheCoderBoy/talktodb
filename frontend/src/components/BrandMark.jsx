import React from "react";
import { Database } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * talkToDB wordmark — compact for top bar, full for sidebar.
 */
export default function BrandMark({ size = "md", className, showTagline = false }) {
  const sizes = {
    sm: { icon: "h-4 w-4", text: "text-sm", gap: "gap-1.5", pad: "p-1" },
    md: { icon: "h-5 w-5", text: "text-lg", gap: "gap-2", pad: "p-1.5" },
    lg: { icon: "h-6 w-6", text: "text-2xl", gap: "gap-2.5", pad: "p-2" },
  };
  const s = sizes[size] ?? sizes.md;

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div
        className={cn(
          "inline-flex items-center rounded-xl bg-primary/10 ring-1 ring-primary/25",
          s.gap,
          s.pad
        )}
      >
        <span className="flex items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/30">
          <Database className={cn(s.icon, "m-1.5")} strokeWidth={2.25} />
        </span>
        <span className={cn("font-semibold tracking-tight text-foreground", s.text)}>
          talk<span className="text-primary">To</span>DB
        </span>
      </div>
      {showTagline && (
        <p className="mt-2 text-[11px] text-muted-foreground text-center max-w-[200px] leading-snug">
          Chat with your data
        </p>
      )}
    </div>
  );
}

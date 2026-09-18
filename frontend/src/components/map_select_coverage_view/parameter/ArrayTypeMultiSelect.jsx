import React, { useState, useRef, useEffect } from "react";
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, X, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ArrayTypeMultiSelect({ label, parameters, setParameters }) {
  const [open, setOpen] = useState(false);
  const options = parameters?.arrayTypes || [];
  const selected = options.filter((opt) => opt?.isSelected);

  const toggle = (value) => {
    const updated = options.map((opt) =>
      opt.value === value ? { ...opt, isSelected: !opt.isSelected } : opt
    );
    setParameters({ ...parameters, arrayTypes: updated });
  };

  const removeTag = (e, value) => {
    e.stopPropagation();
    toggle(value);
  };

  const selectAll = () => {
    const allSelected = options.every((opt) => opt.isSelected);
    const updated = options.map((opt) => ({ ...opt, isSelected: !allSelected }));
    setParameters({ ...parameters, arrayTypes: updated });
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className={cn(
            "flex items-center gap-1.5 min-w-[220px] max-w-[500px] w-full rounded-lg border px-3 py-2 text-left text-sm transition-all",
            "bg-card border-border hover:border-primary/50",
            open && "border-primary/50 ring-1 ring-primary/50"
          )}
        >
          <div className="flex flex-1 flex-wrap items-center gap-1.5 overflow-hidden">
            {selected.length === 0 ? (
              <span className="text-muted-foreground text-[13px]">{label ? `Select ${label.toLowerCase()}...` : "Select array types..."}</span>
            ) : (
              selected.map((opt) => (
                <span
                  key={opt.value}
                  className="inline-flex items-center gap-1 rounded-md bg-primary/15 border border-primary/30 px-2 py-0.5 text-xs font-medium text-primary"
                >
                  {opt.label}
                  <span
                    role="button"
                    tabIndex={-1}
                    onClick={(e) => removeTag(e, opt.value)}
                    onKeyDown={(e) => e.key === "Enter" && removeTag(e, opt.value)}
                    className="ml-0.5 rounded-sm hover:bg-red-500/30 hover:text-red-300 p-0.5 cursor-pointer transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </span>
                </span>
              ))
            )}
          </div>
          <ChevronDown
            className={cn(
              "w-4 h-4 shrink-0 text-muted-foreground transition-transform duration-200",
              open && "rotate-180"
            )}
          />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          side="top"
          align="start"
          sideOffset={6}
          className="z-10000000 w-(--radix-popover-trigger-width) min-w-[220px] max-h-[260px] overflow-y-auto rounded-lg border border-border bg-popover shadow-xl shadow-black/40 animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-2 duration-150"
        >
          {options.length > 1 && (
            <button
              type="button"
              onClick={selectAll}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-accent border-b border-border transition-colors"
            >
              <div
                className={cn(
                  "flex items-center justify-center w-4 h-4 rounded border transition-colors",
                  options.every((o) => o.isSelected)
                    ? "bg-primary border-primary"
                    : "border-border bg-transparent"
                )}
              >
                {options.every((o) => o.isSelected) && <Check className="w-3 h-3 text-primary-foreground" />}
              </div>
              {options.every((o) => o.isSelected) ? "Deselect all" : "Select all"}
            </button>
          )}

          <div className="p-1">
            {options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggle(opt.value)}
                className={cn(
                  "w-full flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors cursor-pointer",
                  opt.isSelected
                    ? "bg-primary/10 text-primary"
                    : "text-foreground hover:bg-accent"
                )}
              >
                <div
                  className={cn(
                    "flex items-center justify-center w-4 h-4 rounded border shrink-0 transition-colors",
                    opt.isSelected
                      ? "bg-primary border-primary"
                      : "border-border bg-transparent"
                  )}
                >
                  {opt.isSelected && <Check className="w-3 h-3 text-primary-foreground" />}
                </div>
                <span className="truncate">{opt.label}</span>
              </button>
            ))}
          </div>

          {options.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              No array types available
            </div>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

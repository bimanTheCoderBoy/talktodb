import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Download, Loader2 } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "./ui/button";
import { downloadToolResult } from "@/services/downloadService";

const MENU_ITEM_HEIGHT_PX = 36;
const MENU_PADDING_PX = 8;

const STATUS_LABELS = {
  PENDING: "Queued...",
  STARTED: "Converting...",
  SUCCESS: "Downloading...",
  FAILURE: "Failed",
};

const FILETYPE_LABELS = {
  pdf: "PDF",
  md: "MD",
  csv: "CSV",
};

const DownloadOptionsButton = ({
  content,
  allowedFiletypes = ["pdf"],
  defaultFiletype,
  titlePrefix = "Download",
}) => {
  const containerRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const [menuStyle, setMenuStyle] = useState(null);
  const normalizedAllowed = useMemo(() => {
    const uniq = Array.from(new Set((allowedFiletypes || []).map((t) => String(t).toLowerCase())));
    return uniq.filter((t) => ["pdf", "md", "csv"].includes(t));
  }, [allowedFiletypes]);

  const chosenDefault = defaultFiletype
    ? String(defaultFiletype).toLowerCase()
    : (normalizedAllowed[0] || "pdf");

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("");

  const updateMenuPosition = useCallback(() => {
    const buttonEl = buttonRef.current;
    if (!buttonEl) return;

    const rect = buttonEl.getBoundingClientRect();
    const menuHeight = normalizedAllowed.length * MENU_ITEM_HEIGHT_PX + MENU_PADDING_PX;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < menuHeight && rect.top > menuHeight;

    setMenuStyle(
      openUp
        ? {
            position: "fixed",
            bottom: window.innerHeight - rect.top + 4,
            right: window.innerWidth - rect.right,
            zIndex: 10000,
          }
        : {
            position: "fixed",
            top: rect.bottom + 4,
            right: window.innerWidth - rect.right,
            zIndex: 10000,
          }
    );
  }, [normalizedAllowed.length]);

  useEffect(() => {
    const onDocMouseDown = (e) => {
      if (containerRef.current?.contains(e.target)) return;
      if (menuRef.current?.contains(e.target)) return;
      setIsOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      setMenuStyle(null);
      return;
    }

    updateMenuPosition();
    const onScrollOrResize = () => updateMenuPosition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [isOpen, updateMenuPosition]);

  const runDownload = async (filetype) => {
    if (!content) {
      toast.error("No content to download");
      return;
    }

    setIsLoading(true);
    setStatusText("Converting...");
    setIsOpen(false);

    try {
      const result = await downloadToolResult(content, {
        filetype,
        onStatusUpdate: (status) => setStatusText(STATUS_LABELS[status] || status),
      });

      if (result.success) {
        toast.success(`${FILETYPE_LABELS[filetype] || filetype.toUpperCase()} download started - check your browser's download section`);
      } else {
        toast.error(result.error || `Failed to download ${FILETYPE_LABELS[filetype] || filetype.toUpperCase()}`);
      }
    } catch (error) {
      toast.error(`Failed to download ${FILETYPE_LABELS[filetype] || filetype.toUpperCase()}`);
      console.error("Download error:", error);
    } finally {
      setIsLoading(false);
      setStatusText("");
    }
  };

  const hasOptions = normalizedAllowed.length > 1;

  const handleButtonClick = () => {
    if (isLoading) return;
    if (!hasOptions) {
      runDownload(chosenDefault);
      return;
    }
    setIsOpen((v) => !v);
  };

  return (
    <div ref={containerRef} className="relative flex items-center mr-2 ">
      <span ref={buttonRef} className="inline-flex">
        <Button
          variant="outline"
          size="icon"
          className="cursor-pointer"
          onClick={handleButtonClick}
          disabled={isLoading || !content}
          title={statusText || titlePrefix}
          type="button"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <div className="flex items-center">
              <Download className="w-4 h-4" />
            </div>
          )}
        </Button>
      </span>

      {statusText && (
        <span className="text-xs text-muted-foreground animate-pulse">
          {statusText}
        </span>
      )}

      {isOpen && hasOptions && menuStyle && createPortal(
        <div
          ref={menuRef}
          style={menuStyle}
          className="min-w-28 overflow-hidden rounded-md border border-border bg-popover shadow-lg"
        >
          {normalizedAllowed.map((filetype) => (
            <button
              key={filetype}
              type="button"
              className="w-full px-3 py-2 text-left text-sm text-popover-foreground hover:bg-accent transition-colors"
              onClick={() => runDownload(filetype)}
            >
              {FILETYPE_LABELS[filetype] || filetype.toUpperCase()}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
};

export default DownloadOptionsButton;


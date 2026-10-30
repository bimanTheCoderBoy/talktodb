import SidebarApp from "./Sidebar";
import Body from "./Body";
import React, { useState, useEffect } from "react";
import { createThread } from "../api";

const Wrapper = () => {
  const [currentThread, setCurrentThread] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [threadTitle, setThreadTitle] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarMinWidth = 256;
  const sidebarMaxWidth = 600;
  const bodyMinWidth = 800;
  const [threads, setThreads] = useState([]);

  const addNewThread = async () => {
    try {
      const newThread = await createThread();
      setThreads((prev) => [newThread, ...prev]);
      setCurrentThread(newThread);
    } catch (error) {
      console.error("Error creating new thread:", error);
    }
  };

  useEffect(() => {
    const savedWidth = localStorage.getItem("sidebarWidth");
    if (savedWidth) {
      const width = parseInt(savedWidth, 10);
      if (width >= sidebarMinWidth && width <= sidebarMaxWidth) {
        setSidebarWidth(width);
      }
    }
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      const newWidth = e.clientX;
      const maxAllowedWidth = window.innerWidth - bodyMinWidth;
      const constrainedWidth = Math.max(
        sidebarMinWidth,
        Math.min(sidebarMaxWidth, Math.min(newWidth, maxAllowedWidth))
      );
      setSidebarWidth(constrainedWidth);
      localStorage.setItem("sidebarWidth", constrainedWidth.toString());
    };
    const handleMouseUp = () => setIsResizing(false);
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing, sidebarMinWidth, sidebarMaxWidth, bodyMinWidth]);

  return (
    <div className="h-screen flex overflow-hidden">
      <div
        className={`h-screen ${isResizing ? "" : "transition-all duration-300"}`}
        style={{
          width: sidebarOpen ? `${sidebarWidth}px` : "48px",
          minWidth: sidebarOpen ? `${sidebarMinWidth}px` : "48px",
          maxWidth: sidebarOpen
            ? `${Math.min(sidebarMaxWidth, window.innerWidth - bodyMinWidth)}px`
            : "48px",
          overflow: "visible",
        }}
      >
        <SidebarApp
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          currentThread={currentThread}
          setCurrentThread={setCurrentThread}
          threadTitle={threadTitle}
          addNewThread={addNewThread}
          threads={threads}
          setThreads={setThreads}
          sidebarWidth={sidebarWidth}
        />
      </div>

      {sidebarOpen && (
        <div
          onMouseDown={(e) => {
            e.preventDefault();
            setIsResizing(true);
          }}
          className="w-1.5 h-full cursor-col-resize bg-border hover:bg-primary/40 transition-colors z-[50] flex items-center justify-center flex-shrink-0"
          title="Drag to resize sidebar"
        />
      )}

      <div className="bg-background h-screen flex-1 min-w-0">
        <Body
          currentThread={currentThread}
          sidebarOpen={sidebarOpen}
          setThreadTitle={setThreadTitle}
          addNewThread={addNewThread}
          setCurrentThread={setCurrentThread}
        />
      </div>
    </div>
  );
};

export default Wrapper;

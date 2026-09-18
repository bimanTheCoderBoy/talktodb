import SidebarApp from "./Sidebar";
import Body from "./Body";  
import React, { useState, useEffect } from "react";
import { createThread } from "../api";
import { useProjectContext } from "../context/ProjectContext";

const Wrapper = () => {
  const [currentThread, setCurrentThread] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [threadTitle, setThreadTitle] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(256); // Default 256px (w-64)
  const [isResizing, setIsResizing] = useState(false);
  const sidebarMinWidth = 256;
  const sidebarMaxWidth = 600;
  const bodyMinWidth = 800;
  const projectName = useProjectContext().projectName;
  const [threads, setThreads] = useState([]);


  const addNewThread = async () => {
    try {
      const newThread = await createThread(projectName);
      setThreads(prev => [newThread, ...prev]);
      setCurrentThread(newThread);
    } catch (error) {
      console.error('Error creating new thread:', error);
    }
  };

  
  // Load saved sidebar width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem('sidebarWidth');
    if (savedWidth) {
      const width = parseInt(savedWidth, 10);
      if (width >= sidebarMinWidth && width <= sidebarMaxWidth) {
        setSidebarWidth(width);
      }
    }
  }, []);

  // Handle mouse events for resizing
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      
      const newWidth = e.clientX;
      const windowWidth = window.innerWidth;
      const maxAllowedWidth = windowWidth - bodyMinWidth;
      
      // Constrain sidebar width
      const constrainedWidth = Math.max(
        sidebarMinWidth,
        Math.min(sidebarMaxWidth, Math.min(newWidth, maxAllowedWidth))
      );
      
      setSidebarWidth(constrainedWidth);
      console.log("Sidebar width:", sidebarWidth);
      localStorage.setItem('sidebarWidth', constrainedWidth.toString());
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, sidebarMinWidth, sidebarMaxWidth, bodyMinWidth]);

  // Handle clear messages event
  useEffect(() => {
    const handleClearMessages = async (event) => {
      console.log("Clear messages event received:", event.detail);
      try {
        // Create a new thread to clear messages
        const newThread = await createThread(projectName);
        setCurrentThread(newThread);
        console.log("New thread created:", newThread);
      } catch (error) {
        console.error("Error creating new thread:", error);
      }
    };

    window.addEventListener('clearMessages', handleClearMessages);
    
    return () => {
      window.removeEventListener('clearMessages', handleClearMessages);
    };
  }, []);

  return (
    <div className={`h-screen flex overflow-hidden`}>
      {/* Sidebar */}
      {/* <div
        className={`h-screen ${
          sidebarOpen ? "" : "w-0"
        } ${isResizing ? "" : "transition-all duration-300"}`}
        style={{
          width: sidebarOpen ? `${sidebarWidth}px` : '0px',
          minWidth: sidebarOpen ? `${sidebarMinWidth}px` : '0px',
          maxWidth: sidebarOpen ? `${Math.min(sidebarMaxWidth, window.innerWidth - bodyMinWidth)}px` : '0px',
          overflow: 'visible',
        }}
      > */}
      <div
        className={`h-screen ${isResizing ? "" : "transition-all duration-300"}`}
        style={{
          width: sidebarOpen ? `${sidebarWidth}px` : '48px',
          minWidth: sidebarOpen ? `${sidebarMinWidth}px` : '48px',
          maxWidth: sidebarOpen ? `${Math.min(sidebarMaxWidth, window.innerWidth - bodyMinWidth)}px` : '48px',
          overflow: 'visible',
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

      {/* Resize Handler */}
      {sidebarOpen && (
        <div
          onMouseDown={(e) => {
            e.preventDefault();
            setIsResizing(true);
          }}
          className="w-1.5 h-full cursor-col-resize bg-border hover:bg-primary/40 transition-colors z-[50] group relative flex items-center justify-center flex-shrink-0"
          style={{ touchAction: 'none' }}
          title="Drag to resize sidebar"
        >
          <div className="w-0.5 h-32 bg-primary/30 group-hover:bg-primary/70 rounded-full transition-all duration-200" />
        </div>
      )}

      {/* Body */}
      <div
        // className={`bg-slate-800 h-screen flex-1 ${
          className={`bg-background h-screen flex-1 ${
          sidebarOpen ? "" : ""
        }`}
        // style={{
        //   minWidth: sidebarOpen ? `${bodyMinWidth}px` : '0px',
        // }}
        
      >
        <Body currentThread={currentThread} setThreads={setThreads} sidebarOpen={sidebarOpen} setThreadTitle={setThreadTitle}  addNewThread={addNewThread} setCurrentThread={setCurrentThread}/>
      </div>
    </div>
  );
};

export default Wrapper;



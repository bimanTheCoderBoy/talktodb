import React, { useState } from 'react';
import LayerManager from './LayerManager';
import CellsToggle from '../cells/CellsToggle';
import Legend from './Legend';
import PolygonDrawControl from './PolygonDrawControl';

//main sidebar contains everything rsrp layer, opacity, filter range etc; on/off sidebar
function ControlPanel() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          position: 'absolute',
          top: '20px',
          left: isCollapsed ? '20px' : '352px',
          width: '36px',
          height: '36px',
          background: isHovered ? 'var(--foreground)' : 'var(--bg-panel)',
          border: 'none',
          borderRadius: '8px',
          color: isHovered ? 'var(--background)' : 'var(--text-primary)',
          cursor: 'pointer',
          zIndex: 1001,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px color-mix(in oklch, var(--foreground) 12%, transparent)',
          transition:
            'left 0.3s ease, background 0.2s ease, color 0.2s ease',
        }}
        title={isCollapsed ? 'Show panel' : 'Hide panel'}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{
            transform: isCollapsed
              ? 'rotate(180deg)'
              : 'rotate(0deg)',
            transition: 'transform 0.3s ease',
          }}
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      {/* Control Panel */}
      <div 
        className="control-panel"
        style={{
          transform: isCollapsed ? 'translateX(-340px)' : 'translateX(0)',
          transition: 'transform 0.3s ease',
        }}
      >
        <div className="panel-header dark:bg-gradient-to-r dark:from-[#1d4a91] dark:to-[#0d172b] bg-gradient-to-r from-gray-100 to-white">
          <h1 className="font-bold bg-gradient-to-r from-foreground to-primary bg-clip-text text-transparent">
            raNora — Map Viewer
          </h1>
        </div>
        
        <div className="panel-content">
          <LayerManager />
          <CellsToggle />  
          <PolygonDrawControl/> 
          <Legend />  
        </div>
      </div>
    </>
  );
}

export default ControlPanel;

import React from 'react';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { useParams, useSearchParams } from 'react-router-dom';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { X, MoonIcon, SunIcon } from 'lucide-react';
import { serveDocUrl } from '@/lib/docRagAssetServeUrl';
import { useTheme } from 'next-themes';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';

const renderRange = ({ startPage, endPage, numPages }) => {
  const BUFFER = 5;
  return {
    startPage: Math.max(0, startPage - BUFFER),
    endPage: Math.min(numPages - 1, endPage + BUFFER),
  };
};

const DARK_STYLES = `
  .rpv-core__viewer { border: none !important; }
  .rpv-core__page-layer {
    box-shadow: 0 8px 30px rgba(0,0,0,0.5) !important;
  }
  .rpv-default-layout__toolbar {
    background-color: #0d172b !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
  }
  .rpv-default-layout__sidebar-headers {
    background-color: #0a0f1e !important;
  }
  .rpv-default-layout__sidebar-header-item--opened {
    border-bottom-color: #1d4a91 !important;
  }
  .rpv-default-layout__sidebar {
    background-color: #0d172b !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
  }
  .rpv-default-layout__body {
    background-color: #080c17 !important;
  }
  .rpv-core__inner-pages {
    background-color: #080c17 !important;
  }
  .rpv-core__minimal-button {
    color: #94a3b8 !important;
  }
  .rpv-core__minimal-button:hover {
    background-color: rgba(255,255,255,0.05) !important;
    color: #ffffff !important;
  }
  .rpv-core__minimal-button--selected {
    background-color: rgba(29,74,145,0.25) !important;
    color: #60a5fa !important;
  }
  .rpv-bookmark__title {
    color: #cbd5e1 !important;
  }
  .rpv-bookmark__title:hover {
    color: #ffffff !important;
  }
  .rpv-core__textbox {
    background-color: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e2e8f0 !important;
  }
  .rpv-core__popover-body {
    background-color: #0d172b !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e2e8f0 !important;
  }
  .rpv-core__tooltip-body {
    background-color: #1e293b !important;
    color: #f8fafc !important;
  }
  .rpv-core__menu-item {
    color: #cbd5e1 !important;
  }
  .rpv-core__menu-item:hover {
    background-color: rgba(255,255,255,0.05) !important;
  }
`;

const LIGHT_STYLES = `
  .rpv-core__page-layer {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important;
  }
  .rpv-default-layout__toolbar {
    background-color: #f8fafc !important;
    border-bottom: 1px solid #e2e8f0 !important;
  }
  .rpv-default-layout__sidebar-headers {
    background-color: #f1f5f9 !important;
  }
  .rpv-default-layout__sidebar-header-item--opened {
    border-bottom-color: #1d4a91 !important;
  }
  .rpv-default-layout__sidebar {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
  }
  .rpv-default-layout__body {
    background-color: #f1f5f9 !important;
  }
  .rpv-core__inner-pages {
    background-color: #f1f5f9 !important;
  }
  .rpv-core__minimal-button--selected {
    background-color: rgba(29,74,145,0.1) !important;
    color: #1d4a91 !important;
  }
`;

const PdfViewer = () => {
  const { file_name } = useParams();
  const fileUrl = serveDocUrl(file_name);
  const [searchParams] = useSearchParams();
  const pageNumber = searchParams.get('page');
  const initialPage = pageNumber ? parseInt(pageNumber)-1 : 1;
  const { theme ,setTheme} = useTheme();
  const [isDarkMode, setIsDarkMode] = React.useState(theme=='dark');

  const renderToolbar = (Toolbar) => (
    <Toolbar>
      {(slots) => {
        const {
          CurrentPageInput,
          GoToNextPage,
          GoToPreviousPage,
          NumberOfPages,
          Zoom,
          ZoomIn,
          ZoomOut,
          EnterFullScreen,
          Download,
          Print,
        } = slots;

        return (
          <div
            className={`flex items-center justify-between w-full px-2 sm:px-4 py-1 gap-1 sm:gap-2 flex-wrap sm:flex-nowrap ${
              isDarkMode
                ? 'bg-[#0d172b] border-b border-white/10'
                : 'bg-[#f8fafc] border-b border-slate-200'
            }`}
          >
            {/* Left: File info + Nav */}
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              <div
                className={`hidden md:flex items-center gap-2.5 shrink-0 pr-4 border-r h-8 ${
                  isDarkMode ? 'border-white/10' : 'border-slate-200'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded flex items-center justify-center border ${
                    isDarkMode
                      ? 'bg-teoco-real-blue/20 border-teoco-real-blue/30'
                      : 'bg-teoco-real-blue/10 border-teoco-real-blue/20'
                  }`}
                >
                  <svg className="w-3.5 h-3.5 text-teoco-real-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="overflow-hidden">
                  <h1
                    className={`text-xs font-semibold truncate max-w-[200px] ${
                      isDarkMode ? 'text-slate-200' : 'text-slate-700'
                    }`}
                  >
                    {file_name}
                  </h1>
                  <p className="text-[8px] text-slate-500  tracking-widest">
                    raNora PDF Viewer
                  </p>
                </div>
              </div>

              <div className={`flex items-center gap-0.5 sm:gap-1 ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
                <GoToPreviousPage />
                <div
                  className={`flex items-center gap-0.5 sm:gap-1 px-1.5 sm:px-2 py-0.5 rounded border text-xs ${
                    isDarkMode
                      ? 'bg-white/5 border-white/10'
                      : 'bg-slate-100 border-slate-200'
                  }`}
                >
                  <CurrentPageInput />
                  <span className="text-slate-400">/</span>
                  <NumberOfPages />
                </div>
                <GoToNextPage />
              </div>
            </div>

            {/* Center: Zoom */}
            <div
              className={`flex items-center gap-0.5 sm:gap-1 px-1.5 sm:px-2 py-0.5 rounded-full border ${
                isDarkMode ? 'bg-white/5 border-white/10' : 'bg-slate-100 border-slate-200'
              }`}
            >
              <ZoomOut />
              <div className={`w-10 sm:w-14 text-center text-[11px] font-medium ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
                <Zoom />
              </div>
              <ZoomIn />
            </div>

            {/* Right: Actions + Close */}
            <div className={`flex items-center gap-0.5 sm:gap-1 ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
              <div className="hidden sm:block"><EnterFullScreen /></div>
              <div className={`hidden sm:block w-px h-4 mx-0.5 ${isDarkMode ? 'bg-white/10' : 'bg-slate-200'}`} />
              <Download />
              <div className="hidden sm:block"><Print /></div>
              <button
                onClick={() => {setIsDarkMode(!isDarkMode);setTheme(theme === 'dark' ? 'light' : 'dark')}}
                className={`p-1.5 rounded transition-colors cursor-pointer ${
                  isDarkMode
                    ? 'hover:text-yellow-300 hover:bg-yellow-500/10'
                    : 'hover:text-indigo-600 hover:bg-indigo-50'
                }`}
                title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              >
                {isDarkMode ? <SunIcon className="w-4 h-4" /> : <MoonIcon className="w-4 h-4" />}
              </button>
              <div className={`w-px h-5 mx-0.5 sm:mx-1 ${isDarkMode ? 'bg-white/10' : 'bg-slate-200'}`} />
              <button
                onClick={() => window.close()}
                className={`p-1.5 rounded transition-colors ${
                  isDarkMode
                    ? 'hover:text-red-400 hover:bg-red-500/20'
                    : 'hover:text-red-600 hover:bg-red-50'
                }`}
                title="Close Viewer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        );
      }}
    </Toolbar>
  );

  const defaultLayoutPluginInstance = defaultLayoutPlugin({
    renderToolbar,
    sidebarTabs: (defaultTabs) => [
      defaultTabs[0],
      defaultTabs[1],
    ],
  });

  return (
    <div style={{ height: '100vh', width: '100%' }}>
      <style>{isDarkMode ? DARK_STYLES : LIGHT_STYLES}</style>
      <Worker workerUrl="/pdf.worker.min.js">
        <Viewer
          fileUrl={fileUrl}
          setRenderRange={renderRange}
          defaultScale={2}
          initialPage={initialPage}
          plugins={[defaultLayoutPluginInstance]}
          theme={isDarkMode ? 'dark' : 'light'}
        />
      </Worker>
    </div>
  );
};

export default PdfViewer;

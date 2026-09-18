import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

// Initialize mermaid with configuration matching TEOCO theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  themeVariables: {
    primaryColor: '#1d4a91',
    primaryTextColor: '#fff',
    primaryBorderColor: '#1d4a91',
    lineColor: '#1d4a91',
    secondaryColor: '#0d172b',
    tertiaryColor: '#1d4a91',
    background: '#0d172b',
    mainBkg: '#1d4a91',
    secondBkg: '#0d172b',
    textColor: '#fff',
    nodeBorder: '#1d4a91',
    clusterBkg: '#0d172b',
    clusterBorder: '#1d4a91',
    edgeLabelBackground: '#0d172b',
  }
});

/**
 * MermaidDiagram component renders Mermaid diagrams from code strings
 * @param {Object} props
 * @param {string} props.chart - The mermaid diagram code
 * @param {string} props.className - Optional additional CSS classes
 */
export const MermaidDiagram = ({ chart, className = '' }) => {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current && chart) {
      try {
        // Generate unique ID for each diagram instance
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        
        // Render the mermaid diagram
        mermaid.render(id, chart).then(({ svg }) => {
          if (ref.current) {
            ref.current.innerHTML = svg;
          }
        }).catch((error) => {
          console.error('Mermaid rendering error:', error);
          if (ref.current) {
            ref.current.innerHTML = `<pre class="text-red-500 p-4">Error rendering diagram: ${error.message}</pre>`;
          }
        });
      } catch (error) {
        console.error('Mermaid rendering error:', error);
        if (ref.current) {
          ref.current.innerHTML = `<pre class="text-red-500 p-4">Error rendering diagram: ${error.message}</pre>`;
        }
      }
    }
  }, [chart]);

  return (
    <div className={`my-4 p-4 bg-slate-900/50 border border-teoco-real-blue/30 rounded-lg overflow-x-auto ${className}`}>
      <div ref={ref} className="flex justify-center items-center" />
    </div>
  );
};

MermaidDiagram.displayName = 'MermaidDiagram';


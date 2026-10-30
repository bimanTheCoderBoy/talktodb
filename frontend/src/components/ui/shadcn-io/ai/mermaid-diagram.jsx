import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

// Mermaid theme aligned with talkToDB (teal / slate)
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  themeVariables: {
    primaryColor: '#0d9488',
    primaryTextColor: '#f0fdfa',
    primaryBorderColor: '#14b8a6',
    lineColor: '#2dd4bf',
    secondaryColor: '#141a22',
    tertiaryColor: '#134e4a',
    background: '#0c1015',
    mainBkg: '#0d9488',
    secondBkg: '#141a22',
    textColor: '#e2e8f0',
    nodeBorder: '#14b8a6',
    clusterBkg: '#141a22',
    clusterBorder: '#2dd4bf',
    edgeLabelBackground: '#0c1015',
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
    <div className={`my-4 p-4 bg-card/80 border border-border rounded-lg overflow-x-auto ${className}`}>
      <div ref={ref} className="flex justify-center items-center" />
    </div>
  );
};

MermaidDiagram.displayName = 'MermaidDiagram';


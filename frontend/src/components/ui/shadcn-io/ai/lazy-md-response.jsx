'use client';
import React, { memo, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { CodeBlock, CodeBlockCopyButton } from './code-block';
import { MermaidDiagram } from './mermaid-diagram';
import 'katex/dist/katex.min.css';

import { useInView } from 'react-intersection-observer';
import { useVirtualizer } from '@tanstack/react-virtual';

// --- LAZY LOADING WRAPPER ---
const LazyBlock = ({ children, minHeight = "150px" }) => {
  const { ref, inView } = useInView({ triggerOnce: true, rootMargin: '400px 0px' });
  return (
    <div ref={ref} style={{ minHeight }} className="w-full relative">
      {inView ? children : (
        <div className="w-full h-full min-h-[150px] bg-muted/20 animate-pulse rounded-md flex items-center justify-center text-muted-foreground text-sm border border-border">
          Loading heavy content...
        </div>
      )}
    </div>
  );
};

// --- HAST VIRTUALIZED TABLE ---
const VirtualizedTable = ({ tableNode, className }) => {
  const containerRef = useRef(null);
  
  const theadNode = tableNode.children?.find(child => child.tagName === 'thead');
  const tbodyNode = tableNode.children?.find(child => child.tagName === 'tbody');
  
  const rows = tbodyNode ? tbodyNode.children.filter(child => child.tagName === 'tr') : [];
  const headerRow = theadNode?.children?.find(child => child.tagName === 'tr');
  const firstBodyRow = rows[0];
  const columnCount = Math.max(
    1,
    (headerRow?.children?.filter(child => child.tagName === 'th').length) ||
      (firstBodyRow?.children?.filter(child => child.tagName === 'td').length) ||
      1
  );

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 45,
    overscan: 10,
  });

  if (rows.length <= 10) {
    return (
      <div className="my-4 overflow-x-auto">
        <table className={cn('w-max min-w-full border-collapse border border-border', className)}>
          {renderHastNode(theadNode, 0)}
          {renderHastNode(tbodyNode, 1)}
        </table>
      </div>
    );
  }

  const virtualItems = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end
    : 0;

  return (
    <div ref={containerRef} className="my-4 max-h-[500px] overflow-y-auto overflow-x-auto border border-border rounded-md relative custom-scrollbar">
      <table className={cn('w-max min-w-full border-collapse border-0', className)}>
        {renderHastNode(theadNode, 0)}
        <tbody className="divide-y divide-border">
          {paddingTop > 0 && <tr><td style={{ height: `${paddingTop}px` }} colSpan={columnCount} className="p-0 border-0" /></tr>}
          
          {virtualItems.map((virtualRow) => (
            <React.Fragment key={virtualRow.key}>
              {renderHastNode(rows[virtualRow.index], virtualRow.index)}
            </React.Fragment>
          ))}
          
          {paddingBottom > 0 && <tr><td style={{ height: `${paddingBottom}px` }} colSpan={columnCount} className="p-0 border-0" /></tr>}
        </tbody>
      </table>
    </div>
  );
};

// --- HAST RECURSIVE RENDERER ---
const VOID_ELEMENTS = new Set([
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'link',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
]);

const TABLE_STRUCTURE_TAGS = new Set(['table', 'thead', 'tbody', 'tfoot', 'tr']);

const isWhitespaceTextNode = (n) =>
  n?.type === 'text' && typeof n.value === 'string' && n.value.trim() === '';

const renderHastNode = (node, index = 0) => {
  if (!node) return null;
  
  if (node.type === 'text') {
    return <React.Fragment key={index}>{node.value}</React.Fragment>;
  }

  if (node.type === 'element') {
    const rawChildren = Array.isArray(node.children) ? node.children : [];
    // React table elements (thead/tr/...) cannot have whitespace text children.
    const filteredChildren =
      TABLE_STRUCTURE_TAGS.has(node.tagName)
        ? rawChildren.filter((c) => !isWhitespaceTextNode(c))
        : rawChildren;

    const children = filteredChildren.map((child, i) => renderHastNode(child, i));
    const props = node.properties ?? {};
    // HAST `className` is often an array — normalize it for React.
    // Also avoid letting a raw (array) className override our normalized string.
    // eslint-disable-next-line no-unused-vars
    const { className: _rawClassName, ...restProps } = props;
    const className = _rawClassName ? [].concat(_rawClassName).join(' ') : '';

    switch (node.tagName) {
      case 'p': return <p key={index} className={cn("mb-4", className)}>{children}</p>;
      case 'h1': return <h1 key={index} className={cn('mt-6 mb-2 font-semibold text-3xl', className)}>{children}</h1>;
      case 'h2': return <h2 key={index} className={cn('mt-6 mb-2 font-semibold text-2xl', className)}>{children}</h2>;
      case 'h3': return <h3 key={index} className={cn('mt-6 mb-2 font-semibold text-xl', className)}>{children}</h3>;
      case 'h4': return <h4 key={index} className={cn('mt-6 mb-2 font-semibold text-lg', className)}>{children}</h4>;
      case 'h5': return <h5 key={index} className={cn('mt-6 mb-2 font-semibold text-base', className)}>{children}</h5>;
      case 'h6': return <h6 key={index} className={cn('mt-6 mb-2 font-semibold text-sm', className)}>{children}</h6>;
      case 'ul': return <ul key={index} className={cn('ml-4 list-outside list-disc mb-4', className)}>{children}</ul>;
      case 'ol': return <ol key={index} className={cn('ml-4 list-outside list-decimal mb-4', className)}>{children}</ol>;
      case 'li': return <li key={index} className={cn('py-1', className)}>{children}</li>;
      case 'a': return <a key={index} href={node.properties?.href} className={cn('font-medium text-primary underline', className)} target="_blank" rel="noreferrer">{children}</a>;
      case 'strong': return <strong key={index} className={cn('font-semibold', className)}>{children}</strong>;
      case 'em': return <em key={index} className="italic">{children}</em>;
      case 'del': return <del key={index} className="line-through">{children}</del>;
      case 'blockquote': return <blockquote key={index} className={cn('my-4 border-muted-foreground/30 border-l-4 pl-4 text-muted-foreground italic', className)}>{children}</blockquote>;
      case 'hr': return <hr key={index} className={cn('my-6 border-border', className)} />;
      case 'br': return <br key={index} {...restProps} className={className} />;
      
      case 'table': return <VirtualizedTable key={index} tableNode={node} className={className} />;
      case 'thead': return <thead key={index} className={cn('bg-muted/50 sticky top-0 z-10 shadow-sm backdrop-blur-sm', className)}>{children}</thead>;
      case 'tbody': return <tbody key={index} className={cn('divide-y divide-border', className)}>{children}</tbody>;
      case 'tr': return <tr key={index} className={cn('border-border border-b hover:bg-muted/5 transition-colors', className)}>{children}</tr>;
      case 'th': return <th key={index} className={cn('px-4 py-3 text-left font-semibold text-sm bg-muted/50 whitespace-nowrap break-normal', className)}>{children}</th>;
      case 'td': return <td key={index} className={cn('px-4 py-2 text-sm whitespace-nowrap break-normal max-w-[300px] truncate hover:whitespace-normal hover:wrap-break-word', className)}>{children}</td>;
      case 'img': {
        let src = props.src || '';
        if (!src.startsWith('http') && !src.startsWith('/')) {
          src = `/${src.replace(/^\.?\//, '')}`;
        }
        return (
          <img 
            key={index} 
            src={src} 
            alt={node.properties?.alt || 'Image'} 
            className={cn('my-4 max-w-full h-auto rounded-md border border-border', className)}
            loading="lazy"
          />
        );
      }
      case 'code': {
        const isInline = !className.includes('language-');
        if (isInline) return <code key={index} className={cn('rounded bg-muted px-1.5 py-0.5 font-mono text-sm', className)}>{children}</code>;
        return <code key={index} className={className}>{children}</code>;
      }

      case 'pre': {
        const codeNode = node.children?.find(c => c.tagName === 'code');
        const rawCodeText = codeNode?.children?.find(c => c.type === 'text')?.value || '';
        
        let language = 'javascript';
        const codeClassName = codeNode?.properties?.className ? [].concat(codeNode.properties.className).join(' ') : '';
        if (codeClassName.includes('language-')) {
          language = codeClassName.replace('language-', '').split(' ')[0];
        }

        if (language !== 'mermaid' && rawCodeText) {
          const trimmedCode = rawCodeText.trim();
          const mermaidPatterns = [/^graph\s+/i, /^sequenceDiagram/i, /^classDiagram/i, /^stateDiagram/i, /^erDiagram/i, /^journey/i, /^gantt/i, /^pie/i, /^flowchart/i, /^gitGraph/i, /^mindmap/i, /^timeline/i];
          if (mermaidPatterns.some(pattern => pattern.test(trimmedCode))) language = 'mermaid';
        }

        if (language === 'mermaid') {
          return (
            <LazyBlock key={index} minHeight="300px">
              <MermaidDiagram chart={rawCodeText} className={className} />
            </LazyBlock>
          );
        }

        return (
          <LazyBlock key={index} minHeight="150px">
            <CodeBlock className={cn('my-4 h-auto', className)} code={rawCodeText} language={language}>
              <CodeBlockCopyButton
                onCopy={() => console.log('Copied code to clipboard')}
                onError={() => console.error('Failed to copy code to clipboard')} />
            </CodeBlock>
          </LazyBlock>
        );
      }
      
      default: {
        const Tag = node.tagName;
        if (VOID_ELEMENTS.has(node.tagName)) {
          return <Tag key={index} {...restProps} className={className} />;
        }
        return <Tag key={index} {...restProps} className={className}>{children}</Tag>;
      }
    }
  }
  
  
  if (node.type === 'root') {
    return <>{node.children?.map((child, i) => renderHastNode(child, i))}</>;
  }

  return null;
};

export const LazyMDResponse = memo(({
  className,
  children,
  parseIncompleteMarkdown: _parseIncompleteMarkdown = true,
  ...props
}) => {
  const [hast, setHast] = useState(null);
  const workerRef = useRef(null);

  useEffect(() => {
    workerRef.current = new Worker(new URL('./markdown.worker.js', import.meta.url), {
      type: 'module',
    });

    workerRef.current.onmessage = (e) => {
      if (e.data.type === 'SUCCESS') {
        console.log("HAST",e.data.payload);
        setHast(e.data.payload);
      } else {
        console.error("Worker Parsing Error:", e.data.payload);
      }
    };

    return () => {
      workerRef.current?.terminate();
    };
  }, []);

  useEffect(() => {
    if (workerRef.current && typeof children === 'string') {
      workerRef.current.postMessage(children);
    }
  }, [children]);

  return (
    <div className={cn('w-full min-w-0 wrap-anywhere [&>*:first-child]:mt-0 [&>*:last-child]:mb-0', className)} {...props}>
      {hast ? renderHastNode(hast) : (
        <div role="status" aria-live="polite" className="py-2 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/30" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary/60" />
            </span>
            <span>Rendering response…</span>
          </div>

          <div className="space-y-2">
            <div className="h-3 w-11/12 rounded bg-muted/40 animate-pulse" />
            <div className="h-3 w-8/12 rounded bg-muted/30 animate-pulse" />
            <div className="h-3 w-10/12 rounded bg-muted/30 animate-pulse" />
          </div>
        </div>
      )}
    </div>
  );
}, (prevProps, nextProps) => prevProps.children === nextProps.children);

LazyMDResponse.displayName = 'LazyMDResponse';


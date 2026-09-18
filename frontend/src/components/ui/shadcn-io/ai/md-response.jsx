'use client';
import React, { isValidElement, memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';


import { cn } from '@/lib/utils';

const CODE_HIGHLIGHT_CLASS =
  'rounded-md bg-foreground/10 px-1.5 py-0.5 font-mono text-[0.9em] text-foreground ring-1 ring-inset ring-foreground/15';

const toMarkdownString = (children) => {
  if (typeof children === 'string') return children;
  if (typeof children === 'number') return String(children);
  if (children == null) return '';
  if (isValidElement(children)) return null;
  return String(children);
};

function replaceCitations(text, citationMap) {
  if (!text || !citationMap) return text;
  return text.replace(/<C>(.*?)<\/C>/g, (_match, id) => {
   
    const cite = citationMap[id.trim()];
    if (!cite) return id;
    
    const label = `[${(cite.doc_title || 'Source').substring(0, 8) + '..'}(${cite.page_start || 1})]`;
    const file = (cite.source_file || '');
    const page = cite.page_start ?? '';
    const href = `/pdf/${encodeURIComponent(file)}?page=${page}`;
    return `[${label}](${href})`;
  });
}

export const MDResponse = memo(({ className, children, citationMap, ...props }) => {
  const rawText = toMarkdownString(children);
  const text = useMemo(() => replaceCitations(rawText, citationMap), [rawText, citationMap]);

  if (text === null) {
    return (
      <div className={cn('w-full min-w-0 wrap-anywhere', className)} {...props}>
        {children}
      </div>
    );
  }

  return (
    <div className={cn('w-full min-w-0 wrap-anywhere', className)} {...props}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          h1: ({ children }) => (
            <h1 className="mt-6 mb-2 font-semibold text-2xl">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-6 mb-2 font-semibold text-xl">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-6 mb-2 font-semibold text-lg">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-6 mb-2 font-semibold text-base">{children}</h4>
          ),
          ul: ({ children }) => (
            <ul className="ml-4 list-outside list-disc mb-4">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="ml-4 list-outside list-decimal mb-4">{children}</ol>
          ),
          li: ({ children }) => <li className="py-1">{children}</li>,
          a: ({ children, href }) => (
            <a
              href={href}
              className="font-medium text-primary underline"
              target="_blank"
              rel="noreferrer"
              title="View in PDF"
              style={{ cursor: 'pointer' }}
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-muted-foreground/30 border-l-4 pl-4 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto">
              <table className="w-max min-w-full border-collapse border border-border">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-muted/50">{children}</thead>
          ),
          tbody: ({ children }) => <tbody className="divide-y divide-border">{children}</tbody>,
          tr: ({ children }) => (
            <tr className="border-border border-b hover:bg-muted/5 transition-colors">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 text-left font-semibold text-sm bg-muted/50 whitespace-nowrap break-normal">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-2 text-sm whitespace-nowrap break-normal max-w-[300px] truncate hover:whitespace-normal hover:break-words">
              {children}
            </td>
          ),
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children }) => {
            const raw = String(children ?? '');
            const code = raw.endsWith('\n') ? raw.slice(0, -1) : raw;
            const isBlock =
              /language-/.test(className || '') || code.includes('\n');

            if (!isBlock) {
              return <code className={CODE_HIGHLIGHT_CLASS}>{children}</code>;
            }

            return (
              <code
                className={cn(
                  CODE_HIGHLIGHT_CLASS,
                  'my-2 block w-fit max-w-full whitespace-pre-wrap break-words px-2.5 py-1.5',
                  className
                )}
              >
                {code}
              </code>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}, (prev, next) => prev.children === next.children && prev.className === next.className && prev.citationMap === next.citationMap);

MDResponse.displayName = 'MDResponse';
export default MDResponse;


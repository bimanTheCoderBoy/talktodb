/**
 * Copyright 2023 Vercel, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

'use client';;
import { useControllableState } from '@radix-ui/react-use-controllable-state';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import { BrainIcon, ChevronDownIcon } from 'lucide-react';
import { createContext, memo, useContext, useCallback, useEffect, useRef, useState } from 'react';
import { MDResponse } from './md-response';

import { THINKING_WORDS } from '@/components/streaming-chat/thinkingWords';

const useRotatingWord = (isActive) => {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * THINKING_WORDS.length));
  const intervalRef = useRef(null);

  useEffect(() => {
    if (isActive) {
      intervalRef.current = setInterval(() => {
        setIndex((prev) => (prev + 1) % THINKING_WORDS.length);
      }, 60000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isActive]);

  return THINKING_WORDS[index];
};

const ReasoningContext = createContext(null);

const useReasoning = () => {
  const context = useContext(ReasoningContext);
  if (!context) {
    throw new Error('Reasoning components must be used within Reasoning');
  }
  return context;
};

const AUTO_CLOSE_DELAY = 1000;

export const Reasoning = memo(({
  className,
  isStreaming = false,
  open,
  defaultOpen = false,
  onOpenChange,
  duration: durationProp,
  children,
  ...props
}) => {
  const [isOpen, setIsOpen] = useControllableState({
    prop: open,
    defaultProp: defaultOpen,
    onChange: onOpenChange,
  });
  const [duration, setDuration] = useControllableState({
    prop: durationProp,
    defaultProp: 0,
  });

  const [hasAutoClosedRef, setHasAutoClosedRef] = useState(false);
  const [startTime, setStartTime] = useState(null);

  // Track duration when streaming starts and ends
  useEffect(() => {
    if (isStreaming) {
      if (startTime === null) {
        setStartTime(Date.now());
      }
    } else if (startTime !== null) {
      setDuration(Math.round((Date.now() - startTime) / 1000));
      setStartTime(null);
    }
  }, [isStreaming, startTime, setDuration]);

  // Auto-open when streaming starts, auto-close when streaming ends (once only)
  useEffect(() => {
    if (isStreaming && !isOpen) {
      setIsOpen(true);
    } else if (!isStreaming && isOpen && !defaultOpen && !hasAutoClosedRef) {
      // Add a small delay before closing to allow user to see the content
      const timer = setTimeout(() => {
        setIsOpen(false);
        setHasAutoClosedRef(true);
      }, AUTO_CLOSE_DELAY);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, isOpen, defaultOpen, setIsOpen, hasAutoClosedRef]);

  const handleOpenChange = (newOpen) => {
    setIsOpen(newOpen);
  };

  return (
    <ReasoningContext.Provider value={{ isStreaming, isOpen, setIsOpen, duration }}>
      <Collapsible
        className={cn('not-prose mb-4', className)}
        onOpenChange={handleOpenChange}
        open={isOpen}
        {...props}>
        {children}
      </Collapsible>
    </ReasoningContext.Provider>
  );
});

export const ReasoningTrigger = memo(({
  className,
  title = 'Reasoning',
  children,
  ...props
}) => {
  const { isStreaming, isOpen, duration } = useReasoning();
  const thinkingWord = useRotatingWord(isStreaming || duration === 0);

  return (
    <CollapsibleTrigger
      className={cn('flex items-center gap-2 text-muted-foreground text-sm', className)}
      {...props}>
      {children ?? (
        <>
          <BrainIcon className="size-4" />
          {isStreaming || duration === 0 ? (
            <p className="transition-opacity duration-300">{thinkingWord}...</p>
          ) : (
            <p>Thought for {duration} seconds</p>
          )}
          <ChevronDownIcon
            className={cn(
              'size-4 text-muted-foreground transition-transform',
              isOpen ? 'rotate-180' : 'rotate-0'
            )} />
        </>
      )}
    </CollapsibleTrigger>
  );
});

export const ReasoningContent = memo(({
  className,
  children,
  ...props
}) => (
  <CollapsibleContent
    className={cn(
      'mt-4 text-sm',
      'data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2  outline-none data-[state=closed]:animate-out data-[state=open]:animate-in text-gray-500',
      className
    )}
    {...props}>
    <MDResponse className="grid gap-2">{children}</MDResponse>
  </CollapsibleContent>
));

Reasoning.displayName = 'Reasoning';
ReasoningTrigger.displayName = 'ReasoningTrigger';
ReasoningContent.displayName = 'ReasoningContent';

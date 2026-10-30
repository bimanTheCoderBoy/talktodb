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
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { ArrowUp, Loader2Icon, SquareIcon, XIcon } from 'lucide-react';
import { Children } from 'react';



export const PromptInput = ({
  className,
  ...props
}) => (
  <form
    className={cn(
      'flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-full border bg-card px-4 py-1.5 shadow-lg',
      className
    )}
    {...props} />
);

export const PromptInputTextarea = ({
  onChange,
  className,
  placeholder = 'What would you like to know?',
  minHeight = 48,
  maxHeight = 164,
  ...props
}) => {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        // Allow newline
        return;
      }

      // Submit on Enter (without Shift)
      e.preventDefault();
      const form = e.currentTarget.form;
      if (form) {
        form.requestSubmit();
      }
    }
  };

  return (
    <Textarea
      rows={1}
      className={cn(
        'min-h-0 h-10 max-h-28 flex-1 resize-none rounded-none border-none bg-transparent px-0 py-2 shadow-none outline-none ring-0',
        'text-sm leading-normal field-sizing-content',
        'focus-visible:ring-0 focus-visible:ring-offset-0',
        className
      )}
      name="message"
      onChange={(e) => {
        onChange?.(e);
      }}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      {...props} />
  );
};

export const PromptInputToolbar = ({
  className,
  ...props
}) => (
  <div
    className={cn('flex shrink-0 items-center p-0', className)}
    {...props} />
);

export const PromptInputTools = ({
  className,
  ...props
}) => (
  <div
    className={cn(
      'flex items-center gap-1',
      '[&_button:first-child]:rounded-bl-xl',
      className
    )}
    {...props} />
);

export const PromptInputButton = ({
  variant = 'ghost',
  className,
  size,
  ...props
}) => {
  const newSize =
    (size ?? Children.count(props.children) > 1) ? 'default' : 'icon';

  return (
    <Button
      className={cn(
        'shrink-0 gap-1.5 rounded-lg',
        variant === 'ghost' && 'text-muted-foreground',
        newSize === 'default' && 'px-3',
        className
      )}
      size={newSize}
      type="button"
      variant={variant}
      {...props} />
  );
};

export const PromptInputSubmit = ({
  className,
  variant = 'default',
  size = 'icon',
  status,
  children,
  ...props
}) => {
  let Icon = <ArrowUp className="size-4" strokeWidth={2.5} />;

  if (status === 'submitted') {
    Icon = <Loader2Icon className="size-4 animate-spin" />;
  } else if (status === 'streaming') {
    Icon = <SquareIcon className="size-3.5" />;
  } else if (status === 'error') {
    Icon = <XIcon className="size-4" />;
  }

  return (
    <Button
      className={cn(
        'size-9 shrink-0 rounded-full p-0',
        status === 'submitted' && 'hover:bg-red-400/30 duration-200 transition-all',
        className
      )}
      size={size}
      type="submit"
      variant={variant}
      {...props}>
      {children ?? Icon}
    </Button>
  );
};

export const PromptInputModelSelect = (props) => (
  <Select {...props} />
);

export const PromptInputModelSelectTrigger = ({
  className,
  ...props
}) => (
  <SelectTrigger
    className={cn(
      'border-none bg-transparent font-medium text-muted-foreground shadow-none transition-colors',
      'hover:bg-accent hover:text-foreground [&[aria-expanded="true"]]:bg-accent [&[aria-expanded="true"]]:text-foreground',
      className
    )}
    {...props} />
);

export const PromptInputModelSelectContent = ({
  className,
  ...props
}) => (
  <SelectContent className={cn(className)} {...props} />
);

export const PromptInputModelSelectItem = ({
  className,
  ...props
}) => (
  <SelectItem className={cn(className)} {...props} />
);

export const PromptInputModelSelectValue = ({
  className,
  ...props
}) => (
  <SelectValue className={cn(className)} {...props} />
);


const TeocoPromptInputLoader = () => {
  return (
    <div className="h-full w-full">
      {/* Injecting Styles Locally for Portability */}
      <style>{`
        /* Perimeter is approx 360 units. */
        @keyframes continuous-flow {
          from { 
            stroke-dashoffset: 360; 
          }
          to { 
            stroke-dashoffset: 0; 
          }
        }
        
        .animate-smooth-flow {
          stroke-linecap: round;
          /* 
             Fixed dash array: 90px dash, 270px gap.
             Keeps the stroke length constant for a smooth loop.
          */
          stroke-dasharray: 90 270; 
          
          /* 
             Key changes:
             1. 'linear' removes the "stop" pause at start/end.
             2. '1.5s' adjusts speed (1s might be too fast for linear).
          */
          animation: continuous-flow 1s linear infinite;
        }
      `}</style>

      <div className={`relative scale-200  translate-x-[55%]  translate-y-[55%]`}>
        {/* Main SVG Container */}
        <svg  
          viewBox="0 0 200 200" 
          xmlns="http://www.w3.org/2000/svg" 
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Background Triangle */}
          <polygon
            points="100,168 41,66 159,66"
            fill="none"
            stroke="white"
            strokeWidth="25"
            strokeLinejoin="round"
          />
        </svg>
        
        {/* LAYER 2: Animation Overlay */}
        <svg 
          viewBox="0 0 200 200" 
          xmlns="http://www.w3.org/2000/svg" 
          className="absolute inset-0"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* The Smooth Continuous Stroke */}
          <polygon
            points="100,168 41,66 159,66"
            fill="none"
            stroke="#334155" 
            strokeWidth="18" 
            strokeLinejoin="round"
            className="animate-smooth-flow"
          />
        </svg>
      </div>
    </div>
  );
};

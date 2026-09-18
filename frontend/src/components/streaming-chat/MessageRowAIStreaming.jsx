import React from "react";
import {
  Reasoning,
} from "@/components/ui/shadcn-io/ai/reasoning";
import { useEffect, useRef } from "react";


export default function MessageRowAIStreaming({ message }) {
  const liveReasoning =
    message.additional_kwargs?.reasoning && message.additional_kwargs?.reasoning !== ""
      ? message.additional_kwargs.reasoning
      : typeof message.content === "string"
      ? message.content
      : JSON.stringify(message.content, null, 2);



      const reasoningRef = useRef(null);
      
      useEffect(() => {
        if (reasoningRef.current) {
          reasoningRef.current.scrollTop = reasoningRef.current.scrollHeight;
        }
      }, [liveReasoning]);


  if (!liveReasoning) {
    return null;
  }
  return (
    <Reasoning isStreaming={true}>
      <h3 className="text-sm text-muted-foreground font-bold animate-pulse">
        Agent Reasoning...🧠
      </h3>
      <div ref={reasoningRef} className="mt-2 text-sm text-muted-foreground max-h-[300px] overflow-y-auto opacity-60 whitespace-pre-wrap wrap-break-word">
        {liveReasoning}
      </div>
    </Reasoning>
  );
}

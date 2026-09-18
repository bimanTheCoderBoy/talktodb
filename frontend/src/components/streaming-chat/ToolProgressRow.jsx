import React from "react";
import {
  Reasoning,
  ReasoningContent,
} from "@/components/ui/shadcn-io/ai/reasoning";

const ToolProgressRow = React.memo(function ToolProgressRow({
  step,
  message,
}) {
  return (
    <div className="w-full max-w-6xl min-w-0">
      <Reasoning isStreaming={true}>
        <h3 className="text-sm text-muted-foreground font-bold animate-pulse">
          Agent Tool Calling Progress...🔧
        </h3>
        <ReasoningContent className="text-sm text-muted-foreground opacity-60">
          {`Step ${step} - ${message}`}
        </ReasoningContent>
      </Reasoning>
    </div>
  );
});

export default ToolProgressRow;

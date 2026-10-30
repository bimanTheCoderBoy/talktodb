import React, { useState } from "react";
import { Copy, Eye, EyeOff } from "lucide-react";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolOutput,
} from "@/components/ui/shadcn-io/ai/tool";
import { LazyMDResponse } from "@/components/ui/shadcn-io/ai/lazy-md-response";
import { Button } from "../ui/button";
import { getToolDisplayName } from "@/constants/toolUi";

const ToolResultCard = ({ message, onCopy }) => {
  const toolName = message?.name;
  const displayName = getToolDisplayName(toolName);
  const contentText =
    typeof message?.content === "string"
      ? message.content
      : JSON.stringify(message?.content, null, 2);
  const [open, setOpen] = useState(false);

  return (
    <Tool
      defaultOpen={false}
      open={open}
      onOpenChange={setOpen}
      className="w-full max-w-full min-w-0 bg-secondary/60 border border-border"
    >
      <span className="cursor-pointer">
        <ToolHeader state={message?.status} type={displayName} />
      </span>
      <ToolContent className="w-full min-w-0">
        <ToolOutput
          className="max-w-full"
          output={
            <div className="p-4 min-w-0">
              <LazyMDResponse className="min-w-0 wrap-anywhere">{contentText}</LazyMDResponse>
            </div>
          }
        />
        <div className="flex items-end justify-end pb-3 gap-2 min-w-full">
          <Button variant="outline" size="icon" className="cursor-pointer" onClick={() => setOpen(!open)} type="button">
            {open ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="cursor-pointer"
            onClick={() => onCopy?.(message?.content)}
            type="button"
            title="Copy tool output"
          >
            <Copy className="w-4 h-4" />
          </Button>
        </div>
      </ToolContent>
    </Tool>
  );
};

export default ToolResultCard;

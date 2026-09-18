import React from "react";
import { Message, MessageContent } from "@/components/ui/shadcn-io/ai/message";
import { MDResponse } from "@/components/ui/shadcn-io/ai/md-response";
import { Copy } from "lucide-react";
import fembotIcon from "@/asset/fembot-icon.svg";
import { Button } from "../ui/button";

const MessageRowAI = React.memo(function MessageRowAI({ message, onCopy, citationMap }) {
  return (
    <Message from="ai" className="w-full min-w-0">
      <div className="size-8 rounded-full bg-gradient-to-br from-teoco-real-blue to-teoco-navy-blue flex items-center justify-center ring-2 ring-teoco-real-blue/30">
        <img
          src={fembotIcon}
          alt="Assistant"
          className="w-5 h-5 object-contain"
        />
      </div>
      <MessageContent className="min-w-0">
        <MDResponse className="min-w-0 wrap-anywhere" citationMap={citationMap}>
          {typeof message.content === "string"
            ? message.content
            : JSON.stringify(message.content, null, 2)}
        </MDResponse>
        {message.name != null && message.name !== "IGNORE" && (
          <div className="flex justify-end items-end gap-2">
            <Button
              variant="outline"
              size="icon"
              className="cursor-pointer"
              onClick={() => onCopy(message.content)}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        )}
      </MessageContent>
    </Message>
  );
});

export default MessageRowAI;

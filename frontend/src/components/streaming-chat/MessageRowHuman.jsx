import React from "react";
import { Message, MessageContent } from "@/components/ui/shadcn-io/ai/message";
import { MDResponse } from "@/components/ui/shadcn-io/ai/md-response";
import { User } from "lucide-react";

const MessageRowHuman = React.memo(function MessageRowHuman({ content }) {
  return (
    <Message from="user" className="w-full min-w-0">
      <div className="size-8 rounded-full bg-teoco-real-blue flex items-center justify-center ring-2 ring-teoco-real-blue/30">
        <User className="w-5 h-5 text-white" />
      </div>
      <MessageContent className="min-w-0">
        <MDResponse className="min-w-0 wrap-anywhere">
          {typeof content === "string"
            ? content
            : JSON.stringify(content, null, 2)}
        </MDResponse>
      </MessageContent>
    </Message>
  );
});

export default MessageRowHuman;

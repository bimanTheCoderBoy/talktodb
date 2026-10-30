import React from "react";
import { LazyMDResponse } from "@/components/ui/shadcn-io/ai/lazy-md-response";

const MessageRowMapLink = React.memo(function MessageRowMapLink({ content }) {
  const text = typeof content === "string" ? content : JSON.stringify(content ?? "");
  return (
    <div className="w-full max-w-3xl px-2 py-2 text-sm text-muted-foreground">
      <LazyMDResponse>{text}</LazyMDResponse>
    </div>
  );
});

export default MessageRowMapLink;

import React from "react";
import ToolResultCard from "./ToolResultCard";

const MessageRowTool = React.memo(function MessageRowTool({ message, onCopy }) {
  return <ToolResultCard message={message} onCopy={onCopy} />;
});

export default MessageRowTool;

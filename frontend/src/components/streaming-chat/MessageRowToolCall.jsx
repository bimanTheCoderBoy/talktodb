import React from "react";
import {
  Task,
  TaskContent,
  TaskItem,
  TaskTrigger,
} from "@/components/ui/shadcn-io/ai/task";
import { getToolDisplayName } from "@/constants/toolUi";

const MessageRowToolCall = React.memo(function MessageRowToolCall({ toolCalls }) {
  return toolCalls.map((toolCall) => (
    <Task key={toolCall.id} defaultOpen={false}>
      <TaskTrigger title={getToolDisplayName(toolCall?.name)} />
      <TaskContent>
        <TaskItem>calling {getToolDisplayName(toolCall?.name)} Tool</TaskItem>
      </TaskContent>
    </Task>
  ));
});

export default MessageRowToolCall;

import React, { useState, useEffect, useCallback, useMemo, useRef, useDeferredValue } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { Client } from "@langchain/langgraph-sdk";
import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
} from "@/components/ui/shadcn-io/ai/prompt-input";
import { LANGGRAPH_GRAPH_ID } from "@/constants/computer";
import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/ui/shadcn-io/ai/conversation";
import keycloak from "../keycloak";
import { useKeycloakToken } from "@/hooks/useKeycloakToken";
import TopBar from "./TopBar";
import { toast } from "react-toastify";
import InterruptCard from "./interrupt/InterruptCard";
import ToolCallInterruptModal, {
  toolCallInterruptStubResume,
} from "./interrupt/ToolCallInterruptModal";
import StreamingMessageList from "./streaming-chat/StreamingMessageList";
import ChatMessageNavigator from "./streaming-chat/ChatMessageNavigator";
import { MessageCircle } from "lucide-react";

const getApiUrl = () => {
  const configuredUrl = import.meta.env.VITE_LANGGRAPH_API_URL || "http://localhost:2024";
  if (configuredUrl.startsWith("/")) {
    return `${window.location.origin}${configuredUrl}`;
  }
  return configuredUrl;
};

function streamContext(threadId) {
  return {
    user_email: keycloak.tokenParsed?.email ?? "",
    thread_id: threadId,
  };
}

export function StreamingChat({ currentThread, sidebarOpen, setThreadTitle, setCurrentThread, addNewThread }) {
  const [inputValue, setInputValue] = useState("");
  const [streamErrorText, setStreamErrorText] = useState("");
  const [dismissedInterruptKey, setDismissedInterruptKey] = useState(null);
  const [tool_intermetiate_message_via_custom_events, setToolIntermetiateMessageViaCustomEvents] = useState(null);
  const [chatNavState, setChatNavState] = useState(null);
  const messagesKey = "ui_messages";
  const token = useKeycloakToken();

  const formatStreamError = (err) => {
    if (!err) return "";
    if (typeof err === "string") return err;
    if (err?.message && typeof err.message === "string") return err.message;
    if (err?.error?.message && typeof err.error.message === "string") return err.error.message;
    try {
      return JSON.stringify(err);
    } catch {
      return String(err);
    }
  };

  const client = useMemo(
    () =>
      new Client({
        apiUrl: getApiUrl(),
        defaultHeaders: { Authorization: `Bearer ${token}` },
      }),
    [token]
  );

  const { submit, messages, isLoading, interrupt, stop, error: errorMessage } = useStream({
    client,
    streamMode: "updates",
    assistantId: LANGGRAPH_GRAPH_ID,
    threadId: currentThread?.thread_id,
    messagesKey,
    onThreadId: (threadId) => {
      setCurrentThread((prev) => ({ ...prev, thread_id: threadId }));
    },
    reconnectOnMount: () => window.localStorage,
    onCustomEvent: (event) => {
      if (event.step && event.status && event.message) {
        setToolIntermetiateMessageViaCustomEvents({
          step: event.step,
          status: event.status,
          message: event.message,
        });
        if (event.status === "completed" || event.status === "failed") {
          setTimeout(() => setToolIntermetiateMessageViaCustomEvents(null), 200);
        }
      }
    },
  });

  const rawDeferred = useDeferredValue(messages);
  const prevThreadRef = useRef(currentThread?.thread_id);
  const threadChanged = prevThreadRef.current !== currentThread?.thread_id;
  if (threadChanged) prevThreadRef.current = currentThread?.thread_id;
  const deferredMessages = threadChanged ? messages : rawDeferred;

  const MAX_TOTAL_MESSAGES = 500;
  const cappedMessages = useMemo(() => {
    if (!deferredMessages || deferredMessages.length <= MAX_TOTAL_MESSAGES) return deferredMessages;
    return deferredMessages.slice(-MAX_TOTAL_MESSAGES);
  }, [deferredMessages]);

  const getInterruptKey = (interruptVal) => {
    if (!interruptVal?.value) return null;
    const type = interruptVal.value.type ?? "";
    const content = interruptVal.value.content;
    const contentStr = typeof content === "string" ? content : JSON.stringify(content ?? null);
    return `${type}:${contentStr.slice(0, 300)}`;
  };
  const currentInterruptKey = getInterruptKey(interrupt);
  const showInterrupt = currentInterruptKey !== null && currentInterruptKey !== dismissedInterruptKey;
  const dismissInterrupt = useCallback(() => {
    setDismissedInterruptKey(currentInterruptKey);
  }, [currentInterruptKey]);

  useEffect(() => {
    setDismissedInterruptKey(null);
  }, [currentThread?.thread_id]);

  useEffect(() => {
    if (!errorMessage) {
      setStreamErrorText("");
      return;
    }
    const msg = formatStreamError(errorMessage);
    if (String(msg).toLowerCase().includes("cancelled")) {
      setStreamErrorText("Request cancelled by you.");
      return;
    }
    setStreamErrorText(msg.length > 4000 ? `${msg.slice(0, 4000)}…` : msg);
  }, [errorMessage, currentThread?.thread_id]);

  useEffect(() => {
    setToolIntermetiateMessageViaCustomEvents(null);
  }, [currentThread?.thread_id]);

  const handleSubmit = async (e) => {
    dismissInterrupt();
    e.preventDefault();
    if (!currentThread?.thread_id) return;

    setStreamErrorText("");
    setToolIntermetiateMessageViaCustomEvents(null);
    const interruptType = interrupt?.value?.type;

    if (isLoading) {
      await stop();
      setInputValue("");
      setStreamErrorText("Request cancelled by you.");
      return;
    }

    if (interruptType === "ASK_HUMAN_BINARY" || interruptType === "tool_call") return;
    if (!inputValue.trim()) return;

    const query = inputValue.trim();
    const humanMessage = { type: "human", content: query };
    setInputValue("");

    const ctx = streamContext(currentThread.thread_id);

    if (interruptType === "ASK_HUMAN") {
      await submit(undefined, {
        command: { resume: query },
        streamResumable: true,
        context: ctx,
      });
      return;
    }

    if (messages.length === 0) {
      const title = "CE-" + (query.slice(0, 40) || "New chat");
      client.threads
        .update(currentThread.thread_id, {
          metadata: { thread_title: title, thread_title_generated: true },
        })
        .then(() => setThreadTitle((prev) => !prev))
        .catch((error) => console.error("Error updating thread title:", error));
    }

    await submit(
      { input_message: humanMessage },
      {
        optimisticValues(prev) {
          const prevMessages = prev?.[messagesKey] ?? [];
          return { ...prev, [messagesKey]: [...prevMessages, humanMessage] };
        },
        streamResumable: true,
        context: ctx,
      }
    );
  };

  const handleBinaryInterrupt = async (approved) => {
    dismissInterrupt();
    await submit(undefined, {
      command: { resume: approved },
      streamResumable: true,
      context: streamContext(currentThread?.thread_id),
    });
  };

  const handleToolCallInterruptAck = async () => {
    dismissInterrupt();
    await submit(undefined, {
      command: { resume: toolCallInterruptStubResume() },
      streamResumable: true,
      context: streamContext(currentThread?.thread_id),
    });
  };

  const handleCopyToClipboard = useCallback(async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard!");
    } catch {
      toast.error("Failed to copy!");
    }
  }, []);

  const interruptType = interrupt?.value?.type;
  const isHumanInterruptActive =
    interruptType === "ASK_HUMAN" ||
    interruptType === "ASK_HUMAN_BINARY" ||
    interruptType === "tool_call";
  const isBinaryInterruptActive = interruptType === "ASK_HUMAN_BINARY";
  const isToolCallInterruptActive = interruptType === "tool_call";

  if (!currentThread) {
    return (
      <div className="flex flex-col h-full items-center justify-center px-6 text-center">
        <MessageCircle className="w-12 h-12 text-muted-foreground mb-4" />
        <p className="text-lg text-foreground font-medium">No conversation selected</p>
        <p className="text-sm text-muted-foreground mt-2 max-w-sm">
          Choose a chat in the sidebar or create a new one with the plus button.
        </p>
        <button
          type="button"
          onClick={() => addNewThread?.()}
          className="mt-6 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
        >
          New chat
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <TopBar currentThread={currentThread} sidebarOpen={sidebarOpen} />

      <div className="relative flex-1 min-h-0 flex flex-col">
        <Conversation className="chat-pane-scroll px-3 sm:px-6 bg-transparent">
          <ConversationContent className="flex flex-col items-center w-full">
            <StreamingMessageList
              key={currentThread?.thread_id || "no-thread"}
              messages={cappedMessages}
              isLoading={isLoading}
              toolProgress={tool_intermetiate_message_via_custom_events}
              onCopy={handleCopyToClipboard}
              onNavStateChange={setChatNavState}
            />
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
        {chatNavState?.entries?.length > 1 && (
          <ChatMessageNavigator
            entries={chatNavState.entries}
            activeIndex={chatNavState.activeIndex}
            onJump={chatNavState.jump}
          />
        )}
      </div>

      <div className="w-full px-3 sm:px-6 lg:px-10 mb-5 flex justify-center items-center bg-transparent">
        <div
          className={`w-full max-w-[min(1120px,100%)] flex flex-col gap-2 ${
            isHumanInterruptActive ? "rounded-2xl bg-primary/15 border border-primary/35 p-2" : ""
          }`}
        >
          {!!streamErrorText && (
            <div className="mb-2 flex items-start gap-3 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-200 text-sm min-w-0">
              <div className="flex-1 min-w-0 whitespace-pre-wrap wrap-break-word">{streamErrorText}</div>
              <button
                type="button"
                className="shrink-0 px-2 py-1 rounded-md border border-red-500/30 hover:bg-red-500/10"
                onClick={() => setStreamErrorText("")}
              >
                Dismiss
              </button>
            </div>
          )}

          {showInterrupt && !isToolCallInterruptActive && (
            <div className="mb-2">
              <InterruptCard
                type={interruptType}
                content={interrupt?.value?.content}
                isLoading={isLoading}
                onApprove={() => handleBinaryInterrupt(true)}
                onDeny={() => handleBinaryInterrupt(false)}
              />
            </div>
          )}

          <ToolCallInterruptModal
            open={showInterrupt && isToolCallInterruptActive}
            content={interrupt?.value?.content}
            isLoading={isLoading}
            onUnderstood={handleToolCallInterruptAck}
          />

          <PromptInput
            onSubmit={handleSubmit}
            className="w-full min-w-0 border-border/80"
          >
            <PromptInputTextarea
              onChange={(e) => setInputValue(e.target.value)}
              value={inputValue}
              disabled={isBinaryInterruptActive || isToolCallInterruptActive}
              placeholder={
                isBinaryInterruptActive
                  ? "Select Approve or Deny to continue"
                  : isToolCallInterruptActive
                    ? "Acknowledge the tool popup to continue"
                    : "Ask about your database, schema, or data — type a question and press Enter…"
              }
              className="placeholder:text-muted-foreground/90"
            />
            <PromptInputToolbar>
              <PromptInputSubmit
                disabled={
                  isBinaryInterruptActive ||
                  isToolCallInterruptActive ||
                  (!inputValue && !isLoading)
                }
                status={isLoading ? "submitted" : ""}
                className="cursor-pointer bg-primary/90 hover:bg-primary text-primary-foreground border-0 disabled:opacity-40"
              />
            </PromptInputToolbar>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}

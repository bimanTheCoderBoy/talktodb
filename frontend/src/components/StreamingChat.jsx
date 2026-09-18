import React, { useState, useEffect, useCallback, useMemo, useRef, useDeferredValue } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { Client } from "@langchain/langgraph-sdk";
import { Settings2 } from "lucide-react";
import {
  PromptInput,
  PromptInputModelSelect,
  PromptInputModelSelectContent,
  PromptInputModelSelectItem,
  PromptInputModelSelectTrigger,
  PromptInputModelSelectValue,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from '@/components/ui/shadcn-io/ai/prompt-input';
import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ui/shadcn-io/ai/conversation';

import keycloak from "../keycloak";
import { useKeycloakToken } from "@/hooks/useKeycloakToken";

import TelecomMapContainer from "./map_select_coverage_view/TelecomMapContainer";
import TopBar from "./TopBar";
import { useProjectContext } from "@/context/ProjectContext";
import { toast } from "react-toastify";
import WelcomeScreen from "./WelcomeScreen";
import InterruptCard from "./interrupt/InterruptCard";
import StreamingMessageList from "./streaming-chat/StreamingMessageList";
import ChatMessageNavigator from "./streaming-chat/ChatMessageNavigator";

// Build full URL for LangGraph API (handles relative paths like /langgraph-api)
const getApiUrl = () => {
  const configuredUrl = import.meta.env.VITE_LANGGRAPH_API_URL || "http://localhost:2024";
  // If it's a relative path, prepend the current origin
  if (configuredUrl.startsWith('/')) {
    return `${window.location.origin}${configuredUrl}`;
  }
  return configuredUrl;
};



// -------------------  ---------------------------------------------------------------------------------------------------
export function StreamingChat({ currentThread, setThreads, sidebarOpen, setThreadTitle,  setCurrentThread, addNewThread }) {
  const [inputValue, setInputValue] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("agent");
  const [streamErrorText, setStreamErrorText] = useState("");
  const [dismissedInterruptKey, setDismissedInterruptKey] = useState(null);
  const [tool_intermetiate_message_via_custom_events, setToolIntermetiateMessageViaCustomEvents] = useState(null);
  const [chatNavState, setChatNavState] = useState(null);
  const { projectName, projectConfigured } = useProjectContext();
  const projectReady = !!(projectName && projectConfigured);
  const messagesKey = selectedAgent === "agent" ? "messages" : "ui_messages";
  const token = useKeycloakToken();




  const formatStreamError = (err) => {
    if (!err) return "";
    if (typeof err === "string") return err;
    if (err?.message && typeof err.message === "string") return err.message;
    if (err?.error?.message && typeof err.error.message === "string") return err.error.message;
    if (err?.cause?.message && typeof err.cause.message === "string") return err.cause.message;
    try {
      return safeStringify(err);
    } catch {
      return String(err);
    }
  };

  const isAuthErrorText = (text) => {
    if (!text) return false;
    const t = String(text).toLowerCase();
    return (
      t.includes("http 401") ||
      t.includes("unauthorized") ||
      t.includes("invalid or missing token") ||
      t.includes("invalid or expired token") ||
      t.includes("missing authorization")
    );
  };

  const isCancellationText = (text) => {
    if (!text) return false;
    const t = String(text).toLowerCase();
    return (

      t.includes("cancelled") 
    
    );
  };

 
  useEffect(() => {
   setCurrentThread(null);
  }, [projectName]);


  const client = useMemo(
    () =>
      new Client({
        apiUrl: getApiUrl(),
        defaultHeaders: {
          Authorization: `Bearer ${token}`,
        },
      }),
    [token]
  );
  const {
    stream,
    submit, 
    messages, 
    isLoading,

    
    interrupt, 
    stop,
    error:errorMessage,

  } = useStream({
    client,
    streamMode: "updates",
    assistantId: selectedAgent,
    threadId: currentThread?.thread_id,
    messagesKey,
    onThreadId:(threadId) => {
      setCurrentThread((prev) => ({...prev, thread_id: threadId}));
    },
    
    reconnectOnMount: () => window.localStorage,
  

    onCustomEvent: (event) => {
      if (event.step && event.status && event.message) {
        setToolIntermetiateMessageViaCustomEvents({
          step: event.step,
          status: event.status,
          message: event.message
        });
        
        // Clear the step when completed
        if (event.status === 'completed' || event.status === 'failed') {
          setTimeout(() => setToolIntermetiateMessageViaCustomEvents(null), 200);
        }
      }
    }

  });

  const rawDeferred = useDeferredValue(messages);
  const prevThreadRef = useRef(currentThread?.thread_id);
  const threadChanged = prevThreadRef.current !== currentThread?.thread_id;
  if (threadChanged) prevThreadRef.current = currentThread?.thread_id;
  // Bypass deferred value on thread switch to prevent stale cross-thread messages
  const deferredMessages = threadChanged ? messages : rawDeferred;

  // Cap messages to prevent useStream SDK O(n^2) messageMetadata accumulation
  const MAX_TOTAL_MESSAGES = 500;
  const cappedMessages = useMemo(() => {
    if (!deferredMessages || deferredMessages.length <= MAX_TOTAL_MESSAGES) {
      return deferredMessages;
    }
    return deferredMessages.slice(-MAX_TOTAL_MESSAGES);
  }, [deferredMessages]);

  const getInterruptKey = (interruptVal) => {
    if (!interruptVal?.value) return null;
    const type = interruptVal.value.type ?? '';
    const content = interruptVal.value.content;
    const contentStr = typeof content === 'string' ? content : JSON.stringify(content ?? null);
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
    if (isCancellationText(msg)) {
      setStreamErrorText("Request cancelled by you.");
      return;
    }
    if (isAuthErrorText(msg) || errorMessage?.status === 401) {
      setStreamErrorText(
        "Your session has expired. Please refresh the page and sign in again to continue."
      );
      return;
    }
    setStreamErrorText(msg.length > 4000 ? `${msg.slice(0, 4000)}…` : msg);
  }, [errorMessage, currentThread?.thread_id]);

  
  const agents = [
    { value: "db_agent", label: "DB Expert" },
    { value: "agent", label: "Coverage Expert" },
    { value: "computer", label: "Computer Expert" },
  ];

  useEffect(() => {
    setToolIntermetiateMessageViaCustomEvents(null);
    if(currentThread?.metadata?.agent_type){
      
      setSelectedAgent(currentThread.metadata.agent_type);
    } 
  }, [currentThread]);

  

  const handleAgentChange = async (value, forceNewThread=false) => {
   if (messages.length > 0 || forceNewThread) {
      await addNewThread();
    }
    setToolIntermetiateMessageViaCustomEvents(null);
    if(value){
    setSelectedAgent(value);}
    
  }

  const handleSubmit = async (e) => {
    dismissInterrupt();
    e.preventDefault();
    if (!projectReady) return;
    setStreamErrorText("");
    setToolIntermetiateMessageViaCustomEvents(null);
    const interruptType = interrupt?.value?.type;

    if (isLoading) {
      await stop();
      setInputValue("");
      setStreamErrorText("Request cancelled by you.");
      return;
    }

    // For binary human approval, only the explicit Approve/Deny buttons should resume execution.
    if (interruptType === "ASK_HUMAN_BINARY") {
      return;
    }

    if (!inputValue.trim()) return;


    const query = inputValue.trim();
    const humanMessage = { type: "human", content: query };

    setInputValue("");
    if (interruptType === "ASK_HUMAN") {
      await submit(undefined, {
         command: { resume: query },
         streamResumable: true,
         context:{project_name: projectName, user_email: keycloak.tokenParsed?.email, thread_id: currentThread?.thread_id}
        });

    } else {
      if (messages.length == 0 && humanMessage) {
        const agent_tag = selectedAgent=="agent" ? "CA-" : selectedAgent=="computer" ? "CE-" : "DA-";
        const title = agent_tag+ humanMessage.content.trim().slice(0, 40) || agent_tag+ "New chat";
        client.threads.update(currentThread.thread_id, { metadata: { thread_title: title, thread_title_generated: true, agent_type: selectedAgent } }).then(() => {
          setThreadTitle((prev) => !prev);
        }).catch((error) => {
          console.error("Error updating thread title:", error);
        });
      }

      await submit({ input_message: humanMessage, },
        {
          optimisticValues(prev) {
            const prevMessages = prev?.[messagesKey] ?? [];
            const newMessages = [...prevMessages, humanMessage];
            return { ...prev, [messagesKey]: newMessages };
          },
          streamResumable: true,
          context:{project_name: projectName, user_email: keycloak.tokenParsed?.email, thread_id: currentThread?.thread_id} 
          
       });
    }
  };

 const handleBinaryInterrupt = async (approved) => {
  dismissInterrupt();
  await submit(undefined, {
    command: { resume: approved },
    streamResumable: true,
    context:{project_name: projectName, user_email: keycloak.tokenParsed?.email, thread_id: currentThread?.thread_id}
  });
 }

 const handleMapConfirmColseInterrupt = async (data) => {
  dismissInterrupt();
  await submit(undefined, { 
    command: { resume: JSON.stringify(data) },
    streamResumable: true,
    context:{project_name: projectName, user_email: keycloak.tokenParsed?.email, thread_id: currentThread?.thread_id}
  
  });
 }

 const handleCopyToClipboard = useCallback(async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  } catch (err) {
    toast.error('Failed to copy!');
  }
 }, []);
  

  const interruptType = interrupt?.value?.type;
  const isHumanInterruptActive = interruptType === "ASK_HUMAN" || interruptType === "ASK_HUMAN_BINARY";
  const isBinaryInterruptActive = interruptType === "ASK_HUMAN_BINARY";

  const mapDataContent = interrupt?.value?.content;
  const parsedMapData = useMemo(() => {
    if (interruptType !== "VIEW_MAP_DATA" || !mapDataContent) return null;
    try { return JSON.parse(mapDataContent); } catch { return null; }
  }, [interruptType, mapDataContent]);

  if (!currentThread) {
    return <WelcomeScreen addNewThread={addNewThread} handleAgentChange={handleAgentChange} />;
  }

  return (
    <div className="flex flex-col h-full ">
      {/* {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          Error: {error}
        </div>
      )} */}

      <TopBar 
        currentThread={currentThread} 
        sidebarOpen={sidebarOpen}
        selectedAgent={selectedAgent}
        setThreads={setThreads}
        onRunCoverage={async (cellIds) => {
          const query = `I want to run coverage for \`<cell_iids>\`[${cellIds.join(', ')}]\`<\\cell_iids>\``;
          const humanMessage = { type: "human", content: query };
          
          if (messages.length === 0 && humanMessage) {
            const agent_tag = selectedAgent === "agent" ? "CA-" : selectedAgent === "computer" ? "CE-" : "DA-";
            const title = agent_tag + humanMessage.content.trim().slice(0, 40) || agent_tag + "New chat";
            client.threads.update(currentThread.thread_id, { 
              metadata: { thread_title: title, thread_title_generated: true, agent_type: selectedAgent } 
            }).then(() => {
              setThreadTitle((prev) => !prev);
            }).catch((error) => {
              console.error("Error updating thread title:", error);
            });
          }
          
          await submit({ input_message: humanMessage }, {
            optimisticValues(prev) {
              const prevMessages = prev?.[messagesKey] ?? [];
              const newMessages = [...prevMessages, humanMessage];
              return { ...prev, [messagesKey]: newMessages };
            },
            streamResumable: true,
            context: { project_name: projectName, user_email: keycloak.tokenParsed?.email, thread_id: currentThread?.thread_id }
          });
        }}
      />
      
      <div className="relative flex-1 min-h-0 flex flex-col">
      <Conversation className="chat-pane-scroll px-3 sm:px-6 bg-transparent">
        <ConversationContent className="flex flex-col items-center w-full">
          <StreamingMessageList
            key={`${currentThread?.thread_id || "no-thread"}-${selectedAgent}`}
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
      <div className="w-full px-3 sm:px-6 mb-4 flex justify-center items-center bg-transparent">

        <div className={`w-full ${sidebarOpen ? "max-w-3xl" : "max-w-4xl"} flex flex-col p-2 ${isHumanInterruptActive ? "bg-teoco-real-blue/20 border border-teoco-real-blue/40" : "bg-transparent"} cursor-pointer rounded-[20px] transition-[max-width] duration-300`}>

          {!projectReady && (
            <div className="mb-2 flex items-center gap-2 px-4 py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-600 text-sm dark:text-amber-400 rounded-full">
              <Settings2 className="w-4 h-4 shrink-0" />
              <span>
                {!projectName
                  ? "Please set a project name in the top bar to start chatting."
                  : "Please save your project config (select cells/polygon) before chatting."}
              </span>
            </div>
          )}

          {!!streamErrorText && (
            <div className="mb-2 flex items-start gap-3 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-200 text-sm min-w-0">
              <div className="flex-1 min-w-0">
                <div className="mt-1 whitespace-pre-wrap wrap-break-word">{streamErrorText}</div>
              </div>
              <button
                type="button"
                className="shrink-0 px-2 py-1 rounded-md border border-red-500/30 hover:border-red-500/50 hover:bg-red-500/10 text-red-600 dark:text-red-200 transition-colors"
                onClick={() => {
                  setStreamErrorText("");
                }}
              >
                Dismiss
              </button>
            </div>
          )}

          { showInterrupt && <div className="mb-2">
            <InterruptCard
              type={interruptType}
              content={interrupt?.value?.content}
              isLoading={isLoading}
              onApprove={() => handleBinaryInterrupt(true)}
              onDeny={() => handleBinaryInterrupt(false)}
            />
          </div>}
          {/* THEME: hardcoded #0d172b → var(--card), hardcoded border → var(--border), hardcoded #FFFFFF → var(--foreground) */}
          <PromptInput
            onSubmit={handleSubmit}
            className="w-full min-w-0 border-border shadow-xl"
            style={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)' }}
          >
            <PromptInputTextarea
              onChange={(e) => setInputValue(e.target.value)}
              value={inputValue}
              disabled={!projectReady || isBinaryInterruptActive}
              placeholder={
                !projectReady
                  ? "Set up your project name and config via Project Config before chatting"
                  : isBinaryInterruptActive
                    ? "Select Approve or Deny to continue"
                    : selectedAgent == "agent" ? "Ask Questions related to Coverage running" : selectedAgent == "computer" ? "Ask questions about your filesystem workspace" : "Ask your questions related to Asset Network Database"
              }
              style={{ color: 'var(--foreground)' }}
              className="placeholder:text-muted-foreground"
            />
            <PromptInputToolbar>
              <PromptInputTools>
                <PromptInputModelSelect onValueChange={handleAgentChange} value={selectedAgent}>
                  <PromptInputModelSelectTrigger>
                    <PromptInputModelSelectValue />
                  </PromptInputModelSelectTrigger>
                  <PromptInputModelSelectContent>
                    {agents.map((agent) => (
                      <PromptInputModelSelectItem key={agent.value} value={agent.value}>
                        {agent.label}
                      </PromptInputModelSelectItem>
                    ))}
                  </PromptInputModelSelectContent>
                </PromptInputModelSelect>
              </PromptInputTools>
              <PromptInputSubmit
                disabled={!projectReady || isBinaryInterruptActive || (!inputValue && !isLoading)}
                status={isLoading ? 'submitted' : ""}
                className="cursor-pointer bg-primary hover:bg-primary/90 text-primary-foreground border-0 shadow-lg shadow-primary/20"
              />
            </PromptInputToolbar>
          </PromptInput>
        </div>
      </div>
      
      {showInterrupt && interrupt?.value?.type === "VIEW_MAP_DATA" && (
       <TelecomMapContainer data={parsedMapData} onConfirm={handleMapConfirmColseInterrupt} onClose={handleMapConfirmColseInterrupt} />
      )}

    </div>
  );
}

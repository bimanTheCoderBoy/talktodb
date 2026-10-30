import { Client } from "@langchain/langgraph-sdk";
import keycloak from "./keycloak";

const getApiUrl = () => {
  const configuredUrl = import.meta.env.VITE_LANGGRAPH_API_URL || "http://localhost:2024";
  if (configuredUrl.startsWith("/")) {
    return `${window.location.origin}${configuredUrl}`;
  }
  return configuredUrl;
};

export const langgraphClient = () => {
  try {
    return new Client({
      apiUrl: getApiUrl(),
      defaultHeaders: {
        Authorization: `Bearer ${keycloak.token}`,
      },
    });
  } catch (error) {
    console.error("Error creating langgraph client:", error);
    return null;
  }
};

export const getThreads = async () => {
  const threads = await langgraphClient().threads.search({
    limit: 100,
    sort_by: "created_at",
    sort_order: "desc",
    metadata: {
      owner: keycloak.tokenParsed?.sub ?? "",
    },
  });
  return { threads: threads || [] };
};

export const createThread = async () => {
  const thread = await langgraphClient().threads.create({
    metadata: {
      owner: keycloak.tokenParsed?.sub ?? "",
    },
  });
  return {
    thread_id: thread.thread_id,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
    status: thread.status,
  };
};

export const deleteThread = async (threadId) => {
  await langgraphClient().threads.delete(threadId);
  return { success: true, thread_id: threadId };
};

export const update_thread_title = async (threadId, title, metadata) => {
  await langgraphClient().threads.update(threadId, {
    metadata: { ...metadata, thread_title: title },
  });
  return { success: true, thread_id: threadId };
};

export const update_thread_pinned = async (threadId, pinned, metadata = {}) => {
  await langgraphClient().threads.update(threadId, {
    metadata: {
      ...metadata,
      pinned: !!pinned,
      pinned_at: pinned ? Date.now() : null,
    },
  });
  return { success: true, thread_id: threadId, pinned: !!pinned };
};

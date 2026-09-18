import { Client } from "@langchain/langgraph-sdk";
import keycloak from "./keycloak";
import { useProjectContext } from "./context/ProjectContext";

// Build full URL for LangGraph API (handles relative paths like /langgraph-api)
const getApiUrl = () => {
  const configuredUrl = import.meta.env.VITE_LANGGRAPH_API_URL || "http://localhost:2024";
  // If it's a relative path, prepend the current origin
  if (configuredUrl.startsWith('/')) {
    return `${window.location.origin}${configuredUrl}`;
  }
  return configuredUrl;
};

export const langgraphClient = () => {
  try {
    const client = new Client({
      apiUrl: getApiUrl(),
      defaultHeaders: {
        Authorization: `Bearer ${keycloak.token}`
      }
    }); 
    return client;
  } catch (error) {
    console.error('Error creating langgraph client:', error);
    return null;
  }
}

// API functions
export const getThreads = async (projectName = "") => {
  try {
    // Use LangGraph SDK to search for threads
  
    const threads = await langgraphClient().threads.search({
      limit: 100, // Adjust as needed
      sort_by: "created_at",
      sort_order: "desc",
      metadata: {
        owner: keycloak.tokenParsed?.sub ?? "",
        project_name: projectName,
      }
    });
    
    return { threads: threads || [] };
  } catch (error) {
    console.error('Error fetching threads:', error);
    throw error;
  }
};

export const createThread = async (projectName = "") => {
  try {
    // Use LangGraph SDK to create a new thread
    console.log(keycloak.tokenParsed);
    const thread = await langgraphClient().threads.create({
      metadata: {
        owner: keycloak.tokenParsed?.sub ?? "",
        project_name: projectName,
      }
    });
    
    return { 
      thread_id: thread.thread_id,  
      created_at: thread.created_at,
      updated_at: thread.updated_at,
      status: thread.status,
    };
  } catch (error) {
    console.error('Error creating thread:', error);
    throw error;
  }
};


export const deleteThread = async (threadId) => {
  try {
    // Use LangGraph SDK to delete thread
    // This will delete all checkpoints associated with the thread
    await langgraphClient().threads.delete(threadId);
    return { success: true, thread_id: threadId };
  } catch (error) {
    console.error('Error deleting thread:', error);
    throw error;
  }
};

export const update_thread_title = async (threadId, title, metadata) => {
  try {
    // Use LangGraph SDK to update thread name
    await langgraphClient().threads.update(threadId,  { metadata: { ...metadata, thread_title: title } });
    return { success: true, thread_id: threadId };
  } catch (error) {
    console.error('Error updating thread name:', error);
    throw error;
  }
};

/** Persist pin state on thread metadata  */
export const update_thread_pinned = async (threadId, pinned, metadata = {}) => {
  try {
    await langgraphClient().threads.update(threadId, {
      metadata: {
        ...metadata,
        pinned: !!pinned,
        pinned_at: pinned ? Date.now() : null,
      },
    });
    return { success: true, thread_id: threadId, pinned: !!pinned };
  } catch (error) {
    console.error("Error updating thread pin:", error);
    throw error;
  }
};








export const getSitesCells = async (projectName, auth_scope = false, filters = {}) => {
  try {
    const apiUrl = getApiUrl();
    const params = { auth_scope: auth_scope };
    
    // Add polygon coordinates if provided (takes priority over text filters)
    if (filters.cords) {
      params.cords = filters.cords;
    }

    // Add filter parameters if provided
    if (filters.state) {
      params.state = filters.state;
    }
    if (filters.address1) {
      params.address1 = filters.address1;
    }
    if (filters.town) {
      params.town = filters.town;
    }
    
    const response = await fetch(`${apiUrl}/api/sites-cells`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${keycloak.token}`,
        'x-project-name': projectName,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Failed to fetch sites and cells: ${response.statusText}`);
    }

    const data = await response.json();
    return data.sites || [];
  } catch (error) {
    console.error('Error fetching sites and cells:', error);
    throw error;
  }
};


// ============== Project Config API helpers ==============

export const getProjectCords = async (projectName) => {
  try {
    const apiUrl = getApiUrl();
    const response = await fetch(`${apiUrl}/api/v1/project-cords`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${keycloak.token}`,
        'x-project-name': projectName,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Failed to fetch project cords: ${response.statusText}`);
    }

    const data = await response.json();
    return data.cords || [];
  } catch (error) {
    console.error('Error fetching project cords:', error);
    throw error;
  }
};

export const getUserProjectConfig = async (projectName, email) => {
  try {
    const apiUrl = getApiUrl();
    const params = new URLSearchParams({ project_name: projectName });
    if (email) params.set('email', email);
    const response = await fetch(`${apiUrl}/api/v1/user-project-config?${params}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${keycloak.token}`,
      },
    });

    if (response.status === 404) {
      return null; // No saved config
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Failed to fetch user project config: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching user project config:', error);
    throw error;
  }
};

export const getCellsInPolygon = async (cords, projectName) => {
  const apiUrl = getApiUrl();
  const response = await fetch(`${apiUrl}/api/v1/user-project-config/cells-in-polygon`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${keycloak.token}`,
      'x-project-name': projectName,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ cords }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Failed to fetch cells in polygon: ${response.statusText}`);
  }

  return await response.json();
};

export const upsertUserProjectConfig = async ({ projectName, email, cords, cellIids }) => {
  try {
    const apiUrl = getApiUrl();
    const payload = {
      project_name: projectName,
      cords: cords || [],
      cell_iids: cellIids || [],
    };
    if (email) payload.email = email;
    const response = await fetch(`${apiUrl}/api/v1/user-project-config`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${keycloak.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Failed to save user project config: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error saving user project config:', error);
    throw error;
  }
};

// ============== Audit Rules API helpers ==============

const auditRulesHeaders = () => ({
  Authorization: `Bearer ${keycloak.token}`,
  "Content-Type": "application/json",
});

export const getAuditRulesCatalog = async () => {
  const apiUrl = getApiUrl();
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/catalog`, {
    method: "GET",
    headers: auditRulesHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Failed to fetch audit rules catalog");
  }
  return response.json();
};

export const getAuditRules = async (projectName) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const response = await fetch(`${apiUrl}/api/v1/audit-rules?${params}`, {
    method: "GET",
    headers: auditRulesHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Failed to fetch audit rules");
  }
  return response.json();
};

export const createCustomAuditRule = async (projectName, payload) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/custom?${params}`, {
    method: "POST",
    headers: auditRulesHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail) || "Failed to create custom rule"
    );
  }
  return response.json();
};

export const updateCustomAuditRule = async (projectName, ruleId, payload) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/custom/${ruleId}?${params}`, {
    method: "PUT",
    headers: auditRulesHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail) || "Failed to update custom rule"
    );
  }
  return response.json();
};

export const deleteCustomAuditRule = async (projectName, ruleId) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/custom/${ruleId}?${params}`, {
    method: "DELETE",
    headers: auditRulesHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Failed to delete custom rule");
  }
};

export const updateAuditRulePreferences = async ({ projectName, preferences }) => {
  const apiUrl = getApiUrl();
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/preferences`, {
    method: "PUT",
    headers: auditRulesHeaders(),
    body: JSON.stringify({ project_name: projectName, preferences }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Failed to update rule preferences");
  }
  return response.json();
};

export const updateBuiltinRuleConfig = async (projectName, ruleKey, config) => {
  const apiUrl = getApiUrl();
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/builtin/${encodeURIComponent(ruleKey)}`, {
    method: "PUT",
    headers: auditRulesHeaders(),
    body: JSON.stringify({ project_name: projectName, config }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail) || "Failed to save rule configuration"
    );
  }
  return response.json();
};

export const downloadBuiltinRuleConfigsCsv = async (projectName) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/builtin/export?${params}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${keycloak.token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Failed to download rule configurations");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] || `audit-rules-config-${projectName}.csv`;
  return { blob, filename };
};

export const uploadBuiltinRuleConfigsCsv = async (projectName, file) => {
  const apiUrl = getApiUrl();
  const params = new URLSearchParams({ project_name: projectName });
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${apiUrl}/api/v1/audit-rules/builtin/import?${params}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${keycloak.token}` },
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = error.detail;
    if (detail && typeof detail === "object" && Array.isArray(detail.errors)) {
      throw new Error(detail.errors.join("\n"));
    }
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail) || "Failed to upload rule configurations"
    );
  }
  return response.json();
};
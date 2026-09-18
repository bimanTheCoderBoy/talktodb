import axios from 'axios';
import keycloak from '@/keycloak';



const getAcssApiUrl = () => {
  const configuredUrl = import.meta.env.VITE_ACSS_API_URL || 'http://localhost:8009';
  return configuredUrl;
};

// Create axios instance with default configuration
const acssApiClient = axios.create({
  baseURL: getAcssApiUrl(),
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

acssApiClient.interceptors.request.use(
  (config) => {
    if (keycloak?.token) {
      config.headers['Authorization'] = `Bearer ${keycloak.token}`;
    }
    const email = keycloak?.tokenParsed?.email;
    if (email) {
      config.headers['x-user-email'] = email;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

const formatErrorDetail = (error) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.slice(1).join('.') : d.loc;
        return `${field}: ${d.msg}`;
      })
      .join('; ');
  }
  return error?.message || 'Unknown error';
};


export const sessionApi = {

  createOrGetSession: async (sessionData) => {
    try {

      const response = await acssApiClient.post('/api/v1/session/create_or_get', sessionData, {
        headers: {
          'x-project-name': sessionData?.project_name,
        },
      });
      return response.data;
    } catch (error) {

      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to create or get session: ${errorDetail}`);
    }
  },

  deleteSession: async (session_id, project_name) => {
    try {
      const response = await acssApiClient.delete(`/api/v1/session/${session_id}`, {
        headers: { 'x-project-name': project_name },
      });
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to delete session: ${errorDetail}`);
    }
  },

  listSessions: async (project_name, limit = 20) => {
    try {
      const response = await acssApiClient.get('/api/v1/session/list', {
        headers: { 'x-project-name': project_name },
        params: { limit },
      });
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to list sessions: ${errorDetail}`);
    }
  },

}

export const setupApi = {
  getGoals: async () => {
    try {
      const response = await acssApiClient.get('/api/v1/setup/goals');
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to get goals: ${errorDetail}`);
    }
  },

  putPolygon: async (acss_session_id, polygonData, project_name) => {
    try {
      const response = await acssApiClient.put(`/api/v1/setup/${acss_session_id}/polygon`, polygonData, {
        headers: {
          'x-project-name': project_name,
        },
      });
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to put polygon: ${errorDetail}`);
    }
  },

  getCellsInBounds: async (acss_session_id, boundaryCoords, project_name) => {
    try {
      const response = await acssApiClient.post(
        `/api/v1/setup/${acss_session_id}/cells-in-bounds`,
        { boundary_coords: boundaryCoords },
        {
          headers: {
            'x-project-name': project_name,
          },
        }
      );
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to get cells in bounds: ${errorDetail}`);
    }
  },

  downloadGdlCsv: async (acss_session_id, project_name) => {
    try {
      const response = await acssApiClient.get(
        `/api/v1/setup/${acss_session_id}/gdl/download`,
        { headers: { 'x-project-name': project_name } }
      );
      return response.data;
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      throw new Error(`Failed to download GDL CSV: ${errorDetail}`);
    }
  },

  uploadGdlFile: async (acss_session_id, project_name, file) => {
    try {
      
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await acssApiClient.post(`/api/v1/setup/${acss_session_id}/gdl`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'x-project-name': project_name,
        },
      });  
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to upload GDL file: ${errorDetail}`);
    }
  },

  putGoal: async (acss_session_id, goalData, project_name) => {
    try {
      const response = await acssApiClient.put(`/api/v1/setup/${acss_session_id}/goal`, goalData, {
        headers: {
          'x-project-name': project_name,
        },
      });
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to save goal: ${errorDetail}`);
    }
  },

  getAntennaTemplates: async () => {
    try {
      const response = await acssApiClient.get('/api/v1/setup/antenna-templates');
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to load antenna templates: ${errorDetail}`);
    }
  },

  getPopulationRasterStatus: async (project_name) => {
    try {
      const response = await acssApiClient.get('/api/v1/setup/population-raster-status', {
        headers: { 'x-project-name': project_name },
      });
      return response.data;   // { available, filename?, total_population?, error? }
    } catch (error) {
      // Treat any failure as "not available" so the UI gracefully degrades.
      return { available: false, error: error?.message || 'probe failed' };
    }
  },

  postAutoGenConfig: async (sessionId, config, project_name) => {
    // config: { n, threshold_dbm, template_name, seed }
    try {
      const response = await acssApiClient.post(`/api/v1/setup/${sessionId}/autogen-config`, config, {
        headers: { 'x-project-name': project_name },
      });
      return response.data;
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      console.error('[autogen-config] sent:', config, 'error:', error.response?.data);
      throw new Error(`Failed to save auto-gen config: ${errorDetail}`);
    }
  },


  deleteCandidate: async (sessionId, siteIid, project_name) => {
    try {
      const response = await acssApiClient.delete(`/api/v1/setup/${sessionId}/candidate/${encodeURIComponent(siteIid)}`, {
        headers: { 'x-project-name': project_name },
      });
      return response.data;
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      throw new Error(`Failed to delete candidate: ${errorDetail}`);
    }
  },

  cleanupEdsSites: async (sessionId, project_name) => {
    try {
      const response = await acssApiClient.delete(`/api/v1/setup/${sessionId}/eds-cleanup`, {
        headers: { 'x-project-name': project_name },
      });
      return response.data;
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      throw new Error(`Failed to clean up EDS sites: ${errorDetail}`);
    }
  },

  getTiltMapping: async () => {
    try {
      const response = await acssApiClient.get('/api/v1/setup/tilt-mapping');
      return response.data;   // { available, entry_count, bands, path }
    } catch (error) {
      // Treat any failure as "no mapping" so the UI gracefully degrades.
      return { available: false, entry_count: 0, bands: {} };
    }
  },

  uploadTiltMapping: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await acssApiClient.post('/api/v1/setup/tilt-mapping', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;  // { accepted, entry_count, bands, message }
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      throw new Error(`Failed to upload tilt mapping: ${errorDetail}`);
    }
  },

  deleteTiltMapping: async () => {
    try {
      const response = await acssApiClient.delete('/api/v1/setup/tilt-mapping');
      return response.data;  // { deleted, message }
    } catch (error) {
      const errorDetail = formatErrorDetail(error);
      throw new Error(`Failed to delete tilt mapping: ${errorDetail}`);
    }
  },

  downloadTiltMappingSample: async () => {
    const response = await acssApiClient.get(
      '/api/v1/setup/tilt-mapping/sample',
      { responseType: 'blob' }
    );
    const url = window.URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tilt_mapping_sample.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
}

export const executionApi = {
  runExecution: async (acss_session_id, project_name) => {
    try {
      const response = await acssApiClient.post(
        `/api/v1/execution/${acss_session_id}/run`,
        {},
        {
          headers: {
            'x-project-name': project_name,
          },
        }
      );
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to start execution: ${errorDetail}`);
    }
  },

  getJobHealth: async (job_id) => {
    try {
      const response = await acssApiClient.get(`/api/v1/execution/${job_id}/health`);
      return response.data; // { task_id, status, error }
    } catch (error) {
      return { task_id: job_id, status: 'UNKNOWN', error: error.message };
    }
  },

  getReview: async (acss_session_id, project_name) => {
    try {
      const response = await acssApiClient.get(
        `/api/v1/execution/${acss_session_id}/review`,
        {
          headers: {
            'x-project-name': project_name,
          },
        }
      );
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to get review: ${errorDetail}`);
    }
  },

  confirmReview: async (acss_session_id, project_name, selected_candidate_names) => {
    try {
      const response = await acssApiClient.post(
        `/api/v1/execution/${acss_session_id}/review/confirm`,
        { selected_candidate_names },
        {
          headers: {
            'x-project-name': project_name,
          },
        }
      );
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to confirm review: ${errorDetail}`);
    }
  },

  closeReview: async (acss_session_id, project_name) => {
    try {
      const response = await acssApiClient.post(
        `/api/v1/execution/${acss_session_id}/review/close`,
        {},
        {
          headers: {
            'x-project-name': project_name,
          },
        }
      );
      return response.data;
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message;
      throw new Error(`Failed to close review: ${errorDetail}`);
    }
  },
};

export default acssApiClient;

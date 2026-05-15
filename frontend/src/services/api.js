import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const apiService = {
  // Design API
  generateDesign: (params) =>
    api.post('/design/', {
      user_prompt: params.prompt,
      plot_width_m: params.plotWidth || 30,
      plot_depth_m: params.plotDepth || 40,
      num_floors: params.numFloors || 2,
      building_type: params.buildingType || 'residential',
      region: params.region || 'default',
      use_vastu: params.useVastu || false,
    }),

  getDesignSession: (sessionId) =>
    api.get(`/design/${sessionId}/`),

  listDesignSessions: () =>
    api.get('/design/list/'),

  // Project API
  createProject: (params) =>
    api.post('/projects/', {
      name: params.name || 'Untitled Project',
      description: params.description || '',
      location: params.location || '',
      plot_width_m: params.plotWidth || 30,
      plot_depth_m: params.plotDepth || 40,
      num_floors: params.numFloors || 2,
      building_type: params.buildingType || 'residential',
      region: params.region || 'default',
      use_vastu: params.useVastu || false,
    }),

  listProjects: () =>
    api.get('/projects/'),

  getProject: (projectId) =>
    api.get(`/projects/${projectId}/`),

  updateProject: (projectId, params) =>
    api.patch(`/projects/${projectId}/`, params),

  deleteProject: (projectId) =>
    api.delete(`/projects/${projectId}/`),

  // Revision API
  getProjectRevisions: (projectId) =>
    api.get(`/projects/${projectId}/revisions/`),

  getProjectRevision: (projectId, revisionId) =>
    api.get(`/projects/${projectId}/revisions/${revisionId}/`),

  saveProjectRevision: (projectId, params) =>
    api.post(`/projects/${projectId}/revisions/`, params),

  // Report API
  generateReport: (params) =>
    api.post('/reports/', {
      session_id: params.sessionId,
      layout_data: params.layoutData,
      format: 'pdf',
    }),

  generateDXF: (params) =>
    api.post('/reports/dxf/', {
      session_id: params.sessionId,
      layout_data: params.layoutData,
    }),

  getReportStatus: (reportId) =>
    api.get(`/reports/${reportId}/`),

  downloadReport: (reportId) =>
    api.get(`/reports/${reportId}/download/`),

  // Compliance API
  checkCompliance: (params) =>
    api.post('/design/compliance/', {
      layout_zones: params.zones,
      region: params.region,
      plot_width_m: params.plotWidth,
      plot_depth_m: params.plotDepth,
    }),

  // Health check
  checkHealth: () =>
    api.get('/health/'),
};

export default api;

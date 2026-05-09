/**
 * studio-api.js — Archi3D Studio API Service Layer
 * ═════════════════════════════════════════════════════════════
 * Clean abstractions for all backend API calls.
 * Handles authentication, error handling, and response parsing.
 */

class StudioAPI {
  constructor() {
    this.baseUrl = '/api/v1';
    this.token = this.loadToken();
  }

  /**
   * Token Management
   */
  loadToken() {
    return localStorage.getItem('studio_auth_token') || sessionStorage.getItem('studio_auth_token');
  }

  saveToken(token) {
    localStorage.setItem('studio_auth_token', token);
  }

  clearToken() {
    localStorage.removeItem('studio_auth_token');
    sessionStorage.removeItem('studio_auth_token');
    this.token = null;
  }

  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * HTTP Methods
   */
  async request(method, endpoint, body = null) {
    const url = `${this.baseUrl}${endpoint}`;
    const options = {
      method,
      headers: this.getHeaders(),
    };

    if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
      const csrfToken = this.getCsrfToken();
      if (csrfToken) {
        options.headers['X-CSRFToken'] = csrfToken;
      }
      if (body) {
        options.body = JSON.stringify(body);
      }
    }

    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `API Error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Request Failed: ${method} ${endpoint}`, error);
      throw error;
    }
  }

  async get(endpoint) {
    return this.request('GET', endpoint);
  }

  async post(endpoint, body) {
    return this.request('POST', endpoint, body);
  }

  async put(endpoint, body) {
    return this.request('PUT', endpoint, body);
  }

  async patch(endpoint, body) {
    return this.request('PATCH', endpoint, body);
  }

  async delete(endpoint) {
    return this.request('DELETE', endpoint);
  }

  /**
   * DESIGN API — Main pipeline and generation
   */

  /**
   * Generate design from prompt and settings
   * POST /api/v1/design/
   */
  async generateDesign(params) {
    const body = {
      raw_text: params.prompt || '',
      building_type: params.buildingType || 'residential',
      plot_width_m: params.plotWidth || 30.0,
      plot_depth_m: params.plotDepth || 40.0,
      num_floors: params.numFloors || 2,
      num_units: params.numUnits || 1,
      plot_facing_direction: params.plotFacing || 'north',
      use_vastu: params.useVastu || false,
      _explicit_fields: ['plot_width_m', 'plot_depth_m', 'building_type', 'num_floors', 'num_units'],
    };

    if (params.hyparUrl) body.hypar_api_url = params.hyparUrl;
    if (params.hyparToken) body.hypar_api_token = params.hyparToken;

    return this.post('/design/', body);
  }

  /**
   * Get design session details
   * GET /api/v1/design/<session_id>/
   */
  async getDesignSession(sessionId) {
    return this.get(`/design/${sessionId}/`);
  }

  /**
   * List all design sessions
   * GET /api/v1/design/list/
   */
  async listDesignSessions() {
    return this.get('/design/list/');
  }

  /**
   * Submit to Hypar for external processing
   * POST /api/v1/design/hypar/auto-create/
   */
  async submitToHypar(sessionId, params = {}) {
    const body = {
      session_id: sessionId,
      ...params,
    };
    return this.post('/design/hypar/auto-create/', body);
  }

  /**
   * Generate fallback export package
   * POST /api/v1/design/hypar/bridge/
   */
  async generateBridgeExport(sessionId) {
    const body = { session_id: sessionId };
    return this.post('/design/hypar/bridge/', body);
  }

  /**
   * Get job status
   * GET /api/v1/design/jobs/<job_id>/
   */
  async getJobStatus(jobId) {
    return this.get(`/design/jobs/${jobId}/`);
  }

  /**
   * List all jobs
   * GET /api/v1/design/jobs/
   */
  async listJobs() {
    return this.get('/design/jobs/');
  }

  /**
   * PROJECTS API — Project management
   */

  /**
   * Create a new project
   * POST /api/v1/projects/
   */
  async createProject(params) {
    const body = {
      name: params.name || 'Untitled Project',
      description: params.description || '',
      location: params.location || '',
      plot_width_m: params.plotWidth || 30.0,
      plot_depth_m: params.plotDepth || 40.0,
      num_floors: params.numFloors || 2,
      building_type: params.buildingType || 'residential',
      region: params.region || '',
      use_vastu: params.useVastu || false,
    };
    return this.post('/projects/', body);
  }

  /**
   * List all projects for current user
   * GET /api/v1/projects/
   */
  async listProjects() {
    return this.get('/projects/');
  }

  /**
   * Get project details
   * GET /api/v1/projects/<project_id>/
   */
  async getProject(projectId) {
    return this.get(`/projects/${projectId}/`);
  }

  /**
   * Update project
   * PATCH /api/v1/projects/<project_id>/
   */
  async updateProject(projectId, params) {
    return this.patch(`/projects/${projectId}/`, params);
  }

  /**
   * Delete project
   * DELETE /api/v1/projects/<project_id>/
   */
  async deleteProject(projectId) {
    return this.delete(`/projects/${projectId}/`);
  }

  /**
   * Get project revisions
   * GET /api/v1/projects/<project_id>/revisions/
   */
  async getProjectRevisions(projectId) {
    return this.get(`/projects/${projectId}/revisions/`);
  }

  /**
   * Get specific revision
   * GET /api/v1/projects/<project_id>/revisions/<revision_id>/
   */
  async getProjectRevision(projectId, revisionId) {
    return this.get(`/projects/${projectId}/revisions/${revisionId}/`);
  }

  /**
   * Create project revision (save)
   * POST /api/v1/projects/<project_id>/revisions/
   */
  async saveProjectRevision(projectId, params) {
    const body = {
      title: params.title || 'Auto-saved revision',
      description: params.description || '',
      layout_data: params.layoutData || {},
      design_data: params.designData || {},
    };
    return this.post(`/projects/${projectId}/revisions/`, body);
  }

  /**
   * REPORTS API — Export and reporting
   */

  /**
   * Generate PDF report
   * POST /api/v1/reports/
   */
  async generateReport(params) {
    const body = {
      session_id: params.sessionId,
      revision_id: params.revisionId,
      report_type: params.reportType || 'pdf',
      include_compliance: params.includeCompliance !== false,
      include_vastu: params.includeVastu !== false,
    };
    return this.post('/reports/', body);
  }

  /**
   * Get report status
   * GET /api/v1/reports/<export_id>/
   */
  async getReportStatus(exportId) {
    return this.get(`/reports/${exportId}/`);
  }

  /**
   * Download report
   * GET /api/v1/reports/<export_id>/download/
   */
  async downloadReport(exportId) {
    // Returns a file, not JSON
    const url = `${this.baseUrl}/reports/${exportId}/download/`;
    return url; // Caller can use fetch or window.open
  }

  /**
   * Generate DXF export
   * POST /api/v1/reports/dxf/
   */
  async generateDXF(params) {
    const body = {
      session_id: params.sessionId,
      layout_data: params.layoutData || {},
      include_dimensions: params.includeDimensions !== false,
    };
    return this.post('/reports/dxf/', body);
  }

  /**
   * HEALTH / UTILITY API
   */

  /**
   * Check backend health
   * GET /api/v1/health/
   */
  async checkHealth() {
    try {
      return await this.get('/health/');
    } catch (error) {
      return { status: 'error', message: error.message };
    }
  }

  /**
   * Helper method: Parse compliance response into readable format
   */
  parseComplianceResponse(data) {
    const compliance = {
      passed: [],
      failed: [],
      warnings: [],
    };

    if (data.setback_violations) {
      compliance.failed.push(`Setback violations: ${data.setback_violations.join(', ')}`);
    }
    if (data.parking_deficit) {
      compliance.failed.push(`Parking deficit: ${data.parking_deficit} spaces needed`);
    }
    if (data.floor_constraint_violations) {
      compliance.failed.push(`Floor constraint violations: ${data.floor_constraint_violations.join(', ')}`);
    }

    if (data.setback_compliant) {
      compliance.passed.push('✓ Setback requirements met');
    }
    if (data.parking_compliant) {
      compliance.passed.push(`✓ Parking compliant (${data.parking_spaces} spaces)`);
    }
    if (data.floor_compliant) {
      compliance.passed.push('✓ Floor constraints met');
    }

    return compliance;
  }

  /**
   * Helper method: Format area values
   */
  formatArea(sqm) {
    return `${sqm.toFixed(2)} m²`;
  }

  /**
   * Helper method: Download file from URL
   */
  downloadFile(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
}

// Export as global or module
if (typeof module !== 'undefined' && module.exports) {
  module.exports = StudioAPI;
}

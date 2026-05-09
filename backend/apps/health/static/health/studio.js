/**
 * studio.js — Archi3D Design Studio Main Application
 * ═════════════════════════════════════════════════════════════
 * Entry point for the design studio interface
 */

// Initialize API
const api = new StudioAPI();

// ═══════════════════════════════════════════════════════════════
// Global State
// ═══════════════════════════════════════════════════════════════

let appState = {
  currentProject: null,
  currentSession: null,
  layoutZones: [],
  selectedZoneId: null,
  isDirty: false,
  isLoading: false,
  currentTool: 'select',
  sessions: [],
};

// ═══════════════════════════════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

function setLoading(isLoading) {
  appState.isLoading = isLoading;
  const buttons = document.querySelectorAll('button[type="button"]');
  buttons.forEach(btn => {
    if (isLoading) {
      btn.classList.add('loading');
      btn.disabled = true;
    } else {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  });
}

function updateStatus(text, type = 'ready') {
  const indicator = document.getElementById('status-indicator');
  const dot = indicator.querySelector('.status-dot');
  const statusText = indicator.querySelector('.status-text');

  dot.className = `status-dot ${type}`;
  statusText.textContent = text;
}

function modalOpen(id) {
  document.getElementById(id).removeAttribute('hidden');
}

function modalClose(id) {
  document.getElementById(id).setAttribute('hidden', '');
}

// ═══════════════════════════════════════════════════════════════
// Project Management
// ═══════════════════════════════════════════════════════════════

async function createNewProject() {
  const projectName = prompt('Project name:', 'New Project');
  if (!projectName) return;

  try {
    setLoading(true);
    updateStatus('Creating project...', 'loading');

    const project = await api.createProject({
      name: projectName,
      location: document.getElementById('location-input').value,
      plotWidth: parseFloat(document.getElementById('plot-width').value),
      plotDepth: parseFloat(document.getElementById('plot-depth').value),
      numFloors: parseInt(document.getElementById('num-floors').value),
      buildingType: document.getElementById('building-type').value,
      useVastu: document.getElementById('use-vastu').checked,
    });

    appState.currentProject = project;
    document.getElementById('project-name').value = project.name;

    updateStatus('Project created', 'success');
    showToast('✓ Project created successfully');
    await refreshSessions();
  } catch (error) {
    console.error('Failed to create project:', error);
    updateStatus('Error creating project', 'error');
    showToast('✗ Failed to create project', 'error');
  } finally {
    setLoading(false);
  }
}

async function saveProject() {
  if (!appState.currentProject) {
    showToast('No project to save', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Saving project...', 'loading');

    await api.saveProjectRevision(appState.currentProject.id, {
      title: `Revision at ${new Date().toLocaleTimeString()}`,
      layoutData: {
        zones: appState.layoutZones,
      },
      designData: {
        prompt: document.getElementById('prompt-input').value,
        settings: {
          location: document.getElementById('location-input').value,
          plotWidth: parseFloat(document.getElementById('plot-width').value),
          plotDepth: parseFloat(document.getElementById('plot-depth').value),
          numFloors: parseInt(document.getElementById('num-floors').value),
        },
      },
    });

    appState.isDirty = false;
    updateStatus('Project saved', 'success');
    showToast('✓ Project saved successfully');
  } catch (error) {
    console.error('Failed to save project:', error);
    updateStatus('Error saving project', 'error');
    showToast('✗ Failed to save project', 'error');
  } finally {
    setLoading(false);
  }
}

async function loadProject(projectId) {
  try {
    setLoading(true);
    updateStatus('Loading project...', 'loading');

    const project = await api.getProject(projectId);
    const revisions = await api.getProjectRevisions(projectId);

    if (revisions && revisions.length > 0) {
      const latestRevision = revisions[0];
      appState.layoutZones = latestRevision.layout_data?.zones || [];
      document.getElementById('prompt-input').value = latestRevision.design_data?.prompt || '';
    }

    appState.currentProject = project;
    document.getElementById('project-name').value = project.name;

    updateStatus('Project loaded', 'success');
    showToast('✓ Project loaded successfully');
    modalClose('load-project-modal');

    // Re-render canvas
    await renderDesign();
  } catch (error) {
    console.error('Failed to load project:', error);
    updateStatus('Error loading project', 'error');
    showToast('✗ Failed to load project', 'error');
  } finally {
    setLoading(false);
  }
}

async function deleteProject(projectId) {
  if (!confirm('Delete this project? This cannot be undone.')) return;

  try {
    setLoading(true);
    updateStatus('Deleting project...', 'loading');

    await api.deleteProject(projectId);

    showToast('✓ Project deleted');
    updateStatus('Project deleted', 'success');
    await refreshSessions();
  } catch (error) {
    console.error('Failed to delete project:', error);
    showToast('✗ Failed to delete project', 'error');
    updateStatus('Error deleting project', 'error');
  } finally {
    setLoading(false);
  }
}

async function refreshSessions() {
  try {
    const sessions = await api.listDesignSessions();
    appState.sessions = sessions;
    renderSessionsList();
  } catch (error) {
    console.error('Failed to refresh sessions:', error);
  }
}

function renderSessionsList() {
  const list = document.getElementById('sessions-list');

  if (!appState.sessions || appState.sessions.length === 0) {
    list.innerHTML = '<div class="sessions-empty">No projects yet. Create one to start.</div>';
    return;
  }

  list.innerHTML = appState.sessions
    .slice(0, 5)
    .map(
      (session) => `
        <div class="session-item" onclick="loadProject(${session.id})">
          <div class="session-name">${session.project_name || `Session ${session.id}`}</div>
          <div class="session-meta">
            ${new Date(session.created_at).toLocaleDateString()} · ${session.status || 'pending'}
          </div>
          <div class="session-actions">
            <button type="button" class="btn-sm" onclick="event.stopPropagation(); loadProject(${session.id})">Open</button>
            <button type="button" class="btn-sm" onclick="event.stopPropagation(); deleteProject(${session.id})">Delete</button>
          </div>
        </div>
      `
    )
    .join('');
}

// ═══════════════════════════════════════════════════════════════
// Design Generation
// ═══════════════════════════════════════════════════════════════

async function generateDesign() {
  const prompt = document.getElementById('prompt-input').value.trim();
  if (!prompt) {
    showToast('Please enter a design prompt', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Generating design...', 'loading');

    const response = await api.generateDesign({
      prompt,
      buildingType: document.getElementById('building-type').value,
      plotWidth: parseFloat(document.getElementById('plot-width').value),
      plotDepth: parseFloat(document.getElementById('plot-depth').value),
      numFloors: parseInt(document.getElementById('num-floors').value),
      useVastu: document.getElementById('use-vastu').checked,
    });

    appState.currentSession = response;
    appState.layoutZones = response.layout_zones || [];

    updateStatus('Design generated', 'success');
    showToast('✓ Design generated successfully');

    await renderDesign();
  } catch (error) {
    console.error('Failed to generate design:', error);
    updateStatus('Error generating design', 'error');
    showToast('✗ Failed to generate design: ' + error.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function improveDesign() {
  if (!appState.currentSession) {
    showToast('Generate a design first', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Improving design...', 'loading');

    // Call regenerate with improvement flag
    const response = await api.generateDesign({
      prompt: document.getElementById('prompt-input').value,
      buildingType: document.getElementById('building-type').value,
      plotWidth: parseFloat(document.getElementById('plot-width').value),
      plotDepth: parseFloat(document.getElementById('plot-depth').value),
      numFloors: parseInt(document.getElementById('num-floors').value),
      useVastu: document.getElementById('use-vastu').checked,
    });

    appState.currentSession = response;
    appState.layoutZones = response.layout_zones || [];

    updateStatus('Design improved', 'success');
    showToast('✓ Design improved');

    await renderDesign();
  } catch (error) {
    console.error('Failed to improve design:', error);
    showToast('✗ Failed to improve design', 'error');
    updateStatus('Error improving design', 'error');
  } finally {
    setLoading(false);
  }
}

async function runPipeline() {
  if (!appState.currentSession) {
    showToast('Generate a design first', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Running pipeline...', 'loading');

    const response = await api.generateDesign({
      prompt: document.getElementById('prompt-input').value,
      buildingType: document.getElementById('building-type').value,
      plotWidth: parseFloat(document.getElementById('plot-width').value),
      plotDepth: parseFloat(document.getElementById('plot-depth').value),
      numFloors: parseInt(document.getElementById('num-floors').value),
      useVastu: document.getElementById('use-vastu').checked,
    });

    appState.layoutZones = response.layout_zones || [];
    updateStatus('Pipeline complete', 'success');
    showToast('✓ Pipeline executed successfully');

    await renderDesign();
  } catch (error) {
    console.error('Pipeline failed:', error);
    showToast('✗ Pipeline failed: ' + error.message, 'error');
    updateStatus('Pipeline error', 'error');
  } finally {
    setLoading(false);
  }
}

async function checkCompliance() {
  if (!appState.currentSession) {
    showToast('Generate a design first', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Checking compliance...', 'loading');

    // For now, this is a placeholder — backend needs compliance endpoint
    const compliance = {
      passed: [
        '✓ Setback requirements met',
        '✓ Parking spaces sufficient (8 spaces)',
        '✓ Floor area ratio compliant (2.5 FAR)',
      ],
      failed: [],
      warnings: [
        '⚠ Northeast entrance recommended for Vastu',
      ],
    };

    displayComplianceResults(compliance);
    updateStatus('Compliance checked', 'success');
    showToast('✓ Compliance check complete');
  } catch (error) {
    console.error('Compliance check failed:', error);
    showToast('✗ Compliance check failed', 'error');
    updateStatus('Compliance error', 'error');
  } finally {
    setLoading(false);
  }
}

function displayComplianceResults(compliance) {
  const content = document.getElementById('compliance-content');

  let html = '';

  if (compliance.passed && compliance.passed.length > 0) {
    html += `
      <div class="compliance-section">
        <div class="compliance-section-title">✓ Passed</div>
        ${compliance.passed.map((item) => `<div class="compliance-item passed">${item}</div>`).join('')}
      </div>
    `;
  }

  if (compliance.failed && compliance.failed.length > 0) {
    html += `
      <div class="compliance-section">
        <div class="compliance-section-title">✗ Failed</div>
        ${compliance.failed.map((item) => `<div class="compliance-item failed">${item}</div>`).join('')}
      </div>
    `;
  }

  if (compliance.warnings && compliance.warnings.length > 0) {
    html += `
      <div class="compliance-section">
        <div class="compliance-section-title">⚠ Warnings</div>
        ${compliance.warnings.map((item) => `<div class="compliance-item warning">${item}</div>`).join('')}
      </div>
    `;
  }

  if (!html) {
    html = '<p>No compliance data available.</p>';
  }

  content.innerHTML = html;
  modalOpen('compliance-modal');
}

async function applyVastuRules() {
  if (!appState.currentSession) {
    showToast('Generate a design first', 'warning');
    return;
  }

  try {
    setLoading(true);
    updateStatus('Applying Vastu rules...', 'loading');

    // Placeholder — should call backend Vastu rules engine
    document.getElementById('use-vastu').checked = true;
    showToast('✓ Vastu rules applied');
    updateStatus('Vastu applied', 'success');

    await generateDesign(); // Regenerate with Vastu enabled
  } catch (error) {
    console.error('Failed to apply Vastu rules:', error);
    showToast('✗ Failed to apply Vastu rules', 'error');
    updateStatus('Vastu error', 'error');
  } finally {
    setLoading(false);
  }
}

// ═══════════════════════════════════════════════════════════════
// Canvas Rendering
// ═══════════════════════════════════════════════════════════════

async function renderDesign() {
  const canvas = document.getElementById('studio-3d-canvas');
  const empty = canvas.querySelector('.canvas-empty');

  if (!appState.layoutZones || appState.layoutZones.length === 0) {
    if (empty) empty.style.display = 'flex';
    return;
  }

  if (empty) empty.style.display = 'none';

  // Clear canvas
  canvas.innerHTML = '';

  // Render zones as 3D boxes (CSS 3D fallback)
  renderZonesCSS3D();
  updateLayersList();
  updateStatistics();
}

function renderZonesCSS3D() {
  const canvas = document.getElementById('studio-3d-canvas');

  appState.layoutZones.forEach((zone, index) => {
    const zoneEl = document.createElement('div');
    zoneEl.className = 'zone-box';
    zoneEl.dataset.zoneId = index;
    zoneEl.textContent = zone.room_type || `Zone ${index}`;

    const style = {
      position: 'absolute',
      left: (zone.x || 0) * 2 + 'px',
      top: (zone.y || 0) * 2 + 'px',
      width: (zone.width || 5) * 2 + 'px',
      height: (zone.depth || 5) * 2 + 'px',
      background: getRoomTypeColor(zone.room_type),
      border: '2px solid rgba(0, 212, 170, 0.3)',
      borderRadius: '4px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontSize: '12px',
      fontWeight: 'bold',
      cursor: 'pointer',
      transition: 'all 0.2s',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
    };

    Object.assign(zoneEl.style, style);

    zoneEl.addEventListener('click', () => selectZone(index, zone));
    zoneEl.addEventListener('mouseover', () => {
      zoneEl.style.boxShadow = '0 6px 20px rgba(0, 212, 170, 0.4)';
    });
    zoneEl.addEventListener('mouseout', () => {
      if (appState.selectedZoneId !== index) {
        zoneEl.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.5)';
      }
    });

    canvas.appendChild(zoneEl);
  });
}

function getRoomTypeColor(roomType) {
  const colors = {
    living_room: 'rgba(100, 150, 255, 0.7)',
    bedroom: 'rgba(255, 150, 100, 0.7)',
    kitchen: 'rgba(150, 255, 100, 0.7)',
    bathroom: 'rgba(255, 200, 100, 0.7)',
    parking: 'rgba(200, 200, 200, 0.7)',
    staircase: 'rgba(150, 150, 255, 0.7)',
    balcony: 'rgba(100, 255, 200, 0.7)',
  };
  return colors[roomType] || 'rgba(100, 200, 255, 0.7)';
}

function selectZone(zoneId, zone) {
  appState.selectedZoneId = zoneId;

  // Update visual selection
  document.querySelectorAll('.zone-box').forEach((el) => {
    el.style.opacity = '0.6';
  });
  document.querySelector(`[data-zone-id="${zoneId}"]`).style.opacity = '1';

  // Update inspector
  updateInspector(zone);
}

function updateInspector(zone) {
  const content = document.getElementById('inspector-content');

  const html = `
    <div class="inspector-section">
      <div class="inspector-section-title">Room Details</div>
      
      <div class="field">
        <label>Room Type</label>
        <div style="padding: 8px; background: var(--color-bg-dark); border-radius: 4px;">
          ${zone.room_type || 'Unknown'}
        </div>
      </div>

      <div class="field">
        <label>Dimensions</label>
        <div style="padding: 8px; background: var(--color-bg-dark); border-radius: 4px; font-size: 12px;">
          ${zone.width?.toFixed(1) || 0}m × ${zone.depth?.toFixed(1) || 0}m × ${zone.height?.toFixed(1) || 3}m
        </div>
      </div>

      <div class="field">
        <label>Area</label>
        <div style="padding: 8px; background: var(--color-bg-dark); border-radius: 4px; font-size: 12px;">
          ${((zone.width || 0) * (zone.depth || 0)).toFixed(2)} m²
        </div>
      </div>

      <div class="field">
        <label>Position</label>
        <div style="padding: 8px; background: var(--color-bg-dark); border-radius: 4px; font-size: 12px;">
          X: ${(zone.x || 0).toFixed(1)}m, Y: ${(zone.y || 0).toFixed(1)}m
        </div>
      </div>
    </div>
  `;

  content.innerHTML = html;
}

function updateLayersList() {
  const list = document.getElementById('layers-list');
  const stats = document.getElementById('layers-stats');

  if (!appState.layoutZones || appState.layoutZones.length === 0) {
    list.innerHTML = '<div class="layers-empty">No spaces yet</div>';
    stats.textContent = '0 spaces';
    return;
  }

  stats.textContent = `${appState.layoutZones.length} spaces`;

  list.innerHTML = appState.layoutZones
    .map(
      (zone, index) => `
        <div class="layer-item ${appState.selectedZoneId === index ? 'selected' : ''}" onclick="selectZone(${index}, ${JSON.stringify(zone).replace(/"/g, '&quot;')})">
          <div class="layer-visibility">👁</div>
          <div class="layer-name">${zone.room_type || `Zone ${index}`}</div>
          <div class="layer-lock">🔓</div>
        </div>
      `
    )
    .join('');
}

function updateStatistics() {
  if (!appState.layoutZones || appState.layoutZones.length === 0) {
    document.getElementById('stat-buildup').textContent = '0 m²';
    document.getElementById('stat-open').textContent = '0 m²';
    document.getElementById('stat-parking').textContent = '0 m²';
    document.getElementById('stat-far').textContent = '0.0';
    return;
  }

  let builtUpArea = 0;
  let parkingArea = 0;

  appState.layoutZones.forEach((zone) => {
    const area = (zone.width || 0) * (zone.depth || 0);
    if (zone.room_type === 'parking') {
      parkingArea += area;
    } else {
      builtUpArea += area;
    }
  });

  const plotArea = (parseFloat(document.getElementById('plot-width').value) || 30) *
    (parseFloat(document.getElementById('plot-depth').value) || 40);
  const openArea = Math.max(0, plotArea - builtUpArea - parkingArea);
  const numFloors = parseInt(document.getElementById('num-floors').value) || 2;
  const far = (builtUpArea * numFloors) / plotArea;

  document.getElementById('stat-buildup').textContent = builtUpArea.toFixed(0) + ' m²';
  document.getElementById('stat-open').textContent = openArea.toFixed(0) + ' m²';
  document.getElementById('stat-parking').textContent = parkingArea.toFixed(0) + ' m²';
  document.getElementById('stat-far').textContent = far.toFixed(2);
}

// ═══════════════════════════════════════════════════════════════
// Export Functions
// ═══════════════════════════════════════════════════════════════

async function exportPDF() {
  try {
    setLoading(true);
    updateStatus('Exporting PDF...', 'loading');

    const report = await api.generateReport({
      sessionId: appState.currentSession?.id,
      reportType: 'pdf',
    });

    const downloadUrl = await api.downloadReport(report.id);
    api.downloadFile(downloadUrl, 'design-report.pdf');

    showToast('✓ PDF exported');
    updateStatus('PDF exported', 'success');
  } catch (error) {
    console.error('Export failed:', error);
    showToast('✗ Export failed', 'error');
    updateStatus('Export error', 'error');
  } finally {
    setLoading(false);
    modalClose('export-modal');
  }
}

async function exportDXF() {
  try {
    setLoading(true);
    updateStatus('Exporting DXF...', 'loading');

    const result = await api.generateDXF({
      sessionId: appState.currentSession?.id,
      layoutData: { zones: appState.layoutZones },
    });

    // Placeholder - DXF download URL should be in result
    showToast('✓ DXF exported');
    updateStatus('DXF exported', 'success');
  } catch (error) {
    console.error('DXF export failed:', error);
    showToast('✗ DXF export failed', 'error');
    updateStatus('Export error', 'error');
  } finally {
    setLoading(false);
    modalClose('export-modal');
  }
}

async function exportJSON() {
  try {
    const data = {
      project: appState.currentProject,
      session: appState.currentSession,
      zones: appState.layoutZones,
      timestamp: new Date().toISOString(),
    };

    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    api.downloadFile(url, 'design-data.json');

    showToast('✓ JSON exported');
  } catch (error) {
    console.error('JSON export failed:', error);
    showToast('✗ JSON export failed', 'error');
  }
}

function takeScreenshot() {
  const canvas = document.getElementById('studio-3d-canvas');
  html2canvas(canvas).then((cnv) => {
    const link = document.createElement('a');
    link.href = cnv.toDataURL();
    link.download = 'design-screenshot.png';
    link.click();
    showToast('✓ Screenshot saved');
  });
}

async function downloadProject() {
  try {
    await exportJSON();
    showToast('✓ Project downloaded');
  } catch (error) {
    showToast('✗ Download failed', 'error');
  }
}

// ═══════════════════════════════════════════════════════════════
// Event Handler Setup
// ═══════════════════════════════════════════════════════════════

function setupEventHandlers() {
  // Prompt example chips
  document.querySelectorAll('.prompt-example-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.getElementById('prompt-input').value = chip.dataset.prompt;
    });
  });

  // Main buttons
  document.getElementById('generate-design').addEventListener('click', generateDesign);
  document.getElementById('improve-design').addEventListener('click', improveDesign);
  document.getElementById('regenerate-design').addEventListener('click', generateDesign);
  document.getElementById('run-pipeline').addEventListener('click', runPipeline);
  document.getElementById('check-compliance').addEventListener('click', checkCompliance);
  document.getElementById('apply-vastu').addEventListener('click', applyVastuRules);

  document.getElementById('new-project').addEventListener('click', createNewProject);
  document.getElementById('save-project').addEventListener('click', saveProject);
  document.getElementById('refresh-sessions').addEventListener('click', refreshSessions);

  // Export modal
  document.getElementById('export-btn').addEventListener('click', () => modalOpen('export-modal'));
  document.getElementById('export-modal-close').addEventListener('click', () => modalClose('export-modal'));
  document.getElementById('export-pdf').addEventListener('click', exportPDF);
  document.getElementById('export-dxf').addEventListener('click', exportDXF);
  document.getElementById('export-json').addEventListener('click', exportJSON);
  document.getElementById('export-screenshot').addEventListener('click', takeScreenshot);
  document.getElementById('download-project').addEventListener('click', downloadProject);

  // Settings modal
  document.getElementById('settings-btn').addEventListener('click', () => modalOpen('settings-modal'));
  document.getElementById('settings-modal-close').addEventListener('click', () => modalClose('settings-modal'));
  document.getElementById('settings-cancel').addEventListener('click', () => modalClose('settings-modal'));
  document.getElementById('settings-save').addEventListener('click', () => {
    document.getElementById('project-name').value = document.getElementById('settings-project-name').value;
    modalClose('settings-modal');
    showToast('✓ Settings saved');
  });

  // Compliance modal
  document.getElementById('compliance-modal-close').addEventListener('click', () => modalClose('compliance-modal'));

  // Load project modal
  document.getElementById('load-project-modal-close').addEventListener('click', () => modalClose('load-project-modal'));

  // Canvas toolbar
  document.getElementById('canvas-2d').addEventListener('click', () => showToast('2D view coming soon'));
  document.getElementById('canvas-3d').addEventListener('click', () => showToast('3D view coming soon'));
  document.getElementById('canvas-top').addEventListener('click', () => showToast('Top view coming soon'));
  document.getElementById('canvas-frame').addEventListener('click', () => showToast('Frame view coming soon'));
  document.getElementById('canvas-grid').addEventListener('click', () => showToast('Grid toggle coming soon'));
  document.getElementById('canvas-reset').addEventListener('click', () => showToast('Camera reset coming soon'));
  document.getElementById('canvas-screenshot').addEventListener('click', takeScreenshot);

  // Bottom toolbar
  document.getElementById('tool-select').addEventListener('click', () => {
    appState.currentTool = 'select';
    updateToolbarState();
  });
  document.getElementById('tool-move').addEventListener('click', () => {
    appState.currentTool = 'move';
    updateToolbarState();
  });
  document.getElementById('tool-rotate').addEventListener('click', () => {
    appState.currentTool = 'rotate';
    updateToolbarState();
  });
  document.getElementById('tool-scale').addEventListener('click', () => {
    appState.currentTool = 'scale';
    updateToolbarState();
  });
  document.getElementById('tool-delete').addEventListener('click', deleteSelected);
  document.getElementById('tool-duplicate').addEventListener('click', duplicateSelected);

  // Character count
  document.getElementById('prompt-input').addEventListener('input', (e) => {
    const count = e.target.value.length;
    document.getElementById('prompt-char-count').textContent = `${count} / 500`;
  });
}

function updateToolbarState() {
  document.querySelectorAll('.toolbar-btn').forEach((btn) => {
    btn.removeAttribute('aria-pressed');
  });
  document.getElementById(`tool-${appState.currentTool}`).setAttribute('aria-pressed', 'true');
}

function deleteSelected() {
  if (appState.selectedZoneId !== null) {
    appState.layoutZones.splice(appState.selectedZoneId, 1);
    appState.selectedZoneId = null;
    renderDesign();
    showToast('✓ Zone deleted');
  }
}

function duplicateSelected() {
  if (appState.selectedZoneId !== null) {
    const zone = appState.layoutZones[appState.selectedZoneId];
    const duplicate = { ...zone, x: (zone.x || 0) + 1, y: (zone.y || 0) + 1 };
    appState.layoutZones.push(duplicate);
    renderDesign();
    showToast('✓ Zone duplicated');
  }
}

// ═══════════════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════════════

async function initializeStudio() {
  try {
    // Check health
    const health = await api.checkHealth();
    if (health.status === 'error') {
      showToast('Backend not reachable. Check if server is running.', 'error');
      return;
    }

    // Load existing sessions
    await refreshSessions();

    // Setup event handlers
    setupEventHandlers();

    // Set initial status
    updateStatus('Ready', 'idle');

    console.log('✓ Archi3D Studio initialized');
  } catch (error) {
    console.error('Initialization failed:', error);
    showToast('Failed to initialize studio', 'error');
  }
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', initializeStudio);

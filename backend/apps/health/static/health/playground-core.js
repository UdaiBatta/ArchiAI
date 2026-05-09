/* ════════════════════════════════════════════════════════════════
       STATE
       ════════════════════════════════════════════════════════════════ */
    let lastRequestPayload = {};
    let lastResponseText = '';

    const buttons = {
      autoCreate: document.getElementById('auto-create'),
      run: document.getElementById('run'),
      bridge: document.getElementById('bridge'),
    };

    const reportControls = {
      create: document.getElementById('create-report'),
      refresh: document.getElementById('refresh-report'),
      downloadPdf: document.getElementById('download-report'),
      downloadDxf: document.getElementById('download-dxf'),
    };

    const reportFields = {
      token: document.getElementById('report_access_token'),
      revisionId: document.getElementById('report_revision_id'),
      exportId: document.getElementById('report_export_id'),
      statusPill: document.getElementById('report-status-pill'),
      statusNote: document.getElementById('report-status-note'),
      output: document.getElementById('report-out'),
    };

    const studioControls = {
      promptTemplate: document.getElementById('prompt-template'),
      loadPromptTemplate: document.getElementById('load-prompt-template'),
      copyPromptTemplate: document.getElementById('copy-prompt-template'),
      floorSelect: document.getElementById('studio-floor-select'),
      zoneSelect: document.getElementById('studio-zone-select'),
      zoneRoomType: document.getElementById('studio-zone-room-type'),
      zoneFloor: document.getElementById('studio-zone-floor'),
      zoneX: document.getElementById('studio-zone-x'),
      zoneY: document.getElementById('studio-zone-y'),
      zoneWidth: document.getElementById('studio-zone-width'),
      zoneDepth: document.getElementById('studio-zone-depth'),
      zoneOrientation: document.getElementById('studio-zone-orientation'),
      zoneStreetFacing: document.getElementById('studio-zone-street-facing'),
      zoneList: document.getElementById('studio-zone-list'),
      zoneSummary: document.getElementById('studio-zone-summary'),
      layoutJson: document.getElementById('studio-layout-json'),
      canvas: document.getElementById('studio-layout-canvas'),
      empty: document.getElementById('studio-layout-empty'),
      applyLayout: document.getElementById('studio-apply-layout'),
      resetLayout: document.getElementById('studio-reset-layout'),
    };

    let lastReportExport = null;
    let studioBaseLayoutZones = [];
    let studioDraftLayoutZones = [];
    let studioSelectedZoneId = '';
    let studioSelectedFloor = '';
    let studioDragState = null;

    const storedReportToken = window.localStorage.getItem('archi3d_report_access_token') || '';
    if (reportFields.token) {
      reportFields.token.value = storedReportToken;
    }

    /* ════════════════════════════════════════════════════════════════
       CHAR COUNTER
       ════════════════════════════════════════════════════════════════ */
    const rawTextEl = document.getElementById('raw_text');
    const charCount = document.getElementById('char-count-raw');
    function updateCharCount() {
      charCount.textContent = rawTextEl.value.length + ' / 500';
    }
    rawTextEl.addEventListener('input', updateCharCount);
    updateCharCount();

    /* ════════════════════════════════════════════════════════════════
       ACCORDION
       ════════════════════════════════════════════════════════════════ */
    const accToggle = document.getElementById('advanced-options-toggle');
    const accBody = document.getElementById('advanced-options-body');
    accToggle.addEventListener('click', () => {
      const expanded = accToggle.getAttribute('aria-expanded') === 'true';
      accToggle.setAttribute('aria-expanded', String(!expanded));
      accBody.classList.toggle('open', !expanded);
    });

    /* ════════════════════════════════════════════════════════════════
       TOAST NOTIFICATIONS
       ════════════════════════════════════════════════════════════════ */
    function showToast(msg, type = 'ok') {
      const container = document.getElementById('toast-container');
      const icons = { ok: '✅', warn: '⚠️', bad: '❌' };
      const t = document.createElement('div');
      t.className = 'toast ' + type;
      t.innerHTML = '<span>' + icons[type] + '</span> ' + msg;
      container.appendChild(t);
      setTimeout(() => { if (t.parentNode) t.parentNode.removeChild(t); }, 3100);
    }

    /* ════════════════════════════════════════════════════════════════
       DOM HELPERS
       ════════════════════════════════════════════════════════════════ */
    function setText(id, value) {
      const el = document.getElementById(id);
      if (el) el.textContent = String(value || '—');
    }

    function setStage(name, state, note) {
      const stage = document.getElementById('stage-' + name);
      const stageNote = document.getElementById('stage-note-' + name);
      if (!stage || !stageNote) return;
      stage.className = 'stage stage-' + state;
      stageNote.textContent = note;
    }

    function setStatus(kind, note) {
      const pill = document.getElementById('status-pill');
      const noteEl = document.getElementById('status-note');
      const labels = {
        'pill-run': 'Running',
        'pill-ok': 'Success',
        'pill-warn': 'Fallback',
        'pill-bad': 'Error',
        'pill-idle': 'Idle',
      };
      pill.className = 'pill ' + kind;
      pill.textContent = labels[kind] || kind;
      noteEl.textContent = note;
    }

    function setBusy(btn, isBusy) {
      btn.disabled = isBusy;
      btn.classList.toggle('is-loading', isBusy);
      btn.setAttribute('aria-busy', String(isBusy));
    }

    function setAllBusy(isBusy) {
      Object.values(buttons).forEach(b => setBusy(b, isBusy));
    }

    function setReportStatus(kind, note) {
      const labels = {
        'pill-run': 'Working',
        'pill-ok': 'Ready',
        'pill-warn': 'Waiting',
        'pill-bad': 'Error',
        'pill-idle': 'Idle',
      };
      reportFields.statusPill.className = 'pill ' + kind;
      reportFields.statusPill.textContent = labels[kind] || kind;
      reportFields.statusNote.textContent = note;
    }

    function setReportBusy(isBusy) {
      Object.values(reportControls).forEach(btn => setBusy(btn, isBusy));
    }

    function cloneStudioZones(zones) {
      return JSON.parse(JSON.stringify(Array.isArray(zones) ? zones : []));
    }

    function getStudioFloorNumbers(zones) {
      return Array.from(new Set((zones || []).map(zone => Number(zone.floor || 0)))).sort((a, b) => a - b);
    }

    function getStudioRoomLabel(roomType) {
      return String(roomType || 'space').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
    }

    function getStudioRoomColor(roomType) {
      const colors = {
        living_room: '#38bdf8',
        kitchen: '#f59e0b',
        bedroom: '#5ef5d0',
        master_room: '#00d4aa',
        bathroom: '#a78bfa',
        staircase: '#f43f5e',
        parking: '#00c2e0',
        dining_room: '#10b981',
        balcony: '#8b95b8',
        entrance: '#60a5fa',
        multi_use: '#8b95b8',
      };
      return colors[String(roomType || '').toLowerCase()] || '#8b95b8';
    }

    function getStudioCanvasMetrics() {
      const canvas = studioControls.canvas;
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(320, rect.width || 320);
      const height = Math.max(320, rect.height || 320);
      const margin = 28;
      const zones = studioDraftLayoutZones.length ? studioDraftLayoutZones : [];
      const maxX = Math.max(...zones.map(zone => Number(zone.x || 0) + Number(zone.width_m || 0)), 1);
      const maxY = Math.max(...zones.map(zone => Number(zone.y || 0) + Number(zone.depth_m || 0)), 1);
      const paddedWidth = maxX + Math.max(2, maxX * 0.08);
      const paddedHeight = maxY + Math.max(2, maxY * 0.08);
      const scale = Math.min((width - margin * 2) / paddedWidth, (height - margin * 2) / paddedHeight);
      const offsetX = margin + ((width - margin * 2) - paddedWidth * scale) / 2;
      const offsetY = margin + ((height - margin * 2) - paddedHeight * scale) / 2;
      return { canvas, rect, width, height, margin, scale, offsetX, offsetY, paddedWidth, paddedHeight };
    }

    function getStudioClientPoint(event, metrics) {
      if (!metrics.rect.width || !metrics.rect.height) {
        return { x: 0, y: 0 };
      }
      const svgX = (event.clientX - metrics.rect.left) * (metrics.width / metrics.rect.width);
      const svgY = (event.clientY - metrics.rect.top) * (metrics.height / metrics.rect.height);
      return {
        x: (svgX - metrics.offsetX) / metrics.scale,
        y: (svgY - metrics.offsetY) / metrics.scale,
      };
    }

    function beginStudioZoneDrag(zoneId, event) {
      if (!event || event.button !== 0) return;
      const targetZone = studioDraftLayoutZones.find(zone => String(zone.id) === String(zoneId));
      if (!targetZone) return;

      studioSelectedZoneId = String(targetZone.id);
      studioSelectedFloor = String(targetZone.floor);
      studioControls.floorSelect.value = studioSelectedFloor;
      studioControls.zoneSelect.value = studioSelectedZoneId;
      syncStudioInspectorFromSelection();

      const metrics = getStudioCanvasMetrics();
      const pointer = getStudioClientPoint(event, metrics);

      studioDragState = {
        zoneId: String(targetZone.id),
        startPointerX: pointer.x,
        startPointerY: pointer.y,
        startZoneX: Number(targetZone.x || 0),
        startZoneY: Number(targetZone.y || 0),
        moved: false,
      };

      studioControls.canvas.classList.add('is-dragging');
      event.preventDefault();
      event.stopPropagation();
    }

    function getStudioZoneAtPoint(point) {
      const visibleZones = getStudioVisibleZones();
      for (let index = visibleZones.length - 1; index >= 0; index -= 1) {
        const zone = visibleZones[index];
        const x = Number(zone.x || 0);
        const y = Number(zone.y || 0);
        const width = Number(zone.width_m || 0);
        const depth = Number(zone.depth_m || 0);
        if (point.x >= x && point.x <= x + width && point.y >= y && point.y <= y + depth) {
          return zone;
        }
      }
      return null;
    }

    function handleStudioCanvasPointerDown(event) {
      if (!event || event.button !== 0) return;
      const metrics = getStudioCanvasMetrics();
      const point = getStudioClientPoint(event, metrics);
      const zone = getStudioZoneAtPoint(point);
      if (!zone) return;
      beginStudioZoneDrag(zone.id, event);
    }

    function updateStudioZoneDrag(event) {
      if (!studioDragState) return;
      const zone = studioDraftLayoutZones.find(item => String(item.id) === String(studioDragState.zoneId));
      if (!zone) return;

      const metrics = getStudioCanvasMetrics();
      const pointer = getStudioClientPoint(event, metrics);
      const deltaX = pointer.x - studioDragState.startPointerX;
      const deltaY = pointer.y - studioDragState.startPointerY;

      zone.x = Math.max(0, Number((studioDragState.startZoneX + deltaX).toFixed(3)));
      zone.y = Math.max(0, Number((studioDragState.startZoneY + deltaY).toFixed(3)));
      zone.area_sqm = Number((Number(zone.width_m || 0) * Number(zone.depth_m || 0)).toFixed(2));

      studioDragState.moved = true;
      studioControls.zoneX.value = zone.x;
      studioControls.zoneY.value = zone.y;
      studioControls.layoutJson.textContent = JSON.stringify(studioDraftLayoutZones, null, 2);
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
    }

    function endStudioZoneDrag() {
      if (!studioDragState) return;
      studioControls.canvas.classList.remove('is-dragging');
      studioDragState = null;
    }

    function getStudioSelectedZone() {
      return studioDraftLayoutZones.find(zone => String(zone.id) === String(studioSelectedZoneId)) || null;
    }

    function getStudioVisibleZones() {
      if (!studioSelectedFloor && studioDraftLayoutZones.length > 0) {
        const floors = getStudioFloorNumbers(studioDraftLayoutZones);
        studioSelectedFloor = String(floors[0]);
      }

      if (!studioSelectedFloor) {
        return [];
      }

      return studioDraftLayoutZones.filter(zone => String(zone.floor) === String(studioSelectedFloor));
    }

    function refreshStudioFloorSelect() {
      const floors = getStudioFloorNumbers(studioDraftLayoutZones);
      const previousFloor = studioSelectedFloor;

      studioControls.floorSelect.innerHTML = '';
      if (floors.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No floors yet';
        studioControls.floorSelect.appendChild(option);
        studioControls.floorSelect.disabled = true;
        studioSelectedFloor = '';
        return;
      }

      studioControls.floorSelect.disabled = false;
      floors.forEach(floor => {
        const option = document.createElement('option');
        option.value = String(floor);
        option.textContent = 'Floor ' + floor;
        studioControls.floorSelect.appendChild(option);
      });

      if (previousFloor && floors.some(floor => String(floor) === String(previousFloor))) {
        studioSelectedFloor = String(previousFloor);
      } else {
        studioSelectedFloor = String(floors[0]);
      }

      studioControls.floorSelect.value = studioSelectedFloor;
    }

    function refreshStudioZoneSelect() {
      const visibleZones = getStudioVisibleZones();
      const previousSelection = studioSelectedZoneId;
      studioControls.zoneSelect.innerHTML = '';

      if (visibleZones.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No rooms on this floor';
        studioControls.zoneSelect.appendChild(option);
        studioControls.zoneSelect.disabled = true;
        studioSelectedZoneId = '';
        return;
      }

      studioControls.zoneSelect.disabled = false;
      visibleZones.forEach(zone => {
        const option = document.createElement('option');
        option.value = String(zone.id);
        option.textContent = getStudioRoomLabel(zone.room_type) + ' · ' + Number(zone.width_m || 0).toFixed(1) + 'm × ' + Number(zone.depth_m || 0).toFixed(1) + 'm';
        studioControls.zoneSelect.appendChild(option);
      });

      if (previousSelection && visibleZones.some(zone => String(zone.id) === String(previousSelection))) {
        studioSelectedZoneId = String(previousSelection);
      } else {
        studioSelectedZoneId = String(visibleZones[0].id);
      }

      studioControls.zoneSelect.value = studioSelectedZoneId;
    }

    function syncStudioInspectorFromSelection() {
      const selectedZone = getStudioSelectedZone();
      if (!selectedZone) {
        studioControls.zoneSummary.textContent = 'Select a room to edit it.';
        studioControls.layoutJson.textContent = studioDraftLayoutZones.length ? JSON.stringify(studioDraftLayoutZones, null, 2) : 'No layout loaded yet.';
        return;
      }

      studioControls.zoneRoomType.value = selectedZone.room_type || '';
      studioControls.zoneFloor.value = selectedZone.floor ?? 0;
      studioControls.zoneX.value = selectedZone.x ?? 0;
      studioControls.zoneY.value = selectedZone.y ?? 0;
      studioControls.zoneWidth.value = selectedZone.width_m ?? 0;
      studioControls.zoneDepth.value = selectedZone.depth_m ?? 0;
      studioControls.zoneOrientation.value = selectedZone.orientation || '';
      studioControls.zoneStreetFacing.value = selectedZone.street_facing ? 'true' : 'false';

      studioControls.zoneSummary.textContent =
        getStudioRoomLabel(selectedZone.room_type) +
        ' on floor ' + selectedZone.floor +
        ' · area ' + Number(selectedZone.area_sqm || 0).toFixed(2) + ' sqm';
      studioControls.layoutJson.textContent = JSON.stringify(studioDraftLayoutZones, null, 2);
    }

    function renderStudioZoneCards() {
      const visibleZones = getStudioVisibleZones();
      studioControls.zoneList.innerHTML = '';

      if (visibleZones.length === 0) {
        studioControls.zoneList.innerHTML = '<div class="studio-note">No rooms on this floor yet.</div>';
        return;
      }

      visibleZones.forEach(zone => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'studio-zone-card' + (String(zone.id) === String(studioSelectedZoneId) ? ' is-active' : '');
        button.innerHTML =
          '<div class="studio-zone-title">' + getStudioRoomLabel(zone.room_type) + '</div>' +
          '<div class="studio-zone-meta">Floor ' + zone.floor + ' · ' + Number(zone.width_m || 0).toFixed(1) + 'm × ' + Number(zone.depth_m || 0).toFixed(1) + 'm · x ' + Number(zone.x || 0).toFixed(1) + ', y ' + Number(zone.y || 0).toFixed(1) + '</div>';
        button.addEventListener('click', () => {
          studioSelectedZoneId = String(zone.id);
          studioSelectedFloor = String(zone.floor);
          studioControls.floorSelect.value = studioSelectedFloor;
          studioControls.zoneSelect.value = studioSelectedZoneId;
          syncStudioInspectorFromSelection();
          renderStudioCanvas();
          renderStudioZoneCards();
        });
        studioControls.zoneList.appendChild(button);
      });
    }

    function renderStudioCanvas() {
      const sceneBridge = window.Archi3DStudioScene;
      const zones = studioDraftLayoutZones.length ? cloneStudioZones(studioDraftLayoutZones) : [];
      studioControls.empty.hidden = zones.length > 0;

      if (sceneBridge && typeof sceneBridge.update === 'function') {
        sceneBridge.update({
          zones,
          selectedZoneId: studioSelectedZoneId,
          selectedFloor: studioSelectedFloor,
          selectedZone: getStudioSelectedZone(),
        });
        return;
      }

      if (studioControls.empty) {
        studioControls.empty.hidden = false;
        studioControls.empty.textContent = zones.length
          ? 'Loading 3D workspace…'
          : 'Run the pipeline to generate a Hypar-ready concept. The workspace will appear here.';
      }
    }

    function syncStudioLayoutFromPayload(payload) {
      const zones = Array.isArray(payload && payload.layout_zones) ? payload.layout_zones : [];
      studioBaseLayoutZones = cloneStudioZones(zones);
      studioDraftLayoutZones = cloneStudioZones(zones);
      studioSelectedZoneId = zones.length ? String(zones[0].id) : '';
      studioSelectedFloor = zones.length ? String(zones[0].floor) : '';
      refreshStudioFloorSelect();
      refreshStudioZoneSelect();
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
    }

    function resetStudioDraft() {
      studioDraftLayoutZones = cloneStudioZones(studioBaseLayoutZones);
      studioSelectedZoneId = studioDraftLayoutZones.length ? String(studioDraftLayoutZones[0].id) : '';
      studioSelectedFloor = studioDraftLayoutZones.length ? String(studioDraftLayoutZones[0].floor) : '';
      refreshStudioFloorSelect();
      refreshStudioZoneSelect();
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
      setReportStatus('pill-idle', 'Draft layout reset to the last generated version.');
    }

    function syncStudioSelectedZoneFromInspector() {
      return;

      const selectedZone = getStudioSelectedZone();
      if (!selectedZone) return;

      const floorValue = parseInt(studioControls.zoneFloor.value, 10);
      const xValue = parseFloat(studioControls.zoneX.value);
      const yValue = parseFloat(studioControls.zoneY.value);
      const widthValue = parseFloat(studioControls.zoneWidth.value);
      const depthValue = parseFloat(studioControls.zoneDepth.value);
      const orientationValue = String(studioControls.zoneOrientation.value || '').trim();
      const streetFacingValue = studioControls.zoneStreetFacing.value === 'true';

      selectedZone.room_type = String(studioControls.zoneRoomType.value || selectedZone.room_type || 'space').trim() || 'space';
      if (!Number.isNaN(floorValue)) selectedZone.floor = floorValue;
      if (!Number.isNaN(xValue)) selectedZone.x = Number(xValue.toFixed(3));
      if (!Number.isNaN(yValue)) selectedZone.y = Number(yValue.toFixed(3));
      if (!Number.isNaN(widthValue)) selectedZone.width_m = Math.max(0.1, Number(widthValue.toFixed(3)));
      if (!Number.isNaN(depthValue)) selectedZone.depth_m = Math.max(0.1, Number(depthValue.toFixed(3)));
      selectedZone.orientation = orientationValue;
      selectedZone.street_facing = streetFacingValue;
      selectedZone.area_sqm = Number((selectedZone.width_m * selectedZone.depth_m).toFixed(2));
      selectedZone.target_area_sqm = Number((selectedZone.target_area_sqm || selectedZone.area_sqm).toFixed(2));

      if (String(selectedZone.floor) !== String(studioSelectedFloor)) {
        studioSelectedFloor = String(selectedZone.floor);
        studioControls.floorSelect.value = studioSelectedFloor;
      }

      studioControls.layoutJson.textContent = JSON.stringify(studioDraftLayoutZones, null, 2);
      refreshStudioZoneSelect();
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
    }

    window.addEventListener('archi3d-scene-ready', renderStudioCanvas);
    window.addEventListener('archi3d-zone-selected', function (event) {
      const zoneId = String(event && event.detail && event.detail.zoneId ? event.detail.zoneId : '');
      if (!zoneId) return;

      const selectedZone = studioDraftLayoutZones.find(zone => String(zone.id) === zoneId);
      if (!selectedZone) return;

      studioSelectedZoneId = zoneId;
      studioSelectedFloor = String(selectedZone.floor);
      studioControls.floorSelect.value = studioSelectedFloor;
      refreshStudioFloorSelect();
      refreshStudioZoneSelect();
      syncStudioInspectorFromSelection();
      renderStudioZoneCards();
      renderStudioCanvas();
    });

    function applyStudioDraftToPipeline() {
      if (!studioDraftLayoutZones.length) {
        showToast('Generate a layout first, then edit it.', 'warn');
        return;
      }
      runEndpoint('/api/v1/design/', 'Applying edited layout…', {
        layout_zones_override: studioDraftLayoutZones,
      });
    }

    function syncReportToken() {
      const token = String(reportFields.token.value || '').trim();
      if (token) {
        window.localStorage.setItem('archi3d_report_access_token', token);
      } else {
        window.localStorage.removeItem('archi3d_report_access_token');
      }
    }

    if (reportFields.token) {
      reportFields.token.addEventListener('input', syncReportToken);
    }

    function getReportAuthHeaders() {
      const token = String(reportFields.token.value || '').trim();
      if (!token) return null;
      return { 'Authorization': 'Bearer ' + token };
    }

    function reportExportToText(exportData) {
      if (!exportData) return 'No report export requested yet.';
      return JSON.stringify(exportData, null, 2);
    }

    function renderReportExport(exportData, note) {
      lastReportExport = exportData || null;
      if (exportData && exportData.id && reportFields.exportId) {
        reportFields.exportId.value = exportData.id;
      }
      reportFields.output.textContent = reportExportToText(exportData);
      if (note) {
        setReportStatus(exportData && exportData.status === 'ready' ? 'pill-ok' : 'pill-run', note);
      } else if (exportData && exportData.status === 'ready') {
        setReportStatus('pill-ok', 'Report is ready for download.');
      } else if (exportData && exportData.status === 'failed') {
        setReportStatus('pill-bad', exportData.error_message || 'Report generation failed.');
      }
    }

    function ensureReportToken() {
      const headers = getReportAuthHeaders();
      if (!headers) {
        setReportStatus('pill-warn', 'Paste a JWT access token first.');
        showToast('Reports need a JWT access token.', 'warn');
        return null;
      }
      syncReportToken();
      return headers;
    }

    async function fetchReportJson(endpoint, options = {}) {
      const headers = ensureReportToken();
      if (!headers) return null;

      const response = await fetch(endpoint, {
        method: options.method || 'GET',
        headers: {
          ...headers,
          ...(options.json ? { 'Content-Type': 'application/json' } : {}),
        },
        credentials: 'same-origin',
        body: options.json ? JSON.stringify(options.json) : undefined,
      });

      const text = await response.text();
      let payload = null;
      try { payload = JSON.parse(text); } catch (error) { payload = null; }
      return { response, text, payload };
    }

    async function downloadBinary(endpoint, filename, method = 'GET', jsonBody = null) {
      const headers = ensureReportToken();
      if (!headers) return;

      setReportBusy(true);
      try {
        const response = await fetch(endpoint, {
          method,
          headers: {
            ...headers,
            ...(jsonBody ? { 'Content-Type': 'application/json' } : {}),
          },
          credentials: 'same-origin',
          body: jsonBody ? JSON.stringify(jsonBody) : undefined,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || response.statusText || 'Download failed');
        }

        const blob = await response.blob();
        const objectUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(objectUrl);
      } finally {
        setReportBusy(false);
      }
    }

    async function createReportExport() {
      const revisionId = parseInt(reportFields.revisionId.value, 10);
      if (!revisionId) {
        setReportStatus('pill-warn', 'Enter a revision ID first.');
        showToast('Revision ID is required.', 'warn');
        return;
      }

      if (!ensureReportToken()) return;

      setReportBusy(true);
      setReportStatus('pill-run', 'Generating PDF report…');
      try {
        const result = await fetchReportJson('/api/v1/reports/', {
          method: 'POST',
          json: { revision_id: revisionId },
        });

        if (!result) return;
        const payload = result.payload || { detail: result.text };
        renderReportExport(payload, payload.status === 'ready' ? 'Report ready.' : 'Report generation requested.');

        if (!result.response.ok && result.response.status !== 202) {
          throw new Error(payload.detail || result.response.statusText || 'Report generation failed');
        }

        showToast('Report export requested.', 'ok');
      } catch (error) {
        setReportStatus('pill-bad', String(error.message || error));
        showToast('Report generation failed.', 'bad');
      } finally {
        setReportBusy(false);
      }
    }

    async function refreshReportExport() {
      const exportId = parseInt(reportFields.exportId.value || (lastReportExport && lastReportExport.id) || '', 10);
      if (!exportId) {
        setReportStatus('pill-warn', 'Enter a report export ID first.');
        showToast('Report export ID is required for refresh.', 'warn');
        return;
      }

      setReportBusy(true);
      setReportStatus('pill-run', 'Refreshing report status…');
      try {
        const result = await fetchReportJson('/api/v1/reports/' + exportId + '/');
        if (!result) return;
        if (!result.response.ok) {
          throw new Error((result.payload && result.payload.detail) || result.text || result.response.statusText || 'Could not load report status');
        }
        renderReportExport(result.payload, 'Report status refreshed.');
      } catch (error) {
        setReportStatus('pill-bad', String(error.message || error));
        showToast('Could not refresh report status.', 'bad');
      } finally {
        setReportBusy(false);
      }
    }

    async function downloadReportPdf() {
      const exportId = parseInt(reportFields.exportId.value || (lastReportExport && lastReportExport.id) || '', 10);
      if (!exportId) {
        setReportStatus('pill-warn', 'Create or enter a report export ID first.');
        showToast('No report export ID available.', 'warn');
        return;
      }

      await downloadBinary('/api/v1/reports/' + exportId + '/download/', 'report_' + exportId + '.pdf');
      setReportStatus('pill-ok', 'PDF download triggered.');
      showToast('PDF download started.', 'ok');
    }

    async function exportDxf() {
      const revisionId = parseInt(reportFields.revisionId.value, 10);
      if (!revisionId) {
        setReportStatus('pill-warn', 'Enter a revision ID first.');
        showToast('Revision ID is required for DXF export.', 'warn');
        return;
      }

      await downloadBinary('/api/v1/reports/dxf/', 'revision_' + revisionId + '.dxf', 'POST', { revision_id: revisionId });
      setReportStatus('pill-ok', 'DXF download triggered.');
      showToast('DXF export started.', 'ok');
    }


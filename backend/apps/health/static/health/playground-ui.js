    /* ════════════════════════════════════════════════════════════════
       SESSION HISTORY
       ════════════════════════════════════════════════════════════════ */
    function statusDotClass(s) {
      const m = {
        completed: 'dot-ok', compliance_checked: 'dot-ok', layout_generated: 'dot-ok',
        model_generated: 'dot-ok',
        received: 'dot-idle',
        failed: 'dot-fail',
      };
      return m[s] || 'dot-idle';
    }

    function timeAgo(iso) {
      const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
      if (diff < 60) return diff + 's ago';
      if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
      if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
      return Math.floor(diff / 86400) + 'd ago';
    }

    async function loadHistory() {
      const container = document.getElementById('history-list');
      try {
        const r = await fetch('/api/v1/design/list/', { credentials: 'same-origin' });
        const sessions = await r.json();
        if (!Array.isArray(sessions) || sessions.length === 0) {
          container.innerHTML = '<div class="history-empty">No sessions yet. Run a design pipeline above.</div>';
          return;
        }
        container.innerHTML = '';
        sessions.slice(0, 15).forEach(s => {
          const item = document.createElement('a');
          item.href = '/api/v1/design/' + s.session_id + '/';
          item.target = '_blank';
          item.rel = 'noreferrer';
          item.className = 'history-item';
          const compliant = s.is_fully_compliant === true ? '✓ compliant' : s.is_fully_compliant === false ? '✗ non-compliant' : '';
          item.innerHTML = `
            <span class="history-status-dot ${statusDotClass(s.status)}"></span>
            <div class="history-meta">
              <div class="history-region">${s.region} · ${s.plot_width_m}×${s.plot_depth_m}m · ${s.num_floors}F</div>
              <div class="history-detail">${s.status}${compliant ? ' · ' + compliant : ''}</div>
            </div>
            <div class="history-time">${timeAgo(s.created_at)}</div>
          `;
          container.appendChild(item);
        });
      } catch (e) {
        container.innerHTML = '<div class="history-empty">Could not load sessions.</div>';
      }
    }

    /* ════════════════════════════════════════════════════════════════
       CLIPBOARD
       ════════════════════════════════════════════════════════════════ */
    async function copyText(text) {
      if (!text) return false;
      try { await navigator.clipboard.writeText(text); return true; }
      catch (_) { return false; }
    }

    if (studioControls.loadPromptTemplate && studioControls.promptTemplate) {
      studioControls.loadPromptTemplate.addEventListener('click', function () {
        const promptText = String(studioControls.promptTemplate.value || '').trim();
        if (!promptText) return;
        document.getElementById('raw_text').value = promptText;
        updateCharCount();
        showToast('Prompt template loaded into the brief.', 'ok');
      });
    }

    if (studioControls.copyPromptTemplate && studioControls.promptTemplate) {
      studioControls.copyPromptTemplate.addEventListener('click', async function () {
        const promptText = String(studioControls.promptTemplate.value || '').trim();
        const ok = await copyText(promptText);
        if (ok) {
          showToast('Prompt template copied.', 'ok');
        } else {
          showToast('Could not copy the prompt template.', 'warn');
        }
      });
    }

    studioControls.floorSelect.addEventListener('change', function () {
      studioSelectedFloor = String(this.value || '');
      refreshStudioZoneSelect();
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
    });

    studioControls.zoneSelect.addEventListener('change', function () {
      studioSelectedZoneId = String(this.value || '');
      const selectedZone = getStudioSelectedZone();
      if (selectedZone) {
        studioSelectedFloor = String(selectedZone.floor);
        studioControls.floorSelect.value = studioSelectedFloor;
        refreshStudioZoneSelect();
      }
      renderStudioCanvas();
      renderStudioZoneCards();
      syncStudioInspectorFromSelection();
    });

    [
      studioControls.zoneRoomType,
      studioControls.zoneFloor,
      studioControls.zoneX,
      studioControls.zoneY,
      studioControls.zoneWidth,
      studioControls.zoneDepth,
      studioControls.zoneOrientation,
      studioControls.zoneStreetFacing,
    ].forEach(control => {
      control.addEventListener('input', syncStudioSelectedZoneFromInspector);
      control.addEventListener('change', syncStudioSelectedZoneFromInspector);
    });

    if (studioControls.resetLayout) {
      studioControls.resetLayout.disabled = true;
    }
    if (studioControls.applyLayout) {
      studioControls.applyLayout.disabled = true;
    }

    window.addEventListener('resize', function () {
      if (studioDraftLayoutZones.length) {
        renderStudioCanvas();
      }
    });

    /* ════════════════════════════════════════════════════════════════
       EVENT LISTENERS
       ════════════════════════════════════════════════════════════════ */
    document.getElementById('run').addEventListener('click', function () {
      runEndpoint('/api/v1/design/', 'Running design pipeline…');
    });

    document.getElementById('bridge').addEventListener('click', function () {
      runEndpoint('/api/v1/design/hypar/bridge/', 'Generating Hypar package…');
    });

    document.getElementById('auto-create').addEventListener('click', function () {
      runEndpoint('/api/v1/design/hypar/auto-create/', 'Attempting direct Hypar project creation…');
    });

    document.getElementById('refresh-history').addEventListener('click', loadHistory);
    reportControls.create.addEventListener('click', createReportExport);
    reportControls.refresh.addEventListener('click', refreshReportExport);
    reportControls.downloadPdf.addEventListener('click', downloadReportPdf);
    reportControls.downloadDxf.addEventListener('click', exportDxf);

    /* ════════════════════════════════════════════════════════════════
       INIT
       ════════════════════════════════════════════════════════════════ */
    loadHistory();
    setReportStatus('pill-idle', 'Paste a token and revision ID, then generate a PDF or DXF.');

    /* ════════════════════════════════════════════════════════════════
       FORM DATA
       ════════════════════════════════════════════════════════════════ */
    /* ── Auto-fill plot dimensions from raw_text ──────────────────────────── */
    const widthEl   = document.getElementById('plot_width_m');
    const depthEl   = document.getElementById('plot_depth_m');

    // Track if user has manually edited the dimension fields
    let userEditedWidth = false, userEditedDepth = false;
    widthEl.addEventListener('input', () => { userEditedWidth = true; });
    depthEl.addEventListener('input', () => { userEditedDepth = true; });

    rawTextEl.addEventListener('input', () => {
      const t = rawTextEl.value.toLowerCase();
      // Match patterns like 30x40, 30 x 40, 30×40, 30 by 40
      const m = t.match(/(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)/);
      if (m) {
        if (!userEditedWidth) { widthEl.value = parseFloat(m[1]); }
        if (!userEditedDepth) { depthEl.value = parseFloat(m[2]); }
      }
      // Auto-detect region hint from common city names
      const cityMap = {
        'mumbai': '🇮🇳 india_mumbai',
        'delhi': '🇮🇳 india_delhi',
        'bengaluru': '🇮🇳 india_bangalore',
        'bangalore': '🇮🇳 india_bangalore',
        'chennai': '🇮🇳 india_chennai',
        'new york': '🇺🇸 usa_nyc',
        'nyc': '🇺🇸 usa_nyc',
        'london': '🇬🇧 uk_london',
        'dubai': '🇦🇪 uae_dubai',
      };
      const regionText = document.getElementById('detected-region-text');
      let matched = 'Will be inferred from text';
      for (const [city, label] of Object.entries(cityMap)) {
        if (t.includes(city)) { matched = label; break; }
      }
      regionText.textContent = matched;
    });

    function requestBodyFromForm() {
      const body = {
        raw_text: document.getElementById('raw_text').value,
        building_type: document.getElementById('building_type').value,
        plot_width_m: parseFloat(document.getElementById('plot_width_m').value) || 30.0,
        plot_depth_m: parseFloat(document.getElementById('plot_depth_m').value) || 40.0,
        num_floors: parseInt(document.getElementById('num_floors').value, 10) || 2,
        num_units: parseInt(document.getElementById('num_units').value, 10) || 1,
        plot_facing_direction: document.getElementById('plot_facing_direction').value,
        use_vastu: document.getElementById('use_vastu').checked,
        // Explicitly mark fields the user set so the backend won't infer/override them
        _explicit_fields: ['plot_width_m', 'plot_depth_m', 'building_type', 'num_floors', 'num_units'],
      };
      const hyparUrl = (document.getElementById('hypar_api_url').value || '').trim();
      const hyparToken = (document.getElementById('hypar_api_token').value || '').trim();
      if (hyparUrl) body.hypar_api_url = hyparUrl;
      if (hyparToken) body.hypar_api_token = hyparToken;
      return body;
    }

    /* ════════════════════════════════════════════════════════════════
       SYNTAX HIGHLIGHTING (lightweight, no deps)
       ════════════════════════════════════════════════════════════════ */
    function syntaxHighlight(json) {
      const escaped = json
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return escaped.replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        match => {
          let cls = 'json-num';
          if (/^"/.test(match)) {
            cls = /:$/.test(match) ? 'json-key' : 'json-str';
          } else if (/true|false/.test(match)) {
            cls = 'json-bool';
          } else if (/null/.test(match)) {
            cls = 'json-null';
          }
          return '<span class="' + cls + '">' + match + '</span>';
        }
      );
    }

    function renderOutput(text) {
      const out = document.getElementById('out');
      if (!out) return;
      try {
        const obj = JSON.parse(text.indexOf('\n') > 0 ? text.split('\n').slice(2).join('\n') : text);
        out.innerHTML = syntaxHighlight(JSON.stringify(obj, null, 2));
      } catch (e) {
        out.textContent = text;
      }
    }

    function appendResponseNote(message) {
      const out = document.getElementById('out');
      if (!out) return;
      out.textContent += '\n\n' + message;
    }

    /* ════════════════════════════════════════════════════════════════
       OUTPUT URL HELPER
       ════════════════════════════════════════════════════════════════ */
    function toOutputUrl(relativePath) {
      const value = String(relativePath || '').trim().replace(/^\/+/, '');
      if (!value) return '';
      return '/outputs/' + value.split('/').map(encodeURIComponent).join('/');
    }

    /* ════════════════════════════════════════════════════════════════
       RENDER ARTIFACTS
       ════════════════════════════════════════════════════════════════ */
    function renderArtifacts(payload, endpoint) {
      const box = document.getElementById('artifact-box');
      const list = document.getElementById('artifact-links');
      list.innerHTML = '';

      const isBridgeFlow = endpoint === '/api/v1/design/hypar/bridge/';
      if (!isBridgeFlow) { box.hidden = true; return; }

      const bridge = (payload && payload.hypar_bridge) ? payload.hypar_bridge : {};
      const entries = [
        { label: 'Requirements spreadsheet (upload this first)', path: bridge.requirements_artifact_path },
        { label: 'Zone/floor spreadsheet', path: bridge.artifact_path },
        { label: 'Elements reference JSON', path: payload.hypar_elements_reference_path },
        { label: 'Hypar concept JSON', path: payload.hypar_json_path },
      ];

      let count = 0;
      for (const item of entries) {
        if (!item.path) continue;
        const url = toOutputUrl(item.path);
        if (!url) continue;
        const li = document.createElement('li');
        li.innerHTML = '<strong>' + item.label + ':</strong> <a href="' + url + '" target="_blank" rel="noreferrer">' + item.path + '</a>';
        list.appendChild(li);
        count++;
      }
      box.hidden = count === 0;
    }

    /* ════════════════════════════════════════════════════════════════
       RENDER DESIGN BRIEF
       ════════════════════════════════════════════════════════════════ */
    function renderDesignBrief(payload) {
      const box = document.getElementById('brief-box');
      const summary = document.getElementById('brief-summary');
      const list = document.getElementById('brief-notes');
      const brief = (payload && payload.design_brief) ? payload.design_brief : null;

      if (!brief) { box.hidden = true; summary.textContent = ''; list.innerHTML = ''; return; }

      summary.textContent = brief.presentation_summary || '';
      const lines = [
        { label: 'Zoning', value: brief.zoning_note },
        { label: 'Circulation', value: brief.circulation_note },
        { label: 'Optimization', value: brief.optimization_note },
        { label: 'Daylight & ventilation', value: brief.daylight_ventilation_note },
        { label: 'Structural grid', value: brief.structural_grid_note },
        { label: 'Geometry', value: brief.geometry_note },
      ];

      list.innerHTML = '';
      let count = 0;
      for (const line of lines) {
        if (!line.value) continue;
        const li = document.createElement('li');
        li.innerHTML = '<strong>' + line.label + ':</strong> ' + line.value;
        list.appendChild(li);
        count++;
      }
      box.hidden = count === 0 && !summary.textContent;
    }

    /* ════════════════════════════════════════════════════════════════
       RENDER SNAPSHOT
       ════════════════════════════════════════════════════════════════ */
    function renderSnapshot(endpoint, result, payload) {
      setText('snap-endpoint', endpoint);
      setText('snap-http', result.status + ' ' + result.statusText);

      const pipelineStatus = String(payload.status || (result.status >= 400 ? 'failed' : 'ok'));
      setText('snap-pipeline', pipelineStatus);

      const requiresClarification = Boolean(payload.requires_clarification);
      setText('snap-clarify', requiresClarification ? '⚠ Clarification required' : '✓ No clarification needed');

      const hyparSubmission = payload.hypar_submission || {};
      const hyparSubmitted = hyparSubmission.submitted === true;
      setText('snap-hypar', hyparSubmitted ? '✓ submitted' : '✗ not submitted');
      setText('snap-hypar-reason', hyparSubmitted ? 'Provider accepted payload' : (hyparSubmission.reason || 'no direct submit'));

      const zones = Array.isArray(payload.layout_zones)
        ? payload.layout_zones.length
        : Number((payload.hypar_bridge && payload.hypar_bridge.zone_count) || 0);

      setStage('parse', result.status < 500 ? 'ok' : 'fail', result.status < 500 ? 'input parsed' : 'parse failed');

      if (requiresClarification) {
        setStage('compliance', 'warn', 'awaiting input');
      } else if (payload.compliance_report || payload.design_brief) {
        setStage('compliance', 'ok', 'rules evaluated');
      } else {
        setStage('compliance', 'pending', 'not run');
      }

      if (zones > 0 || payload.hypar_json_path) {
        setStage('layout', 'ok', zones + ' zone' + (zones !== 1 ? 's' : ''));
      } else if (requiresClarification) {
        setStage('layout', 'warn', 'blocked');
      } else {
        setStage('layout', 'pending', 'no geometry');
      }

      if (endpoint === '/api/v1/design/hypar/auto-create/') {
        if (payload.status === 'created_in_hypar') {
          setStage('hypar', 'ok', 'project created');
        } else if (payload.status === 'hypar_submission_failed') {
          setStage('hypar', 'fail', String(payload.reason || 'failed'));
        } else if (requiresClarification) {
          setStage('hypar', 'warn', 'awaiting clarification');
        } else {
          setStage('hypar', 'pending', 'not attempted');
        }
      } else if (endpoint === '/api/v1/design/hypar/bridge/') {
        setStage('hypar', 'warn', 'manual fallback');
      } else {
        if (hyparSubmitted) {
          setStage('hypar', 'ok', 'submitted via pipeline');
        } else {
          setStage('hypar', 'pending', 'not requested');
        }
      }
    }

    /* ════════════════════════════════════════════════════════════════
       API FETCH
       ════════════════════════════════════════════════════════════════ */
    async function postJson(endpoint, bodyPayload) {
      const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        credentials: 'same-origin',
        body: JSON.stringify(bodyPayload),
      });
      const text = await r.text();
      let payload = null;
      try { payload = JSON.parse(text); } catch (e) { payload = null; }
      return { status: r.status, statusText: r.statusText, text, payload };
    }

    /* ════════════════════════════════════════════════════════════════
       RUN ENDPOINT (core logic — functionally identical to original)
       ════════════════════════════════════════════════════════════════ */
    async function runEndpoint(endpoint, loadingLabel, extraBody = {}) {
      setAllBusy(true);
      setStatus('pill-run', loadingLabel);

      try {
        const bodyPayload = {
          ...requestBodyFromForm(),
          ...extraBody,
        };
        lastRequestPayload = bodyPayload;
        const result = await postJson(endpoint, bodyPayload);
        const responseBody = result.payload
          ? JSON.stringify(result.payload, null, 2)
          : result.text;
        lastResponseText = result.status + ' ' + result.statusText + '\n\n' + responseBody;

        renderArtifacts(result.payload || {}, endpoint);
        renderDesignBrief(result.payload || {});
        syncStudioLayoutFromPayload(result.payload || {});

        const payload = result.payload || {};

        if (endpoint === '/api/v1/design/hypar/auto-create/' && payload.status === 'created_in_hypar') {
          const hyparUrl = String(payload.hypar_project_url || '').trim();
          if (hyparUrl) {
            setStatus('pill-ok', 'Project created. Opening Hypar in a new tab.');
            showToast('Hypar project created!', 'ok');
            window.open(hyparUrl, '_blank', 'noopener');
          } else {
            setStatus('pill-warn', 'Project created but Hypar did not return a direct URL.');
            showToast('Created — no Hypar URL returned.', 'warn');
            appendResponseNote('Note: Project was created, but no Hypar URL was returned by the API response.');
          }
        }

        if (endpoint === '/api/v1/design/hypar/auto-create/' && payload.status === 'hypar_submission_failed') {
          const reason = String(payload.reason || '').trim() || 'unknown';
          if (reason === 'not_configured') {
            setStatus('pill-warn', 'Direct Hypar creation is not configured. Set HYPAR_API_URL and HYPAR_API_TOKEN in backend .env.');
            showToast('Hypar not configured — set env vars.', 'warn');
            appendResponseNote('Direct Hypar creation is not configured yet. Set HYPAR_API_URL and HYPAR_API_TOKEN in backend .env, or send hypar_api_url and hypar_api_token from your request payload.');
          } else {
            setStatus('pill-bad', 'Hypar submission failed: ' + reason);
            showToast('Hypar submission failed.', 'bad');
          }
        }

        if (endpoint === '/api/v1/design/' && result.status >= 200 && result.status < 300) {
          setStatus('pill-ok', 'Pipeline complete. Review the brief and adjust the layout.');
          showToast('Pipeline completed successfully.', 'ok');
        }
        if (endpoint === '/api/v1/design/hypar/bridge/' && result.status >= 200 && result.status < 300) {
          setStatus('pill-warn', 'Fallback package generated. Use manual upload only if auto-create is unavailable.');
          showToast('Hypar package generated.', 'warn');
        }
        if (result.status >= 400 && !(endpoint === '/api/v1/design/hypar/auto-create/' && payload.status === 'hypar_submission_failed')) {
          setStatus('pill-bad', 'Request failed. Check response details.');
          showToast('Request failed (' + result.status + ').', 'bad');
        }

        // Refresh history after any successful run
        if (result.status < 400) loadHistory();

      } catch (e) {
        renderArtifacts({}, endpoint);
        renderDesignBrief({});
        setStatus('pill-bad', 'Request error: ' + e);
        showToast('Network error.', 'bad');
      } finally {
        setAllBusy(false);
      }
    }


import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../api';
import { render2DCanvas, getClickedZone } from '../utils/canvas2d';
import { Canvas3D } from '../utils/canvas3d';
import { getRoomTypeColor, calculateStats } from '../utils/fallback';
import { ElementManager } from '../utils/elementManager';
import { ROOM_TYPES, ROOM_LABELS, TRANSFORM_MODES } from '../utils/constants';
import '../styles/studio.css';

export default function Studio() {
  const navigate = useNavigate();
  const canvas2DRef  = useRef(null);
  const canvas3DRef  = useRef(null);
  const c3dRef       = useRef(null); // Canvas3D instance

  const [leftOpen,  setLeftOpen]  = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [editingField, setEditingField] = useState(null);

  const [design,         setDesign]         = useState(null);
  const [designSettings, setDesignSettings] = useState(null);
  const [zones,          setZones]          = useState([]);
  const [selectedId,     setSelectedId]     = useState(null);
  const [viewMode,       setViewMode]       = useState('3d');
  const [showGrid,       setShowGrid]       = useState(true);
  const [isLoading,      setIsLoading]      = useState(true);
  const [error,          setError]          = useState(null);
  const [stats,          setStats]          = useState(null);
  const [isFallback,     setIsFallback]     = useState(false);

  // 3D editor state
  const [transformMode, setTransformMode] = useState('select');
  const [snapToGrid,    setSnapToGrid]    = useState(true);

  /* ── load design from sessionStorage ── */
  useEffect(() => {
    try {
      const raw  = sessionStorage.getItem('currentDesign');
      const sRaw = sessionStorage.getItem('designSettings');
      if (!raw) { setError('No design found. Please generate a design first.'); setIsLoading(false); return; }
      const d = JSON.parse(raw);
      const s = JSON.parse(sRaw || '{}');
      setDesign(d);
      setDesignSettings(s);
      setIsFallback(s.isFallback === true);
      const loadedZones = d.layout_zones || [];
      setZones(loadedZones);
      if (loadedZones.length) setStats(calculateStats(loadedZones));
    } catch (e) {
      setError('Failed to load design data.');
    }
    setIsLoading(false);
  }, []);

  /* ── init / destroy Canvas3D ── */
  useEffect(() => {
    if (viewMode !== '3d' || !canvas3DRef.current || c3dRef.current) return;

    const instance = new Canvas3D(
      canvas3DRef.current,
      (id) => setSelectedId(id),           // onZoneSelect
      (updated) => {                        // onRoomTransformed
        setZones((prev) => ElementManager.updateElement(prev, updated.id, updated));
      },
    );

    c3dRef.current = instance;

    // Render current zones
    if (zones.length) instance.renderZones(zones);

    return () => {
      instance.dispose();
      c3dRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]);

  /* ── push zone changes to 3D ── */
  useEffect(() => {
    if (viewMode === '3d' && c3dRef.current) {
      c3dRef.current.renderZones(zones);
      if (selectedId) c3dRef.current.selectZone(selectedId);
    }
  }, [zones, viewMode]);

  /* ── keep 3D selection in sync when selectedId changes from sidebar/layers ── */
  useEffect(() => {
    if (viewMode === '3d' && c3dRef.current) {
      if (selectedId) c3dRef.current.selectZone(selectedId);
      else c3dRef.current.deselectZone();
    }
  }, [selectedId, viewMode]);

  /* ── 2D canvas ── */
  useEffect(() => {
    if (viewMode !== '2d' || !canvas2DRef.current || !zones.length) return;
    const id = requestAnimationFrame(() => {
      render2DCanvas(canvas2DRef.current, zones, {
        plotWidth:  designSettings?.plotWidth  || 30,
        plotDepth:  designSettings?.plotDepth  || 40,
        selectedZoneId: selectedId,
      });
    });
    return () => cancelAnimationFrame(id);
  }, [viewMode, zones, selectedId, designSettings]);

  /* ── stats ── */
  useEffect(() => {
    if (zones.length) setStats(calculateStats(zones));
  }, [zones]);

  /* ── transform mode → 3D ── */
  useEffect(() => {
    if (c3dRef.current) c3dRef.current.setMode(transformMode);
  }, [transformMode]);

  /* ── snap → 3D ── */
  useEffect(() => {
    if (c3dRef.current) c3dRef.current.setSnapToGrid(snapToGrid);
  }, [snapToGrid]);

  /* ── keyboard shortcuts ── */
  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedId) handleDeleteElement(selectedId);
      }
      if (e.key === 'Escape') setSelectedId(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedId]);

  /* ── 2D click ── */
  const handleCanvas2DClick = (e) => {
    if (!canvas2DRef.current) return;
    const rect = canvas2DRef.current.getBoundingClientRect();
    const zone = getClickedZone(canvas2DRef.current, zones, e.clientX - rect.left, e.clientY - rect.top, {
      plotWidth: designSettings?.plotWidth || 30,
      plotDepth: designSettings?.plotDepth || 40,
    });
    setSelectedId(zone ? zone.id : null);
  };

  /* ── element management ── */
  const handleAddElement = useCallback((roomType) => {
    const result = ElementManager.addElement(zones, roomType);
    setZones(result.zones);
    setSelectedId(result.newId);
    setShowAddMenu(false);
    // Incremental add to 3D
    if (c3dRef.current) {
      const newZone = result.zones.find((z) => z.id === result.newId);
      if (newZone) { c3dRef.current.addRoom(newZone); c3dRef.current.selectZone(result.newId); }
    }
  }, [zones]);

  const handleDeleteElement = useCallback((id) => {
    setZones((prev) => ElementManager.deleteElement(prev, id));
    if (c3dRef.current) c3dRef.current.removeRoom(id);
    if (selectedId === id) setSelectedId(null);
  }, [selectedId]);

  const handleDuplicateElement = useCallback((id) => {
    const result = ElementManager.duplicateElement(zones, id);
    setZones(result.zones);
    setSelectedId(result.newId);
    if (c3dRef.current) {
      const dup = result.zones.find((z) => z.id === result.newId);
      if (dup) { c3dRef.current.addRoom(dup); c3dRef.current.selectZone(result.newId); }
    }
  }, [zones]);

  const handleUpdateElement = useCallback((id, updates) => {
    setZones((prev) => {
      const next = ElementManager.updateElement(prev, id, updates);
      // Sync to 3D incrementally
      if (c3dRef.current) {
        const updated = next.find((z) => z.id === id);
        if (updated) c3dRef.current.updateRoom(updated);
      }
      return next;
    });
  }, []);

  /* ── inspector field change ── */
  const handleInspectorChange = (field, rawValue) => {
    if (!selectedId) return;
    let value = rawValue;
    if (['width','depth','height','x','y','z','floor'].includes(field)) {
      value = Math.max(field === 'floor' ? 1 : 0.1, parseFloat(rawValue) || 0);
    }
    handleUpdateElement(selectedId, { [field]: value });
    setEditingField(null);
  };

  /* ── canvas toolbar actions ── */
  const handleCanvasAction = (action) => {
    if (action === 'fit')   c3dRef.current?.fitCamera();
    if (action === 'reset') { c3dRef.current?.resetCamera(); setSelectedId(null); }
    if (action === 'grid')  { setShowGrid((g) => !g); c3dRef.current?.toggleGrid(); }
  };

  /* ── exports (unchanged) ── */
  const handleExportPDF = async () => {
    try { await apiService.generateReport({ sessionId: design?.session_id, layoutData: { zones } }); alert('PDF generated!'); }
    catch (e) { alert('PDF failed: ' + e.message); }
  };
  const handleExportDXF = async () => {
    try { await apiService.generateDXF({ sessionId: design?.session_id, layoutData: { zones } }); alert('DXF generated!'); }
    catch (e) { alert('DXF failed: ' + e.message); }
  };
  const handleExportJSON = () => {
    const blob = new Blob([JSON.stringify({ design, settings: designSettings, zones, timestamp: new Date().toISOString() }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'design.json'; a.click();
    URL.revokeObjectURL(a.href);
  };
  const handleScreenshot = () => {
    const cv = viewMode === '2d' ? canvas2DRef.current : canvas3DRef.current?.querySelector('canvas');
    if (!cv) return;
    const a = document.createElement('a');
    a.href = cv.toDataURL('image/png'); a.download = `design-${viewMode}-${Date.now()}.png`; a.click();
  };

  /* ── render guards ── */
  if (isLoading) return <div className="studio-loading"><div className="loading-spinner" /><span>Loading design…</span></div>;
  if (error)     return (
    <div className="studio-error">
      <p>{error}</p>
      <button className="btn btn-primary" onClick={() => navigate('/')}>← Back to Home</button>
    </div>
  );

  const selectedZone = zones.find((z) => z.id === selectedId);

  return (
    <div className="studio-wrapper">
      {/* ── Top Bar ── */}
      <header className="studio-topbar">
        <div className="topbar-left">
          <button className="btn-icon-small" onClick={() => navigate('/')} title="Back">← Home</button>
          <h2 className="project-title">{designSettings?.prompt?.substring(0, 45) || 'Untitled Design'}</h2>
          {isFallback && <span className="badge-fallback">Demo Layout</span>}
        </div>
        <div className="topbar-right">
          <button className="btn btn-secondary" title="Save">💾 Save</button>
          <div className="menu-divider" />
          <div style={{ position: 'relative' }}>
            <button className="btn btn-secondary" onClick={() => {
              const m = document.getElementById('export-menu');
              if (m) m.style.display = m.style.display === 'flex' ? 'none' : 'flex';
            }}>⬇ Export</button>
            <div id="export-menu" className="export-menu" style={{ display: 'none' }}>
              <button onClick={handleExportPDF}>📄 PDF Report</button>
              <button onClick={handleExportDXF}>🏗 DXF File</button>
              <button onClick={handleExportJSON}>{ } JSON</button>
              <button onClick={handleScreenshot}>📸 Screenshot</button>
            </div>
          </div>
        </div>
      </header>

      <div className="studio-layout">
        {/* ── Left Sidebar ── */}
        <aside className={`studio-sidebar-left ${leftOpen ? 'open' : 'collapsed'}`}>
          <button className="sidebar-toggle-btn" onClick={() => setLeftOpen(!leftOpen)}>☰</button>
          {leftOpen && (
            <div className="sidebar-content">
              {/* Brief */}
              <section className="sidebar-section">
                <h3>Design Brief</h3>
                <p className="brief-text">{designSettings?.prompt}</p>
                <div className="brief-settings">
                  {[
                    ['📍 Location', designSettings?.location],
                    ['📏 Plot', `${designSettings?.plotWidth}m × ${designSettings?.plotDepth}m`],
                    ['🏢 Floors', designSettings?.numFloors],
                    ['🏗 Type', designSettings?.buildingType],
                  ].map(([label, val]) => (
                    <div className="setting-item" key={label}>
                      <span>{label}:</span><strong>{val}</strong>
                    </div>
                  ))}
                </div>
              </section>

              {/* Add Element */}
              <section className="sidebar-section">
                <h3>Add Element</h3>
                <div className="add-element-menu">
                  {showAddMenu ? (
                    <>
                      {ROOM_TYPES.map((t) => (
                        <button key={t} className="btn btn-small" onClick={() => handleAddElement(t)}>
                          + {ROOM_LABELS[t] || t}
                        </button>
                      ))}
                      <button className="btn btn-small btn-secondary" onClick={() => setShowAddMenu(false)}>✕ Close</button>
                    </>
                  ) : (
                    <button className="btn btn-secondary full-width" onClick={() => setShowAddMenu(true)}>➕ Add New Room</button>
                  )}
                </div>
              </section>

              {/* Design Actions */}
              <section className="sidebar-section">
                <h3>Design Actions</h3>
                <button className="btn btn-secondary full-width">✨ Regenerate</button>
                <button className="btn btn-secondary full-width" style={{ marginTop: 6 }}>✓ Check Compliance</button>
              </section>
            </div>
          )}
        </aside>

        {/* ── Center Canvas ── */}
        <main className="studio-center">
          {/* Toolbar row 1 — view + camera */}
          <div className="canvas-toolbar">
            <div className="toolbar-group">
              <button className={`btn-toolbar ${viewMode === '2d' ? 'active' : ''}`} onClick={() => setViewMode('2d')} title="2D Plan View">📐 2D</button>
              <button className={`btn-toolbar ${viewMode === '3d' ? 'active' : ''}`} onClick={() => setViewMode('3d')} title="3D Model View">🎲 3D</button>
            </div>
            {viewMode === '3d' && (
              <div className="toolbar-group transform-toolbar">
                {TRANSFORM_MODES.map((m) => (
                  <button
                    key={m.id}
                    id={`tool-${m.id}`}
                    className={`btn-toolbar ${transformMode === m.id ? 'mode-active' : ''}`}
                    onClick={() => setTransformMode(m.id)}
                    title={m.label}
                  >
                    {m.icon} {m.label}
                  </button>
                ))}
                <div className="menu-divider" />
                <button
                  className={`btn-toolbar ${snapToGrid ? 'active' : ''}`}
                  onClick={() => setSnapToGrid((s) => !s)}
                  title="Snap to Grid"
                >
                  ⊞ Snap
                </button>
              </div>
            )}
            <div className="toolbar-group">
              <button className={`btn-toolbar ${showGrid ? 'active' : ''}`} onClick={() => handleCanvasAction('grid')} title="Toggle Grid">⊞ Grid</button>
              <button className="btn-toolbar" onClick={() => handleCanvasAction('fit')}   title="Fit to View">▢ Fit</button>
              <button className="btn-toolbar" onClick={() => handleCanvasAction('reset')} title="Reset Camera">↺ Reset</button>
            </div>
          </div>

          {/* Canvas */}
          <div className="canvas-container">
            {viewMode === '2d' ? (
              <canvas
                ref={canvas2DRef}
                className="canvas-2d"
                onClick={handleCanvas2DClick}
                width={1200}
                height={800}
              />
            ) : (
              <div ref={canvas3DRef} className="canvas-3d" />
            )}

            {/* Mode badge overlay for 3D */}
            {viewMode === '3d' && (
              <div className="transform-badge">
                {TRANSFORM_MODES.find((m) => m.id === transformMode)?.icon}{' '}
                {TRANSFORM_MODES.find((m) => m.id === transformMode)?.label}
                {snapToGrid && <span className="snap-dot">⊞</span>}
              </div>
            )}
          </div>

          {/* Status bar */}
          {selectedZone && (
            <div className="canvas-caption">
              <strong>{selectedZone.label}</strong>
              {' '}•{' '}{selectedZone.width?.toFixed(1)}m × {selectedZone.depth?.toFixed(1)}m × {selectedZone.height?.toFixed(1)}m
              {' '}•{' '}{(selectedZone.width * selectedZone.depth).toFixed(1)} m²
              {' '}•{' '}Floor {selectedZone.floor}
            </div>
          )}
        </main>

        {/* ── Right Sidebar ── */}
        <aside className={`studio-sidebar-right ${rightOpen ? 'open' : 'collapsed'}`}>
          <button className="sidebar-toggle-btn" onClick={() => setRightOpen(!rightOpen)}>☰</button>
          {rightOpen && (
            <div className="sidebar-content">
              {/* Layers */}
              <section className="sidebar-section">
                <h3>Layers ({zones.length})</h3>
                <div className="layers-list">
                  {zones.map((zone) => (
                    <div
                      key={zone.id}
                      className={`layer-item ${selectedId === zone.id ? 'selected' : ''}`}
                      onClick={() => setSelectedId(zone.id)}
                    >
                      <div className="layer-color" style={{ backgroundColor: getRoomTypeColor(zone.room_type) }} />
                      <span className="layer-label">{zone.label}</span>
                      <span className="layer-floor">F{zone.floor}</span>
                      <div className="layer-actions">
                        <button className="btn-small-icon" onClick={(e) => { e.stopPropagation(); handleDuplicateElement(zone.id); }} title="Duplicate">📋</button>
                        <button className="btn-small-icon btn-danger" onClick={(e) => { e.stopPropagation(); handleDeleteElement(zone.id); }} title="Delete">✕</button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Inspector */}
              {selectedZone && (
                <section className="sidebar-section">
                  <h3>Inspector</h3>
                  <div className="inspector-content">
                    {/* Label */}
                    <div className="inspector-row">
                      <span className="inspector-label">Name</span>
                      {editingField === 'label' ? (
                        <input className="inspector-input" type="text" defaultValue={selectedZone.label}
                          autoFocus
                          onBlur={(e) => handleInspectorChange('label', e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleInspectorChange('label', e.target.value)}
                        />
                      ) : (
                        <span className="inspector-value" onClick={() => setEditingField('label')}>{selectedZone.label}</span>
                      )}
                    </div>
                    {/* Type */}
                    <div className="inspector-row">
                      <span className="inspector-label">Type</span>
                      <select className="inspector-input" value={selectedZone.room_type}
                        onChange={(e) => handleInspectorChange('room_type', e.target.value)}>
                        {ROOM_TYPES.map((t) => <option key={t} value={t}>{ROOM_LABELS[t] || t}</option>)}
                      </select>
                    </div>
                    {/* Position */}
                    <div className="inspector-group-label">Position (m)</div>
                    {['x','y','z'].map((f) => (
                      <div className="inspector-row" key={f}>
                        <span className="inspector-label">{f.toUpperCase()}</span>
                        <input className="inspector-input" type="number" step="0.1"
                          key={`${selectedId}-${f}-${selectedZone[f]}`}
                          defaultValue={(selectedZone[f] || 0).toFixed(2)}
                          onBlur={(e) => handleInspectorChange(f, e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleInspectorChange(f, e.target.value)}
                        />
                      </div>
                    ))}
                    {/* Dimensions */}
                    <div className="inspector-group-label">Dimensions (m)</div>
                    {[['width','W'],['depth','D'],['height','H']].map(([f, lbl]) => (
                      <div className="inspector-row" key={f}>
                        <span className="inspector-label">{lbl}</span>
                        <input className="inspector-input" type="number" step="0.1" min="0.1"
                          key={`${selectedId}-${f}-${selectedZone[f]}`}
                          defaultValue={selectedZone[f]?.toFixed(2)}
                          onBlur={(e) => handleInspectorChange(f, e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleInspectorChange(f, e.target.value)}
                        />
                      </div>
                    ))}
                    {/* Floor + Rotation */}
                    <div className="inspector-row">
                      <span className="inspector-label">Floor</span>
                      <input className="inspector-input" type="number" min="1"
                        key={`${selectedId}-floor-${selectedZone.floor}`}
                        defaultValue={selectedZone.floor}
                        onBlur={(e) => handleInspectorChange('floor', e.target.value)}
                      />
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Rot °</span>
                      <input className="inspector-input" type="number" step="15"
                        key={`${selectedId}-rot-${selectedZone.rotation}`}
                        defaultValue={selectedZone.rotation || 0}
                        onBlur={(e) => handleInspectorChange('rotation', e.target.value)}
                      />
                    </div>
                    {/* Quick actions */}
                    <div className="inspector-actions">
                      <button className="btn btn-small btn-secondary" onClick={() => handleDuplicateElement(selectedId)}>📋 Duplicate</button>
                      <button className="btn btn-small btn-danger-sm" onClick={() => handleDeleteElement(selectedId)}>🗑 Delete</button>
                    </div>
                  </div>
                </section>
              )}

              {/* Statistics */}
              {stats && (
                <section className="sidebar-section">
                  <h3>Statistics</h3>
                  <div className="stats-grid">
                    <div className="stat-item"><div className="stat-label">Built-up</div><div className="stat-value">{stats.builtUpArea} m²</div></div>
                    <div className="stat-item"><div className="stat-label">Parking</div><div className="stat-value">{stats.parkingArea} m²</div></div>
                    <div className="stat-item"><div className="stat-label">Rooms</div><div className="stat-value">{zones.length}</div></div>
                    <div className="stat-item"><div className="stat-label">Floors</div><div className="stat-value">{Math.max(...zones.map((z) => z.floor || 1), 1)}</div></div>
                  </div>
                </section>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

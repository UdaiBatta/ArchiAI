import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../api';
import { render2DCanvas, getClickedZone } from '../utils/canvas2d';
import { Canvas3D } from '../utils/canvas3d';
import { getRoomTypeColor, calculateStats } from '../utils/fallback';
import { ElementManager } from '../utils/elementManager';
import '../styles/studio.css';

const ROOM_TYPES = [
  'living_room', 'bedroom', 'kitchen', 'bathroom',
  'staircase', 'parking', 'balcony', 'office',
  'corridor', 'terrace', 'generic'
];

export default function Studio() {
  const navigate = useNavigate();
  const canvas2DRef = useRef(null);
  const canvas3DRef = useRef(null);
  const [canvas3DInstance, setCanvas3DInstance] = useState(null);

  // Layout state
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [editingField, setEditingField] = useState(null);

  // Design state
  const [design, setDesign] = useState(null);
  const [designSettings, setDesignSettings] = useState(null);
  const [zones, setZones] = useState([]);
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [viewMode, setViewMode] = useState('2d');
  const [showGrid, setShowGrid] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [isFallback, setIsFallback] = useState(false);

  // Load design from session storage
  useEffect(() => {
    const loadDesign = async () => {
      try {
        const designData = sessionStorage.getItem('currentDesign');
        const settingsData = sessionStorage.getItem('designSettings');

        if (!designData) {
          setError('No design found. Please generate a design first.');
          return;
        }

        const design = JSON.parse(designData);
        const settings = JSON.parse(settingsData || '{}');

        setDesign(design);
        setDesignSettings(settings);
        setZones(design.layout_zones || []);
        setIsFallback(settings.isFallback === true);

        if (design.layout_zones) {
          setStats(calculateStats(design.layout_zones));
        }

        setIsLoading(false);
      } catch (err) {
        console.error('Failed to load design:', err);
        setError('Failed to load design data.');
        setIsLoading(false);
      }
    };

    loadDesign();
  }, []);

  // Initialize 3D canvas
  useEffect(() => {
    if (viewMode === '3d' && canvas3DRef.current && !canvas3DInstance) {
      const instance = new Canvas3D(canvas3DRef.current, (zoneId) => {
        setSelectedZoneId(zoneId);
      });
      if (zones.length > 0) {
        instance.renderZones(zones);
      }
      setCanvas3DInstance(instance);

      return () => {
        instance.dispose();
      };
    }
  }, [viewMode, canvas3DInstance, zones]);

  // Render zones in 3D
  useEffect(() => {
    if (viewMode === '3d' && canvas3DInstance && zones.length > 0) {
      canvas3DInstance.renderZones(zones);
      if (selectedZoneId) {
        canvas3DInstance.selectZone(selectedZoneId);
      }
    }
  }, [zones, viewMode, canvas3DInstance, selectedZoneId]);

  // Render 2D canvas
  useEffect(() => {
    if (viewMode === '2d' && canvas2DRef.current && zones.length > 0) {
      const timer = requestAnimationFrame(() => {
        render2DCanvas(canvas2DRef.current, zones, {
          plotWidth: designSettings?.plotWidth || 30,
          plotDepth: designSettings?.plotDepth || 40,
          selectedZoneId,
        });
      });

      return () => cancelAnimationFrame(timer);
    }
  }, [viewMode, zones, selectedZoneId, designSettings]);

  // Update stats when zones change
  useEffect(() => {
    if (zones.length > 0) {
      setStats(calculateStats(zones));
    }
  }, [zones]);

  // Canvas interactions
  const handleCanvas2DClick = (e) => {
    if (!canvas2DRef.current) return;

    const rect = canvas2DRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const clickedZone = getClickedZone(canvas2DRef.current, zones, clickX, clickY, {
      plotWidth: designSettings?.plotWidth || 30,
      plotDepth: designSettings?.plotDepth || 40,
    });

    if (clickedZone) {
      setSelectedZoneId(clickedZone.id);
    }
  };

  // Element management
  const handleAddElement = (roomType) => {
    const newZones = ElementManager.addElement(zones, roomType, { x: 10, y: 10 });
    setZones(newZones);
    setShowAddMenu(false);
  };

  const handleDeleteElement = (id) => {
    const newZones = ElementManager.deleteElement(zones, id);
    setZones(newZones);
    if (selectedZoneId === id) {
      setSelectedZoneId(null);
    }
  };

  const handleDuplicateElement = (id) => {
    const newZones = ElementManager.duplicateElement(zones, id, { x: 2, y: 2 });
    setZones(newZones);
  };

  const handleUpdateElement = (id, updates) => {
    const newZones = ElementManager.updateElement(zones, id, updates);
    setZones(newZones);
  };

  // Inspector editing
  const handleInspectorChange = (field, value) => {
    if (!selectedZoneId) return;

    let updatedValue = value;

    if (['width', 'depth', 'height', 'x', 'y', 'z', 'floor'].includes(field)) {
      updatedValue = Math.max(0.1, parseFloat(value) || 0);
    }

    handleUpdateElement(selectedZoneId, { [field]: updatedValue });
    setEditingField(null);
  };

  // Export functions
  const handleExportPDF = async () => {
    try {
      await apiService.generateReport({
        sessionId: design?.session_id,
        layoutData: { zones },
      });
      alert('PDF generated! Check your downloads.');
    } catch (err) {
      alert('Failed to generate PDF: ' + err.message);
    }
  };

  const handleExportDXF = async () => {
    try {
      await apiService.generateDXF({
        sessionId: design?.session_id,
        layoutData: { zones },
      });
      alert('DXF generated! Check your downloads.');
    } catch (err) {
      alert('Failed to generate DXF: ' + err.message);
    }
  };

  const handleExportJSON = () => {
    const data = { design, settings: designSettings, zones, timestamp: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'design.json';
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleScreenshot = () => {
    const canvas = viewMode === '2d' ? canvas2DRef.current : canvas3DRef.current?.querySelector('canvas');
    if (!canvas) return;

    const link = document.createElement('a');
    link.href = canvas.toDataURL('image/png');
    link.download = `design-${viewMode}-${Date.now()}.png`;
    link.click();
  };

  const handleCanvasAction = (action) => {
    if (action === 'fit' && viewMode === '3d' && canvas3DInstance) {
      canvas3DInstance.fitCamera();
    } else if (action === 'reset') {
      setSelectedZoneId(null);
      if (viewMode === '3d' && canvas3DInstance) {
        canvas3DInstance.resetCamera();
      }
    } else if (action === 'grid') {
      setShowGrid(!showGrid);
      if (viewMode === '3d' && canvas3DInstance) {
        canvas3DInstance.toggleGrid();
      }
    }
  };

  if (isLoading) {
    return <div className="studio-loading">Loading design…</div>;
  }

  if (error) {
    return (
      <div className="studio-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          ← Back to Home
        </button>
      </div>
    );
  }

  const selectedZone = zones.find((z) => z.id === selectedZoneId);

  return (
    <div className="studio-wrapper">
      {/* Top Bar */}
      <header className="studio-topbar">
        <div className="topbar-left">
          <button className="btn-icon-small" onClick={() => navigate('/')} title="Back to home">
            ← Home
          </button>
          <h2 className="project-title">
            {designSettings?.prompt?.substring(0, 40) || 'Untitled Design'}
          </h2>
          {isFallback && <span className="badge-fallback">Demo Layout</span>}
        </div>
        <div className="topbar-right">
          <button className="btn btn-secondary" title="Save project">
            💾 Save
          </button>
          <div className="menu-divider"></div>
          <button className="btn btn-secondary" title="Export options" onClick={() => {
            const menu = document.getElementById('export-menu');
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
          }}>
            ⬇ Export
          </button>
          <div id="export-menu" className="export-menu" style={{ display: 'none' }}>
            <button onClick={handleExportPDF}>📄 PDF Report</button>
            <button onClick={handleExportDXF}>🏗 DXF File</button>
            <button onClick={handleExportJSON}>{ } JSON</button>
            <button onClick={handleScreenshot}>📸 Screenshot</button>
          </div>
        </div>
      </header>

      <div className="studio-layout">
        {/* Left Sidebar */}
        <aside className={`studio-sidebar-left ${leftSidebarOpen ? 'open' : 'collapsed'}`}>
          <button className="sidebar-toggle-btn" onClick={() => setLeftSidebarOpen(!leftSidebarOpen)} title="Toggle sidebar">
            ☰
          </button>
          {leftSidebarOpen && (
            <div className="sidebar-content">
              {/* Design Brief Summary */}
              <section className="sidebar-section">
                <h3>Design Brief</h3>
                <p className="brief-text">{designSettings?.prompt}</p>
                <div className="brief-settings">
                  <div className="setting-item">
                    <span>📍 Location:</span>
                    <strong>{designSettings?.location}</strong>
                  </div>
                  <div className="setting-item">
                    <span>📏 Plot:</span>
                    <strong>{designSettings?.plotWidth}m × {designSettings?.plotDepth}m</strong>
                  </div>
                  <div className="setting-item">
                    <span>🏢 Floors:</span>
                    <strong>{designSettings?.numFloors}</strong>
                  </div>
                  <div className="setting-item">
                    <span>🏗 Type:</span>
                    <strong>{designSettings?.buildingType}</strong>
                  </div>
                </div>
              </section>

              {/* Add Element */}
              <section className="sidebar-section">
                <h3>Add Element</h3>
                <div className="add-element-menu">
                  {showAddMenu ? (
                    <>
                      {ROOM_TYPES.map((type) => (
                        <button
                          key={type}
                          className="btn btn-small"
                          onClick={() => handleAddElement(type)}
                        >
                          + {type.replace(/_/g, ' ')}
                        </button>
                      ))}
                      <button
                        className="btn btn-small btn-secondary"
                        onClick={() => setShowAddMenu(false)}
                      >
                        ✕ Close
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn btn-secondary full-width"
                      onClick={() => setShowAddMenu(true)}
                    >
                      ➕ Add New Room
                    </button>
                  )}
                </div>
              </section>

              {/* Actions */}
              <section className="sidebar-section">
                <h3>Design Actions</h3>
                <button className="btn btn-secondary full-width">
                  ✨ Regenerate
                </button>
                <button className="btn btn-secondary full-width">
                  💡 Improve
                </button>
                <button className="btn btn-secondary full-width">
                  ✓ Check Compliance
                </button>
              </section>
            </div>
          )}
        </aside>

        {/* Center Canvas */}
        <main className="studio-center">
          {/* Canvas Toolbar */}
          <div className="canvas-toolbar">
            <div className="toolbar-group">
              <button
                className={`btn-toolbar ${viewMode === '2d' ? 'active' : ''}`}
                onClick={() => setViewMode('2d')}
                title="2D Plan View"
              >
                📐 2D
              </button>
              <button
                className={`btn-toolbar ${viewMode === '3d' ? 'active' : ''}`}
                onClick={() => setViewMode('3d')}
                title="3D Model View"
              >
                🎲 3D
              </button>
            </div>

            <div className="toolbar-group">
              <button
                className={`btn-toolbar ${showGrid ? 'active' : ''}`}
                onClick={() => handleCanvasAction('grid')}
                title="Toggle Grid"
              >
                ⊞ Grid
              </button>
              <button
                className="btn-toolbar"
                onClick={() => handleCanvasAction('fit')}
                title="Fit to View"
              >
                ▢ Fit
              </button>
              <button
                className="btn-toolbar"
                onClick={() => handleCanvasAction('reset')}
                title="Reset Camera"
              >
                ↺ Reset
              </button>
            </div>
          </div>

          {/* Canvas Container */}
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
          </div>

          {/* Bottom Caption */}
          {selectedZone && (
            <div className="canvas-caption">
              <strong>{selectedZone.label}</strong> • {selectedZone.width.toFixed(1)}m × {selectedZone.depth.toFixed(1)}m • {(selectedZone.width * selectedZone.depth).toFixed(1)} m²
            </div>
          )}
        </main>

        {/* Right Sidebar */}
        <aside className={`studio-sidebar-right ${rightSidebarOpen ? 'open' : 'collapsed'}`}>
          <button className="sidebar-toggle-btn" onClick={() => setRightSidebarOpen(!rightSidebarOpen)} title="Toggle sidebar">
            ☰
          </button>
          {rightSidebarOpen && (
            <div className="sidebar-content">
              {/* Layers */}
              <section className="sidebar-section">
                <h3>Layers ({zones.length})</h3>
                <div className="layers-list">
                  {zones.map((zone) => (
                    <div
                      key={zone.id}
                      className={`layer-item ${selectedZoneId === zone.id ? 'selected' : ''}`}
                    >
                      <div
                        className="layer-color"
                        style={{ backgroundColor: getRoomTypeColor(zone.room_type) }}
                        onClick={() => setSelectedZoneId(zone.id)}
                      />
                      <span className="layer-label" onClick={() => setSelectedZoneId(zone.id)}>
                        {zone.label}
                      </span>
                      <div className="layer-actions">
                        <button
                          className="btn-small-icon"
                          onClick={() => handleDuplicateElement(zone.id)}
                          title="Duplicate"
                        >
                          📋
                        </button>
                        <button
                          className="btn-small-icon btn-danger"
                          onClick={() => handleDeleteElement(zone.id)}
                          title="Delete"
                        >
                          ✕
                        </button>
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
                    <div className="inspector-row">
                      <span className="inspector-label">Name:</span>
                      {editingField === 'label' ? (
                        <input
                          type="text"
                          defaultValue={selectedZone.label}
                          onBlur={(e) => handleInspectorChange('label', e.target.value)}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              handleInspectorChange('label', e.target.value);
                            }
                          }}
                          autoFocus
                        />
                      ) : (
                        <span className="inspector-value" onClick={() => setEditingField('label')}>
                          {selectedZone.label}
                        </span>
                      )}
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Type:</span>
                      <select
                        className="inspector-input"
                        value={selectedZone.room_type}
                        onChange={(e) => handleInspectorChange('room_type', e.target.value)}
                      >
                        {ROOM_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type.replace(/_/g, ' ')}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Width (m):</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        className="inspector-input"
                        defaultValue={selectedZone.width.toFixed(2)}
                        onBlur={(e) => handleInspectorChange('width', e.target.value)}
                      />
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Depth (m):</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        className="inspector-input"
                        defaultValue={selectedZone.depth.toFixed(2)}
                        onBlur={(e) => handleInspectorChange('depth', e.target.value)}
                      />
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Height (m):</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        className="inspector-input"
                        defaultValue={selectedZone.height.toFixed(2)}
                        onBlur={(e) => handleInspectorChange('height', e.target.value)}
                      />
                    </div>
                    <div className="inspector-row">
                      <span className="inspector-label">Floor:</span>
                      <input
                        type="number"
                        min="1"
                        className="inspector-input"
                        defaultValue={selectedZone.floor}
                        onBlur={(e) => handleInspectorChange('floor', e.target.value)}
                      />
                    </div>
                  </div>
                </section>
              )}

              {/* Statistics */}
              {stats && (
                <section className="sidebar-section">
                  <h3>Statistics</h3>
                  <div className="stats-grid">
                    <div className="stat-item">
                      <div className="stat-label">Built-up Area</div>
                      <div className="stat-value">{stats.builtUpArea.toFixed(2)} m²</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-label">Open Area</div>
                      <div className="stat-value">{stats.openArea.toFixed(2)} m²</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-label">Parking</div>
                      <div className="stat-value">{stats.parkingArea.toFixed(2)} m²</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-label">FAR</div>
                      <div className="stat-value">{stats.far.toFixed(2)}</div>
                    </div>
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

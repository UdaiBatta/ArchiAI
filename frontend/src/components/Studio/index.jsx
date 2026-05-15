/**
 * Studio - Main orchestrator component
 * Handles state management and coordinates all sub-components
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../../services/api';
import { render2DCanvas, getClickedZone } from '../../utils/canvas2d';
import { Canvas3D } from '../../utils/canvas3d';
import { calculateStats } from '../../utils/fallback';
import { getColorHex } from '../../utils/colors';
import { ElementManager } from '../../utils/elementManager';
import { ROOM_TYPES } from '../../utils/constants';
import '../../styles/studio.css';

// Sub-components
import TopBar from './TopBar';
import LeftSidebar from './LeftSidebar';
import RightSidebar from './RightSidebar';
import CanvasToolbar from './CanvasToolbar';
import Canvas2DView from './Canvas2DView';
import Canvas3DView from './Canvas3DView';
import CanvasCaption from './CanvasCaption';

export default function Studio() {
  const navigate = useNavigate();
  const canvas2DRef = useRef(null);
  const canvas3DRef = useRef(null);
  const c3dRef = useRef(null); // Canvas3D instance

  // UI state
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [exportStatus, setExportStatus] = useState(null); // { type: 'success'|'error', message: '...' }

  // Design data state
  const [design, setDesign] = useState(null);
  const [designSettings, setDesignSettings] = useState(null);
  const [zones, setZones] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [viewMode, setViewMode] = useState('3d');
  const [showGrid, setShowGrid] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [isFallback, setIsFallback] = useState(false);

  // 3D editor state
  const [transformMode, setTransformMode] = useState('select');
  const [snapToGrid, setSnapToGrid] = useState(true);

  /* ── load design from sessionStorage ── */
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('currentDesign');
      const sRaw = sessionStorage.getItem('designSettings');
      if (!raw) {
        setError('No design found. Please generate a design first.');
        setIsLoading(false);
        return;
      }
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
      (id) => setSelectedId(id),
      (updated) => {
        setZones((prev) => ElementManager.updateElement(prev, updated.id, updated));
      }
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

  /* ── keep 3D selection in sync ── */
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
        plotWidth: designSettings?.plotWidth || 30,
        plotDepth: designSettings?.plotDepth || 40,
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
  const handleAddElement = useCallback(
    (roomType) => {
      const result = ElementManager.addElement(zones, roomType);
      setZones(result.zones);
      setSelectedId(result.newId);
      setShowAddMenu(false);
      // Incremental add to 3D
      if (c3dRef.current) {
        const newZone = result.zones.find((z) => z.id === result.newId);
        if (newZone) {
          c3dRef.current.addRoom(newZone);
          c3dRef.current.selectZone(result.newId);
        }
      }
    },
    [zones]
  );

  const handleDeleteElement = useCallback(
    (id) => {
      setZones((prev) => ElementManager.deleteElement(prev, id));
      if (c3dRef.current) c3dRef.current.removeRoom(id);
      if (selectedId === id) setSelectedId(null);
    },
    [selectedId]
  );

  const handleDuplicateElement = useCallback(
    (id) => {
      const result = ElementManager.duplicateElement(zones, id);
      setZones(result.zones);
      setSelectedId(result.newId);
      if (c3dRef.current) {
        const dup = result.zones.find((z) => z.id === result.newId);
        if (dup) {
          c3dRef.current.addRoom(dup);
          c3dRef.current.selectZone(result.newId);
        }
      }
    },
    [zones]
  );

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
    if (['width', 'depth', 'height', 'x', 'y', 'z', 'floor'].includes(field)) {
      value = Math.max(field === 'floor' ? 1 : 0.1, parseFloat(rawValue) || 0);
    }
    handleUpdateElement(selectedId, { [field]: value });
    setEditingField(null);
  };

  /* ── canvas toolbar actions ── */
  const handleCanvasAction = (action) => {
    if (action === 'fit') c3dRef.current?.fitCamera();
    if (action === 'reset') {
      c3dRef.current?.resetCamera();
      setSelectedId(null);
    }
    if (action === 'grid') {
      setShowGrid((g) => !g);
      c3dRef.current?.toggleGrid();
    }
  };

  /* ── exports ── */
  const handleExportPDF = async () => {
    try {
      await apiService.generateReport({ sessionId: design?.session_id, layoutData: { zones } });
      setExportStatus({ type: 'success', message: 'PDF generated successfully!' });
      setTimeout(() => setExportStatus(null), 3000);
    } catch (e) {
      setExportStatus({ type: 'error', message: `PDF export failed: ${e.message}` });
      setTimeout(() => setExportStatus(null), 5000);
    }
  };

  const handleExportDXF = async () => {
    try {
      await apiService.generateDXF({ sessionId: design?.session_id, layoutData: { zones } });
      setExportStatus({ type: 'success', message: 'DXF generated successfully!' });
      setTimeout(() => setExportStatus(null), 3000);
    } catch (e) {
      setExportStatus({ type: 'error', message: `DXF export failed: ${e.message}` });
      setTimeout(() => setExportStatus(null), 5000);
    }
  };

  const handleExportJSON = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            design,
            settings: designSettings,
            zones,
            timestamp: new Date().toISOString(),
          },
          null,
          2
        ),
      ],
      { type: 'application/json' }
    );
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'design.json';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleScreenshot = () => {
    const cv =
      viewMode === '2d'
        ? canvas2DRef.current
        : canvas3DRef.current?.querySelector('canvas');
    if (!cv) return;
    const a = document.createElement('a');
    a.href = cv.toDataURL('image/png');
    a.download = `design-${viewMode}-${Date.now()}.png`;
    a.click();
  };

  /* ── render guards ── */
  if (isLoading)
    return (
      <div className="studio-loading">
        <div className="loading-spinner" />
        <span>Loading design…</span>
      </div>
    );

  if (error)
    return (
      <div className="studio-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          ← Back to Home
        </button>
      </div>
    );

  const selectedZone = zones.find((z) => z.id === selectedId);

  return (
    <div className="studio-wrapper">
      <TopBar
        designSettings={designSettings}
        isFallback={isFallback}
        handleExportPDF={handleExportPDF}
        handleExportDXF={handleExportDXF}
        handleExportJSON={handleExportJSON}
        handleScreenshot={handleScreenshot}
      />

      <div className="studio-layout">
        <LeftSidebar
          leftOpen={leftOpen}
          setLeftOpen={setLeftOpen}
          designSettings={designSettings}
          showAddMenu={showAddMenu}
          setShowAddMenu={setShowAddMenu}
          handleAddElement={handleAddElement}
        />

        <main className="studio-center">
          <CanvasToolbar
            viewMode={viewMode}
            setViewMode={setViewMode}
            transformMode={transformMode}
            setTransformMode={setTransformMode}
            snapToGrid={snapToGrid}
            setSnapToGrid={setSnapToGrid}
            showGrid={showGrid}
            handleCanvasAction={handleCanvasAction}
          />

          <div className="canvas-container">
            {viewMode === '2d' ? (
              <Canvas2DView canvas2DRef={canvas2DRef} handleCanvas2DClick={handleCanvas2DClick} />
            ) : (
              <Canvas3DView
                canvas3DRef={canvas3DRef}
                transformMode={transformMode}
                snapToGrid={snapToGrid}
              />
            )}
          </div>

          <CanvasCaption selectedZone={selectedZone} />
        </main>

        <RightSidebar
          rightOpen={rightOpen}
          setRightOpen={setRightOpen}
          zones={zones}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          selectedZone={selectedZone}
          editingField={editingField}
          setEditingField={setEditingField}
          stats={stats}
          handleInspectorChange={handleInspectorChange}
          handleDuplicateElement={handleDuplicateElement}
          handleDeleteElement={handleDeleteElement}
        />
      </div>

      {exportStatus && (
        <div className={`export-notification export-notification-${exportStatus.type}`}>
          {exportStatus.message}
        </div>
      )}
    </div>
  );
}

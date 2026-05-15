/**
 * CanvasToolbar - Toolbar with view modes, transform tools, and canvas actions
 */
import { TRANSFORM_MODES } from '../../utils/constants';

export default function CanvasToolbar({
  viewMode,
  setViewMode,
  transformMode,
  setTransformMode,
  snapToGrid,
  setSnapToGrid,
  showGrid,
  handleCanvasAction,
}) {
  return (
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
        <button
          className={`btn-toolbar ${showGrid ? 'active' : ''}`}
          onClick={() => handleCanvasAction('grid')}
          title="Toggle Grid"
        >
          ⊞ Grid
        </button>
        <button className="btn-toolbar" onClick={() => handleCanvasAction('fit')} title="Fit to View">
          ▢ Fit
        </button>
        <button className="btn-toolbar" onClick={() => handleCanvasAction('reset')} title="Reset Camera">
          ↺ Reset
        </button>
      </div>
    </div>
  );
}

/**
 * RightSidebar - Layers list, inspector panel, and statistics
 */
import React from 'react';
import { ROOM_TYPES, ROOM_LABELS } from '../../utils/constants';
import { getRoomTypeColor } from '../../utils/fallback';

export default function RightSidebar({
  rightOpen,
  setRightOpen,
  zones,
  selectedId,
  setSelectedId,
  selectedZone,
  editingField,
  setEditingField,
  stats,
  handleInspectorChange,
  handleDuplicateElement,
  handleDeleteElement,
}) {
  return (
    <aside className={`studio-sidebar-right ${rightOpen ? 'open' : 'collapsed'}`}>
      <button className="sidebar-toggle-btn" onClick={() => setRightOpen(!rightOpen)}>
        ☰
      </button>
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
                  <div
                    className="layer-color"
                    style={{ backgroundColor: getRoomTypeColor(zone.room_type) }}
                  />
                  <span className="layer-label">{zone.label}</span>
                  <span className="layer-floor">F{zone.floor}</span>
                  <div className="layer-actions">
                    <button
                      className="btn-small-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDuplicateElement(zone.id);
                      }}
                      title="Duplicate"
                    >
                      📋
                    </button>
                    <button
                      className="btn-small-icon btn-danger"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteElement(zone.id);
                      }}
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
                {/* Label */}
                <div className="inspector-row">
                  <span className="inspector-label">Name</span>
                  {editingField === 'label' ? (
                    <input
                      className="inspector-input"
                      type="text"
                      defaultValue={selectedZone.label}
                      autoFocus
                      onBlur={(e) => handleInspectorChange('label', e.target.value)}
                      onKeyDown={(e) =>
                        e.key === 'Enter' && handleInspectorChange('label', e.target.value)
                      }
                    />
                  ) : (
                    <span
                      className="inspector-value"
                      onClick={() => setEditingField('label')}
                    >
                      {selectedZone.label}
                    </span>
                  )}
                </div>

                {/* Type */}
                <div className="inspector-row">
                  <span className="inspector-label">Type</span>
                  <select
                    className="inspector-input"
                    value={selectedZone.room_type}
                    onChange={(e) => handleInspectorChange('room_type', e.target.value)}
                  >
                    {ROOM_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {ROOM_LABELS[t] || t}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Position */}
                <div className="inspector-group-label">Position (m)</div>
                {['x', 'y', 'z'].map((f) => (
                  <div className="inspector-row" key={f}>
                    <span className="inspector-label">{f.toUpperCase()}</span>
                    <input
                      className="inspector-input"
                      type="number"
                      step="0.1"
                      key={`${selectedId}-${f}-${selectedZone[f]}`}
                      defaultValue={(selectedZone[f] || 0).toFixed(2)}
                      onBlur={(e) => handleInspectorChange(f, e.target.value)}
                      onKeyDown={(e) =>
                        e.key === 'Enter' && handleInspectorChange(f, e.target.value)
                      }
                    />
                  </div>
                ))}

                {/* Dimensions */}
                <div className="inspector-group-label">Dimensions (m)</div>
                {[
                  ['width', 'W'],
                  ['depth', 'D'],
                  ['height', 'H'],
                ].map(([f, lbl]) => (
                  <div className="inspector-row" key={f}>
                    <span className="inspector-label">{lbl}</span>
                    <input
                      className="inspector-input"
                      type="number"
                      step="0.1"
                      min="0.1"
                      key={`${selectedId}-${f}-${selectedZone[f]}`}
                      defaultValue={selectedZone[f]?.toFixed(2)}
                      onBlur={(e) => handleInspectorChange(f, e.target.value)}
                      onKeyDown={(e) =>
                        e.key === 'Enter' && handleInspectorChange(f, e.target.value)
                      }
                    />
                  </div>
                ))}

                {/* Floor + Rotation */}
                <div className="inspector-row">
                  <span className="inspector-label">Floor</span>
                  <input
                    className="inspector-input"
                    type="number"
                    min="1"
                    key={`${selectedId}-floor-${selectedZone.floor}`}
                    defaultValue={selectedZone.floor}
                    onBlur={(e) => handleInspectorChange('floor', e.target.value)}
                  />
                </div>
                <div className="inspector-row">
                  <span className="inspector-label">Rot °</span>
                  <input
                    className="inspector-input"
                    type="number"
                    step="15"
                    key={`${selectedId}-rot-${selectedZone.rotation}`}
                    defaultValue={selectedZone.rotation || 0}
                    onBlur={(e) => handleInspectorChange('rotation', e.target.value)}
                  />
                </div>

                {/* Quick actions */}
                <div className="inspector-actions">
                  <button
                    className="btn btn-small btn-secondary"
                    onClick={() => handleDuplicateElement(selectedId)}
                  >
                    📋 Duplicate
                  </button>
                  <button
                    className="btn btn-small btn-danger-sm"
                    onClick={() => handleDeleteElement(selectedId)}
                  >
                    🗑 Delete
                  </button>
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
                  <div className="stat-label">Built-up</div>
                  <div className="stat-value">{stats.builtUpArea} m²</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Parking</div>
                  <div className="stat-value">{stats.parkingArea} m²</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Rooms</div>
                  <div className="stat-value">{zones.length}</div>
                </div>
                <div className="stat-item">
                  <div className="stat-label">Floors</div>
                  <div className="stat-value">
                    {Math.max(...zones.map((z) => z.floor || 1), 1)}
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      )}
    </aside>
  );
}

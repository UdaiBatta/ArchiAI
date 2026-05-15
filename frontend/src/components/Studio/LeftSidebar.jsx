/**
 * LeftSidebar - Design brief, add element menu, and design actions
 */
import { ROOM_TYPES, ROOM_LABELS } from '../../utils/constants';

export default function LeftSidebar({
  leftOpen,
  setLeftOpen,
  designSettings,
  showAddMenu,
  setShowAddMenu,
  handleAddElement,
}) {
  return (
    <aside className={`studio-sidebar-left ${leftOpen ? 'open' : 'collapsed'}`}>
      <button className="sidebar-toggle-btn" onClick={() => setLeftOpen(!leftOpen)}>
        ☰
      </button>
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
                  <span>{label}:</span>
                  <strong>{val}</strong>
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
                    <button
                      key={t}
                      className="btn btn-small"
                      onClick={() => handleAddElement(t)}
                    >
                      + {ROOM_LABELS[t] || t}
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

          {/* Design Actions */}
          <section className="sidebar-section">
            <h3>Design Actions</h3>
            <button className="btn btn-secondary full-width">
              ✨ Regenerate
            </button>
            <button className="btn btn-secondary full-width design-actions-btn">
              ✓ Check Compliance
            </button>
          </section>
        </div>
      )}
    </aside>
  );
}

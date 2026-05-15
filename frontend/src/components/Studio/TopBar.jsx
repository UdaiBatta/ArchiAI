/**
 * TopBar - Header with title, home button, and export menu
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function TopBar({
  designSettings,
  isFallback,
  handleExportPDF,
  handleExportDXF,
  handleExportJSON,
  handleScreenshot,
}) {
  const navigate = useNavigate();
  const [showExportMenu, setShowExportMenu] = useState(false);

  return (
    <header className="studio-topbar">
      <div className="topbar-left">
        <button className="btn-icon-small" onClick={() => navigate('/')} title="Back">
          ← Home
        </button>
        <h2 className="project-title">
          {designSettings?.prompt?.substring(0, 45) || 'Untitled Design'}
        </h2>
        {isFallback && <span className="badge-fallback">Demo Layout</span>}
      </div>
      <div className="topbar-right">
        <button className="btn btn-secondary" title="Save">
          💾 Save
        </button>
        <div className="menu-divider" />
        <div style={{ position: 'relative' }}>
          <button
            className="btn btn-secondary"
            onClick={() => setShowExportMenu(!showExportMenu)}
          >
            ⬇ Export
          </button>
          {showExportMenu && (
            <div className="export-menu" style={{ display: 'flex' }}>
              <button onClick={handleExportPDF}>📄 PDF Report</button>
              <button onClick={handleExportDXF}>🏗 DXF File</button>
              <button onClick={handleExportJSON}>{ } JSON</button>
              <button onClick={handleScreenshot}>📸 Screenshot</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

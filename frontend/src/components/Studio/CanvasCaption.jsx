/**
 * CanvasCaption - Status bar showing selected zone information
 */
import React from 'react';

export default function CanvasCaption({ selectedZone }) {
  if (!selectedZone) return null;

  return (
    <div className="canvas-caption">
      <strong>{selectedZone.label}</strong>
      {' '}•{' '}{selectedZone.width?.toFixed(1)}m × {selectedZone.depth?.toFixed(1)}m × {selectedZone.height?.toFixed(1)}m
      {' '}•{' '}{(selectedZone.width * selectedZone.depth).toFixed(1)} m²
      {' '}•{' '}Floor {selectedZone.floor}
    </div>
  );
}

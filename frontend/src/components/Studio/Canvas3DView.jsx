/**
 * Canvas3DView - Wrapper for 3D canvas rendering
 */
import { TRANSFORM_MODES } from '../../utils/constants';

export default function Canvas3DView({ canvas3DRef, transformMode, snapToGrid }) {
  return (
    <>
      <div ref={canvas3DRef} className="canvas-3d" />
      {/* Mode badge overlay for 3D */}
      <div className="transform-badge">
        {TRANSFORM_MODES.find((m) => m.id === transformMode)?.icon}{' '}
        {TRANSFORM_MODES.find((m) => m.id === transformMode)?.label}
        {snapToGrid && <span className="snap-dot">⊞</span>}
      </div>
    </>
  );
}

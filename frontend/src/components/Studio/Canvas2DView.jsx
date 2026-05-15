/**
 * Canvas2DView - Wrapper for 2D canvas rendering
 */

export default function Canvas2DView({ canvas2DRef, handleCanvas2DClick }) {
  return (
    <canvas
      ref={canvas2DRef}
      className="canvas-2d"
      onClick={handleCanvas2DClick}
      width={1200}
      height={800}
    />
  );
}

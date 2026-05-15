/**
 * 2D Canvas rendering utilities
 */

import { getColorHex } from './colors.js';
import { CANVAS_CONSTANTS, CANVAS_COLORS } from './constants.js';

export function render2DCanvas(canvas, zones, settings = {}) {
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Clear canvas
  ctx.fillStyle = CANVAS_COLORS.BG_2D;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const { plotWidth = 30, plotDepth = 40, selectedZoneId = null } = settings;

  // Calculate scale to fit design in canvas
  const padding = CANVAS_CONSTANTS.PADDING;
  const availableWidth = canvas.width - padding * 2;
  const availableHeight = canvas.height - padding * 2;

  const scaleX = availableWidth / plotWidth;
  const scaleY = availableHeight / plotDepth;
  const scale = Math.min(scaleX, scaleY, CANVAS_CONSTANTS.MAX_SCALE); // Cap scale for readability

  const offsetX = padding + (availableWidth - plotWidth * scale) / 2;
  const offsetY = padding + (availableHeight - plotDepth * scale) / 2;

  // Draw plot boundary
  ctx.strokeStyle = CANVAS_COLORS.PLOT_BORDER;
  ctx.lineWidth = CANVAS_CONSTANTS.GRID_LINE_WIDTH;
  ctx.strokeRect(
    offsetX,
    offsetY,
    plotWidth * scale,
    plotDepth * scale
  );

  // Draw grid
  ctx.strokeStyle = CANVAS_COLORS.GRID_2D;
  ctx.lineWidth = 0.5;
  const gridSize = CANVAS_CONSTANTS.GRID_SIZE; // 5m grid
  for (let i = 0; i <= plotWidth; i += gridSize) {
    const x = offsetX + i * scale;
    ctx.beginPath();
    ctx.moveTo(x, offsetY);
    ctx.lineTo(x, offsetY + plotDepth * scale);
    ctx.stroke();
  }
  for (let i = 0; i <= plotDepth; i += gridSize) {
    const y = offsetY + i * scale;
    ctx.beginPath();
    ctx.moveTo(offsetX, y);
    ctx.lineTo(offsetX + plotWidth * scale, y);
    ctx.stroke();
  }

  // Draw zones
  zones.forEach((zone) => {
    const x = offsetX + zone.x * scale;
    const y = offsetY + zone.y * scale;
    const width = zone.width * scale;
    const height = zone.depth * scale;

    // Room fill
    const colorHex = getColorHex(zone.room_type);
    ctx.fillStyle = colorHex;
    ctx.globalAlpha = selectedZoneId === zone.id ? CANVAS_COLORS.SELECTED_ALPHA : CANVAS_COLORS.UNSELECTED_ALPHA;
    ctx.fillRect(x, y, width, height);

    // Room border
    ctx.strokeStyle = selectedZoneId === zone.id ? CANVAS_COLORS.SELECTED_BORDER : 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = selectedZoneId === zone.id ? 3 : 1.5;
    ctx.strokeRect(x, y, width, height);
    ctx.globalAlpha = 1.0;

    // Room label
    ctx.fillStyle = CANVAS_COLORS.TEXT_COLOR;
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Check if label fits
    const labelWidth = ctx.measureText(zone.label).width;
    if (labelWidth < width - 4 && 20 < height) {
      ctx.fillText(zone.label, x + width / 2, y + height / 2);
    } else if (zone.label.length > 0 && width > 20) {
      // Abbreviated label
      ctx.font = '10px sans-serif';
      const abbrev = zone.label.substring(0, 3);
      ctx.fillText(abbrev, x + width / 2, y + height / 2);
    }
  });

  // Draw compass
  drawCompass(ctx, canvas.width - 50, 40, 30);
}

function drawCompass(ctx, x, y, size) {
  // Circle
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.stroke();

  // N arrow
  ctx.strokeStyle = '#14B8A6';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y - size + 5);
  ctx.lineTo(x, y - size + 15);
  ctx.stroke();

  // N label
  ctx.fillStyle = '#14B8A6';
  ctx.font = 'bold 10px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('N', x, y - size + 20);
}

/**
 * Handle canvas click for zone selection
 */
export function getClickedZone(canvas, zones, clickX, clickY, settings = {}) {
  const { plotWidth = 30, plotDepth = 40 } = settings;

  const padding = 40;
  const availableWidth = canvas.width - padding * 2;
  const availableHeight = canvas.height - padding * 2;

  const scaleX = availableWidth / plotWidth;
  const scaleY = availableHeight / plotDepth;
  const scale = Math.min(scaleX, scaleY, 10);

  const offsetX = padding + (availableWidth - plotWidth * scale) / 2;
  const offsetY = padding + (availableHeight - plotDepth * scale) / 2;

  // Convert click to world coordinates
  const worldX = (clickX - offsetX) / scale;
  const worldY = (clickY - offsetY) / scale;

  // Check which zone was clicked
  for (let i = zones.length - 1; i >= 0; i--) {
    const zone = zones[i];
    if (
      worldX >= zone.x &&
      worldX <= zone.x + zone.width &&
      worldY >= zone.y &&
      worldY <= zone.y + zone.depth
    ) {
      return zone;
    }
  }

  return null;
}

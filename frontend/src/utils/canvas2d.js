/**
 * 2D Canvas rendering utilities
 */

export function render2DCanvas(canvas, zones, settings = {}) {
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Clear canvas
  ctx.fillStyle = '#0F172A';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const { plotWidth = 30, plotDepth = 40, selectedZoneId = null } = settings;

  // Calculate scale to fit design in canvas
  const padding = 40;
  const availableWidth = canvas.width - padding * 2;
  const availableHeight = canvas.height - padding * 2;

  const scaleX = availableWidth / plotWidth;
  const scaleY = availableHeight / plotDepth;
  const scale = Math.min(scaleX, scaleY, 10); // Cap scale for readability

  const offsetX = padding + (availableWidth - plotWidth * scale) / 2;
  const offsetY = padding + (availableHeight - plotDepth * scale) / 2;

  // Draw plot boundary
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
  ctx.lineWidth = 2;
  ctx.strokeRect(
    offsetX,
    offsetY,
    plotWidth * scale,
    plotDepth * scale
  );

  // Draw grid
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  ctx.lineWidth = 0.5;
  const gridSize = 5; // 5m grid
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
    const colors = {
      living_room: '#3B82F6',
      kitchen: '#F59E0B',
      bedroom: '#EC4899',
      bathroom: '#10B981',
      staircase: '#8B5CF6',
      parking: '#4B5563',
      corridor: '#6B7280',
      terrace: '#06B6D4',
      balcony: '#14B8A6',
    };

    ctx.fillStyle = colors[zone.room_type] || '#6B7280';
    ctx.globalAlpha = selectedZoneId === zone.id ? 1.0 : 0.6;
    ctx.fillRect(x, y, width, height);

    // Room border
    ctx.strokeStyle = selectedZoneId === zone.id ? '#FBBF24' : 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = selectedZoneId === zone.id ? 3 : 1.5;
    ctx.strokeRect(x, y, width, height);
    ctx.globalAlpha = 1.0;

    // Room label
    ctx.fillStyle = '#E5E7EB';
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

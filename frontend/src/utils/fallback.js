/**
 * Prompt-aware fallback layout generator.
 * Detects building type from the prompt string and scales rooms to plot dimensions.
 */

/* ─── helpers ──────────────────────────────────────── */
function id(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function room(room_type, label, x, y, width, depth, height = 3, floor = 1, rotation = 0) {
  return {
    id: id(room_type),
    room_type, label,
    x, y,
    z: 0,           // ground-level by default
    width, depth, height, floor,
    rotation,
    visible: true,
    locked: false,
    area: +(width * depth).toFixed(2),
  };
}

/* ─── Residential layout ───────────────────────────── */
function residentialLayout(plotW, plotD, numFloors) {
  const scaleX = plotW / 12;  // reference plot: 12 m wide
  const scaleY = plotD / 10;  // reference plot: 10 m deep
  const sc = (w) => +(w * scaleX).toFixed(2);
  const sd = (d) => +(d * scaleY).toFixed(2);

  const rooms = [
    room('parking', 'Parking', 0, 0, sc(6), sd(2.5), 2.5, 1),
    room('staircase', 'Staircase', sc(6), 0, sc(1.5), sd(2.5), 3.2, 1),
    room('living_room', 'Living Room', 0, sd(2.5), sc(5), sd(3.5), 3.5, 1),
    room('kitchen', 'Kitchen', sc(5), sd(2.5), sc(3), sd(3), 3.0, 1),
    room('bathroom', 'Bathroom', sc(8), sd(2.5), sc(2), sd(2), 2.7, 1),
    room('bedroom', 'Bedroom 1', 0, sd(6), sc(4), sd(4), 3.5, 1),
    room('bedroom', 'Bedroom 2', sc(4), sd(6), sc(4), sd(4), 3.5, 1),
  ];

  // Second floor if numFloors >= 2
  if (numFloors >= 2) {
    rooms.push(
      room('bedroom', 'Bedroom 3', 0, 0, sc(5), sd(4), 3.5, 2),
      room('bathroom', 'Bathroom 2', sc(5), 0, sc(2), sd(2.5), 2.7, 2),
      room('balcony', 'Balcony', sc(7), 0, sc(3), sd(2), 2.8, 2),
      room('terrace', 'Terrace', 0, sd(4), sc(6), sd(3), 2.5, 2),
    );
  }

  return rooms;
}

/* ─── Office layout ────────────────────────────────── */
function officeLayout(plotW, plotD, numFloors) {
  const scaleX = plotW / 12;
  const scaleY = plotD / 10;
  const sc = (w) => +(w * scaleX).toFixed(2);
  const sd = (d) => +(d * scaleY).toFixed(2);

  const rooms = [
    room('parking', 'Parking', 0, 0, sc(12), sd(2.5), 2.5, 1),
    room('staircase', 'Staircase', sc(10), sd(2.5), sc(2), sd(2.5), 3.2, 1),
    room('corridor', 'Lobby', 0, sd(2.5), sc(4), sd(2), 3.5, 1),
    room('office', 'Reception', sc(4), sd(2.5), sc(4), sd(2), 3.5, 1),
    room('bathroom', 'Bathroom', sc(8), sd(2.5), sc(2), sd(2), 2.7, 1),
    room('office', 'Work Area', 0, sd(4.5), sc(6), sd(4), 3.2, 1),
    room('office', 'Meeting Rm', sc(6), sd(4.5), sc(4), sd(3), 3.2, 1),
    room('office', 'Office', sc(6), sd(7.5), sc(4), sd(2.5), 3.2, 1),
  ];

  if (numFloors >= 2) {
    rooms.push(
      room('office', 'Work Area 2', 0, 0, sc(8), sd(4.5), 3.2, 2),
      room('office', 'Conference', sc(8), 0, sc(4), sd(4.5), 3.2, 2),
      room('bathroom', 'Bathroom 2', 0, sd(4.5), sc(2), sd(2), 2.7, 2),
      room('balcony', 'Break Area', sc(2), sd(4.5), sc(4), sd(2.5), 2.8, 2),
    );
  }

  return rooms;
}

/* ─── Mixed / parking-heavy layout ─────────────────── */
function mixedLayout(plotW, plotD, numFloors) {
  const scaleX = plotW / 12;
  const scaleY = plotD / 10;
  const sc = (w) => +(w * scaleX).toFixed(2);
  const sd = (d) => +(d * scaleY).toFixed(2);

  return [
    room('parking', 'Parking A', 0, 0, sc(6), sd(3), 2.5, 1),
    room('parking', 'Parking B', sc(6), 0, sc(6), sd(3), 2.5, 1),
    room('staircase', 'Staircase', sc(5.5), sd(3), sc(1.5), sd(2), 3.2, 1),
    room('living_room', 'Living', 0, sd(3), sc(5), sd(3.5), 3.5, 1),
    room('kitchen', 'Kitchen', sc(5), sd(3), sc(3), sd(3), 3.0, 1),
    room('office', 'Work Area', sc(8), sd(3), sc(4), sd(3.5), 3.2, 1),
    room('bathroom', 'Bathroom', 0, sd(6.5), sc(2), sd(2), 2.7, 1),
    room('bedroom', 'Bedroom', sc(2), sd(6.5), sc(4), sd(3.5), 3.5, 1),
  ];
}

/* ─── Build type detector ───────────────────────────── */
function detectBuildingType(prompt = '', buildingType = 'residential') {
  const p = (prompt + ' ' + buildingType).toLowerCase();
  if (p.includes('office') || p.includes('commercial') || p.includes('corporate')) return 'office';
  if (p.includes('mixed') || p.includes('shopping') || p.includes('retail')) return 'mixed';
  return 'residential';
}

/* ─── Main export ───────────────────────────────────── */
export function generateFallbackLayout(settings = {}) {
  const {
    plotWidth = 30,
    plotDepth = 40,
    numFloors = 2,
    prompt = '',
    buildingType = 'residential',
  } = settings;

  const type = detectBuildingType(prompt, buildingType);

  let rooms;
  if (type === 'office') rooms = officeLayout(plotWidth, plotDepth, numFloors);
  else if (type === 'mixed') rooms = mixedLayout(plotWidth, plotDepth, numFloors);
  else rooms = residentialLayout(plotWidth, plotDepth, numFloors);

  return {
    session_id: `fallback_${Date.now()}`,
    layout_zones: rooms,
    metadata: {
      status: 'fallback_generated',
      building_type: type,
      message: 'Backend not reachable. Showing demo layout.',
      plot_width_m: plotWidth,
      plot_depth_m: plotDepth,
      num_floors: numFloors,
    },
  };
}

/* ─── Statistics ────────────────────────────────────── */
export function calculateStats(zones) {
  if (!zones || !zones.length) return { builtUpArea: 0, openArea: 0, parkingArea: 0, far: 0 };

  const builtUpArea = zones.reduce((s, z) => s + (z.width * z.depth || 0), 0);
  const parkingArea = zones
    .filter((z) => z.room_type === 'parking')
    .reduce((s, z) => s + (z.width * z.depth || 0), 0);

  return {
    builtUpArea: +builtUpArea.toFixed(2),
    openArea: 0,
    parkingArea: +parkingArea.toFixed(2),
    far: 0,
  };
}

/* ─── Room colour map ───────────────────────────────── */
export function getRoomTypeColor(roomType) {
  const colors = {
    living_room: '#3B82F6',
    kitchen: '#F59E0B',
    bedroom: '#EC4899',
    bathroom: '#10B981',
    staircase: '#8B5CF6',
    parking: '#6B7280',
    corridor: '#9CA3AF',
    terrace: '#06B6D4',
    balcony: '#14B8A6',
    office: '#6366F1',
    generic: '#9CA3AF',
  };
  return colors[roomType] || '#6B7280';
}

export function calculateBoundingBox(zones) {
  if (!zones || !zones.length) return { minX: 0, minY: 0, maxX: 30, maxY: 40 };
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  zones.forEach((z) => {
    minX = Math.min(minX, z.x);
    minY = Math.min(minY, z.y);
    maxX = Math.max(maxX, z.x + (z.width || 0));
    maxY = Math.max(maxY, z.y + (z.depth || 0));
  });
  return { minX: Math.max(0, minX - 1), minY: Math.max(0, minY - 1), maxX: maxX + 1, maxY: maxY + 1 };
}

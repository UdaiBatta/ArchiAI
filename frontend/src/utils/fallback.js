/**
 * Generate fallback demo layout when backend fails
 */
export function generateFallbackLayout(settings) {
  const { plotWidth = 30, plotDepth = 40, numFloors = 2 } = settings;

  // Create a simple residential layout
  const rooms = [
    {
      id: 'living_room',
      room_type: 'living_room',
      x: 1,
      y: 1,
      width: 5,
      depth: 4,
      height: 3.5,
      floor: 1,
      label: 'Living Room',
      area: 20,
    },
    {
      id: 'kitchen',
      room_type: 'kitchen',
      x: 6,
      y: 1,
      width: 3,
      depth: 4,
      height: 3,
      floor: 1,
      label: 'Kitchen',
      area: 12,
    },
    {
      id: 'bedroom1',
      room_type: 'bedroom',
      x: 1,
      y: 5,
      width: 4,
      depth: 4,
      height: 3.5,
      floor: 1,
      label: 'Bedroom 1',
      area: 16,
    },
    {
      id: 'bedroom2',
      room_type: 'bedroom',
      x: 6,
      y: 5,
      width: 4,
      depth: 4,
      height: 3.5,
      floor: 1,
      label: 'Bedroom 2',
      area: 16,
    },
    {
      id: 'bathroom',
      room_type: 'bathroom',
      x: 10,
      y: 1,
      width: 2,
      depth: 2,
      height: 2.5,
      floor: 1,
      label: 'Bathroom',
      area: 4,
    },
    {
      id: 'staircase',
      room_type: 'staircase',
      x: 10,
      y: 5,
      width: 2,
      depth: 4,
      height: 3,
      floor: 1,
      label: 'Staircase',
      area: 8,
    },
    {
      id: 'parking',
      room_type: 'parking',
      x: 0,
      y: 9,
      width: 12,
      depth: plotDepth - 9,
      height: 2.5,
      floor: 1,
      label: 'Parking',
      area: 12 * (plotDepth - 9),
    },
  ];

  // Add second floor if needed
  if (numFloors >= 2) {
    rooms.push({
      id: 'bedroom3',
      room_type: 'bedroom',
      x: 1,
      y: 1,
      width: 5,
      depth: 4,
      height: 3.5,
      floor: 2,
      label: 'Bedroom 3',
      area: 20,
    });
  }

  return {
    session_id: `fallback_${Date.now()}`,
    layout_zones: rooms,
    metadata: {
      status: 'fallback_generated',
      message: 'Backend not reachable. Showing demo layout.',
      plot_width_m: plotWidth,
      plot_depth_m: plotDepth,
      num_floors: numFloors,
    },
  };
}

/**
 * Calculate statistics from zones
 */
export function calculateStats(zones) {
  const builtUpArea = zones.reduce((sum, z) => sum + (z.width * z.depth || 0), 0);
  const openArea = 0; // Would be calculated from plot size - built-up area
  const parkingArea = zones
    .filter((z) => z.room_type === 'parking')
    .reduce((sum, z) => sum + (z.width * z.depth || 0), 0);
  const floorAreaRatio = 0; // Would be calculated from zones

  return {
    builtUpArea,
    openArea,
    parkingArea,
    far: floorAreaRatio,
  };
}

/**
 * Get color for room type
 */
export function getRoomTypeColor(roomType) {
  const colors = {
    living_room: '#3B82F6',      // Blue
    kitchen: '#F59E0B',          // Amber
    bedroom: '#EC4899',          // Pink
    bathroom: '#10B981',         // Green
    staircase: '#8B5CF6',        // Purple
    parking: '#6B7280',          // Gray
    corridor: '#9CA3AF',         // Light gray
    terrace: '#06B6D4',          // Cyan
    balcony: '#14B8A6',          // Teal
  };
  return colors[roomType] || '#6B7280';
}

/**
 * Calculate bounding box of all zones
 */
export function calculateBoundingBox(zones) {
  if (zones.length === 0) {
    return { minX: 0, minY: 0, maxX: 30, maxY: 40 };
  }

  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;

  zones.forEach((zone) => {
    minX = Math.min(minX, zone.x);
    minY = Math.min(minY, zone.y);
    maxX = Math.max(maxX, zone.x + (zone.width || 0));
    maxY = Math.max(maxY, zone.y + (zone.depth || 0));
  });

  return {
    minX: Math.max(0, minX - 1),
    minY: Math.max(0, minY - 1),
    maxX: maxX + 1,
    maxY: maxY + 1,
    width: maxX - minX + 2,
    height: maxY - minY + 2,
  };
}

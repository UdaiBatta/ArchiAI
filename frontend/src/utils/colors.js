/**
 * Centralized color palette for room types
 * Used across canvas2d, canvas3d, and UI components
 */

// Hex colors for 2D canvas rendering
export const ROOM_COLORS_HEX = {
  living_room: '#3B82F6',
  kitchen: '#F59E0B',
  bedroom: '#EC4899',
  bathroom: '#10B981',
  staircase: '#8B5CF6',
  parking: '#4B5563',
  corridor: '#6B7280',
  terrace: '#06B6D4',
  balcony: '#14B8A6',
  office: '#6366F1',
  generic: '#9CA3AF',
};

// Decimal colors for Three.js 3D rendering
export const ROOM_COLORS_THREE = {
  living_room: 0x3b82f6,
  kitchen: 0xf59e0b,
  bedroom: 0xec4899,
  bathroom: 0x10b981,
  staircase: 0x8b5cf6,
  parking: 0x4b5563,
  balcony: 0x14b8a6,
  office: 0x6366f1,
  corridor: 0x6b7280,
  terrace: 0x06b6d4,
  generic: 0x9ca3af,
};

// Get hex color for a room type (2D canvas)
export const getColorHex = (roomType) => {
  return ROOM_COLORS_HEX[roomType] || ROOM_COLORS_HEX.generic;
};

// Get Three.js decimal color for a room type (3D canvas)
export const getColorThree = (roomType) => {
  return ROOM_COLORS_THREE[roomType] || ROOM_COLORS_THREE.generic;
};

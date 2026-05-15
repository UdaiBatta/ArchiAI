/**
 * Constants - shared values across the application
 * Centralized room types, labels, modes, and magic numbers
 */

// Room types used throughout the application
export const ROOM_TYPES = [
  'living_room',
  'bedroom',
  'kitchen',
  'bathroom',
  'staircase',
  'parking',
  'balcony',
  'office',
  'corridor',
  'terrace',
  'generic',
];

// Human-readable labels for room types (for UI display)
export const ROOM_LABELS = {
  living_room: 'Living Room',
  bedroom: 'Bedroom',
  kitchen: 'Kitchen',
  bathroom: 'Bathroom',
  staircase: 'Staircase',
  parking: 'Parking',
  balcony: 'Balcony',
  office: 'Office',
  corridor: 'Corridor',
  terrace: 'Terrace',
  generic: 'Generic Room',
};

// Transform modes for 3D editor
export const TRANSFORM_MODES = [
  { id: 'select', icon: '↖', label: 'Select' },
  { id: 'translate', icon: '✛', label: 'Move' },
  { id: 'rotate', icon: '↻', label: 'Rotate' },
  { id: 'scale', icon: '⤢', label: 'Scale' },
];

// Canvas rendering constants
export const CANVAS_CONSTANTS = {
  PADDING: 40,           // Padding around canvas edges (pixels)
  GRID_SIZE: 5,          // Grid cell size (meters)
  SNAP_SIZE: 1.0,        // Snap-to-grid increment (meters)
  MAX_SCALE: 10,         // Maximum zoom scale factor
  DEFAULT_PLOT_WIDTH: 30,  // Default plot width (meters)
  DEFAULT_PLOT_DEPTH: 40,  // Default plot depth (meters)
  DEFAULT_FLOORS: 2,     // Default number of floors
};

// Canvas styling colors
export const CANVAS_COLORS = {
  BG_2D: '#0F172A',            // 2D canvas background
  BG_3D: 0x0d1117,             // 3D canvas background (Three.js hex)
  GRID_2D: 'rgba(255, 255, 255, 0.08)',
  GRID_3D: 0x444444,
  PLOT_BORDER: 'rgba(255, 255, 255, 0.2)',
  SELECTED_BORDER: '#FBBF24',
  SELECTED_ALPHA: 1.0,
  UNSELECTED_ALPHA: 0.6,
  TEXT_COLOR: '#E5E7EB',
  GRID_LINE_WIDTH: 2,
};

// Plot dimension limits
export const PLOT_LIMITS = {
  MIN_WIDTH: 10,
  MAX_WIDTH: 100,
  MIN_DEPTH: 10,
  MAX_DEPTH: 100,
};

// Default element dimensions
export const DEFAULT_DIMENSIONS = {
  width: 4,
  depth: 4,
  height: 3,
  z: 0,
};

// API endpoints (if needed for centralization)
export const API_ENDPOINTS = {
  GENERATE_DESIGN: '/api/generate/',
  GENERATE_REPORT: '/api/generate-report/',
  GENERATE_DXF: '/api/generate-dxf/',
  CHECK_HEALTH: '/api/health/',
};

/**
 * ElementManager — CRUD for zones/rooms
 * All elements follow the canonical shape:
 *   { id, room_type, label, x, y, z, width, depth, height,
 *     floor, rotation, visible, locked, area }
 */

const DEFAULT_DIMS = {
  living_room: { width: 5,   depth: 4,   height: 3.5 },
  bedroom:     { width: 4,   depth: 3.5, height: 3.5 },
  kitchen:     { width: 3.5, depth: 3,   height: 3.0 },
  bathroom:    { width: 2,   depth: 2,   height: 2.7 },
  staircase:   { width: 2.5, depth: 3.5, height: 3.2 },
  parking:     { width: 6,   depth: 3,   height: 2.5 },
  balcony:     { width: 3,   depth: 2,   height: 2.8 },
  office:      { width: 5,   depth: 4,   height: 3.2 },
  corridor:    { width: 2,   depth: 5,   height: 3.0 },
  terrace:     { width: 5,   depth: 4,   height: 2.5 },
  generic:     { width: 4,   depth: 4,   height: 3.0 },
};

const LABELS = {
  living_room: 'Living Room',
  bedroom:     'Bedroom',
  kitchen:     'Kitchen',
  bathroom:    'Bathroom',
  staircase:   'Staircase',
  parking:     'Parking',
  balcony:     'Balcony',
  office:      'Office',
  corridor:    'Corridor',
  terrace:     'Terrace',
  generic:     'Room',
};

export class ElementManager {
  static generateId() {
    return `zone_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  }

  static createElement(type, options = {}) {
    const dims = DEFAULT_DIMS[type] || DEFAULT_DIMS.generic;
    const w = options.width  || dims.width;
    const d = options.depth  || dims.depth;

    return {
      id:        ElementManager.generateId(),
      room_type: type,
      label:     LABELS[type] || 'Room',
      x:         options.x        ?? 0,
      y:         options.y        ?? 0,
      z:         options.z        ?? 0,
      width:     w,
      depth:     d,
      height:    options.height   ?? dims.height,
      floor:     options.floor    ?? 1,
      rotation:  options.rotation ?? 0,
      visible:   options.visible  ?? true,
      locked:    options.locked   ?? false,
      area:      +(w * d).toFixed(2),
    };
  }

  /**
   * Place a new element near the centroid of existing zones,
   * offset slightly so it doesn't overlap exactly.
   */
  static addElement(zones, type, positionHint = null) {
    let x = 0, y = 0;

    if (positionHint) {
      x = positionHint.x;
      y = positionHint.y;
    } else if (zones.length > 0) {
      // Centroid of existing layout
      const cx = zones.reduce((s, z) => s + z.x + z.width  / 2, 0) / zones.length;
      const cy = zones.reduce((s, z) => s + z.y + z.depth / 2, 0) / zones.length;

      // Find rightmost edge and place next to it
      const maxX = Math.max(...zones.map((z) => z.x + z.width));
      const dims = DEFAULT_DIMS[type] || DEFAULT_DIMS.generic;
      x = maxX + 0.5;
      y = cy - dims.depth / 2;
    }

    const newEl = ElementManager.createElement(type, { x, y });
    return {
      zones: [...zones, newEl],
      newId: newEl.id,
    };
  }

  static deleteElement(zones, id) {
    return zones.filter((z) => z.id !== id);
  }

  static duplicateElement(zones, id, offset = { x: 2, y: 2 }) {
    const original = zones.find((z) => z.id === id);
    if (!original) return { zones, newId: null };

    const dup = {
      ...original,
      id:    ElementManager.generateId(),
      label: `${original.label} (Copy)`,
      x:     original.x + offset.x,
      y:     original.y + offset.y,
    };

    return { zones: [...zones, dup], newId: dup.id };
  }

  static updateElement(zones, id, updates) {
    return zones.map((z) => {
      if (z.id !== id) return z;
      const updated = { ...z, ...updates };
      // Keep area in sync if dimensions changed
      if (updates.width !== undefined || updates.depth !== undefined) {
        updated.area = +((updated.width || z.width) * (updated.depth || z.depth)).toFixed(2);
      }
      return updated;
    });
  }

  static getElementsOnFloor(zones, floor) {
    return zones.filter((z) => z.floor === floor);
  }

  static validateElement(el) {
    return el && el.id && el.room_type && el.width > 0 && el.depth > 0 && el.height > 0;
  }
}

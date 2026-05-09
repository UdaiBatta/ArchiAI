/**
 * Element Manager - Handle CRUD operations for zones/elements
 */

export class ElementManager {
  static generateId() {
    return `zone_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  static createElement(type, options = {}) {
    const defaultDimensions = {
      living_room: { width: 5, depth: 4, height: 3 },
      bedroom: { width: 4, depth: 3.5, height: 3 },
      kitchen: { width: 3.5, depth: 3, height: 3 },
      bathroom: { width: 2, depth: 2, height: 2.7 },
      staircase: { width: 2.5, depth: 3.5, height: 3.2 },
      parking: { width: 6, depth: 3, height: 2.5 },
      balcony: { width: 3, depth: 2, height: 2.8 },
      office: { width: 4, depth: 3.5, height: 3 },
      corridor: { width: 2, depth: 4, height: 3 },
      terrace: { width: 5, depth: 4, height: 2.5 },
      generic: { width: 4, depth: 3, height: 3 },
    };

    const roomTypeLabels = {
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
      generic: 'Room',
    };

    const dims = defaultDimensions[type] || defaultDimensions.generic;

    return {
      id: ElementManager.generateId(),
      room_type: type,
      label: roomTypeLabels[type] || `Room ${Math.floor(Math.random() * 1000)}`,
      width: options.width || dims.width,
      depth: options.depth || dims.depth,
      height: options.height || dims.height,
      x: options.x || 0,
      y: options.y || 0,
      z: options.z || 0,
      floor: options.floor || 1,
      rotation: options.rotation || 0,
    };
  }

  static addElement(zones, type, position = { x: 0, y: 0 }) {
    const newElement = ElementManager.createElement(type, {
      x: position.x,
      y: position.y,
    });
    return [...zones, newElement];
  }

  static deleteElement(zones, id) {
    return zones.filter((zone) => zone.id !== id);
  }

  static duplicateElement(zones, id, offset = { x: 1, y: 1 }) {
    const original = zones.find((z) => z.id === id);
    if (!original) return zones;

    const duplicate = {
      ...original,
      id: ElementManager.generateId(),
      label: `${original.label} (Copy)`,
      x: original.x + offset.x,
      y: original.y + offset.y,
    };

    return [...zones, duplicate];
  }

  static updateElement(zones, id, updates) {
    return zones.map((zone) =>
      zone.id === id ? { ...zone, ...updates } : zone
    );
  }

  static moveElement(zones, id, dx, dy) {
    return zones.map((zone) =>
      zone.id === id ? { ...zone, x: zone.x + dx, y: zone.y + dy } : zone
    );
  }

  static resizeElement(zones, id, width, depth, height = null) {
    return zones.map((zone) => {
      if (zone.id === id) {
        return {
          ...zone,
          width: Math.max(0.5, width),
          depth: Math.max(0.5, depth),
          ...(height !== null && { height: Math.max(0.5, height) }),
        };
      }
      return zone;
    });
  }

  static rotateElement(zones, id, angle) {
    return zones.map((zone) =>
      zone.id === id ? { ...zone, rotation: (zone.rotation + angle) % 360 } : zone
    );
  }

  static findElement(zones, id) {
    return zones.find((z) => z.id === id);
  }

  static getElementsOnFloor(zones, floor) {
    return zones.filter((z) => z.floor === floor);
  }

  static validateElement(element) {
    return (
      element.id &&
      element.room_type &&
      element.width > 0 &&
      element.depth > 0 &&
      element.height > 0
    );
  }

  static calculateBounds(zones) {
    if (zones.length === 0) {
      return { minX: 0, maxX: 0, minY: 0, maxY: 0 };
    }

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    zones.forEach((zone) => {
      minX = Math.min(minX, zone.x);
      maxX = Math.max(maxX, zone.x + zone.width);
      minY = Math.min(minY, zone.y);
      maxY = Math.max(maxY, zone.y + zone.depth);
    });

    return { minX, maxX, minY, maxY };
  }

  static centerLayout(zones) {
    const bounds = ElementManager.calculateBounds(zones);
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    return zones.map((zone) => ({
      ...zone,
      x: zone.x - centerX + 15,
      y: zone.y - centerY + 20,
    }));
  }
}

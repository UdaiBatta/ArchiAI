import * as THREE from 'three';

/**
 * Canvas3D - Three.js-based 3D floor plan renderer
 * Handles zone visualization, selection, and camera controls
 */
export class Canvas3D {
  constructor(container, onZoneSelect = null) {
    this.container = container;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.zones = [];
    this.selectedZoneId = null;
    this.zoneObjects = new Map();
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.onZoneSelect = onZoneSelect;
    this.isDragging = false;
    this.previousMousePosition = { x: 0, y: 0 };
    this.showGrid = true;
    this.gridHelper = null;

    this.init();
  }

  init() {
    if (!this.container) {
      console.error('[Canvas3D] Container not found');
      return;
    }

    // Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0f172a);

    // Camera setup
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000);
    this.camera.position.set(20, 20, 20);
    this.camera.lookAt(0, 0, 0);

    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // Clear and add to container
    while (this.container.firstChild) {
      this.container.removeChild(this.container.firstChild);
    }
    this.container.appendChild(this.renderer.domElement);

    // Setup lighting
    this.setupLighting();

    // Setup grid
    this.setupGrid();

    // Setup controls
    this.setupControls();

    // Add ground plane
    this.addGround();

    // Event listeners
    this.renderer.domElement.addEventListener('click', (e) => this.onCanvasClick(e));
    window.addEventListener('resize', () => this.onWindowResize());

    // Start animation loop
    this.animate();

    console.log('[Canvas3D] Initialized successfully');
  }

  setupLighting() {
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    this.scene.add(ambientLight);

    // Directional light (sun)
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.9);
    directionalLight.position.set(50, 40, 50);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.set(2048, 2048);
    directionalLight.shadow.camera.left = -100;
    directionalLight.shadow.camera.right = 100;
    directionalLight.shadow.camera.top = 100;
    directionalLight.shadow.camera.bottom = -100;
    directionalLight.shadow.camera.near = 0.1;
    directionalLight.shadow.camera.far = 200;
    this.scene.add(directionalLight);

    // Point light for warmth
    const pointLight = new THREE.PointLight(0x2dd4bf, 0.5);
    pointLight.position.set(30, 30, 30);
    this.scene.add(pointLight);
  }

  setupGrid() {
    if (this.gridHelper) {
      this.scene.remove(this.gridHelper);
    }
    this.gridHelper = new THREE.GridHelper(100, 20, 0x444444, 0x222222);
    this.gridHelper.position.y = -0.01;
    this.scene.add(this.gridHelper);
  }

  toggleGrid() {
    this.showGrid = !this.showGrid;
    if (this.gridHelper) {
      this.gridHelper.visible = this.showGrid;
    }
  }

  addGround() {
    const groundGeometry = new THREE.PlaneGeometry(200, 200);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1f2e,
      metalness: 0.1,
      roughness: 0.9,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  setupControls() {
    this.renderer.domElement.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    this.renderer.domElement.addEventListener('mousemove', (e) => {
      if (this.isDragging) {
        const deltaX = e.clientX - this.previousMousePosition.x;
        const deltaY = e.clientY - this.previousMousePosition.y;

        // Orbit around center
        const centerX = 0,
          centerY = 0,
          centerZ = 0;
        const radius = this.camera.position.distanceTo(
          new THREE.Vector3(centerX, centerY, centerZ)
        );
        const theta = Math.atan2(
          this.camera.position.z - centerZ,
          this.camera.position.x - centerX
        );
        const phi = Math.acos((this.camera.position.y - centerY) / Math.max(radius, 0.001));

        const newTheta = theta - deltaX * 0.01;
        const newPhi = Math.max(0.1, Math.min(Math.PI - 0.1, phi + deltaY * 0.01));

        this.camera.position.x = centerX + radius * Math.sin(newPhi) * Math.cos(newTheta);
        this.camera.position.y = centerY + radius * Math.cos(newPhi);
        this.camera.position.z = centerZ + radius * Math.sin(newPhi) * Math.sin(newTheta);
        this.camera.lookAt(centerX, centerY, centerZ);
      }

      this.previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    this.renderer.domElement.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    // Zoom with scroll
    this.renderer.domElement.addEventListener('wheel', (e) => {
      e.preventDefault();
      const centerX = 0,
        centerY = 0,
        centerZ = 0;
      const direction = this.camera.position
        .clone()
        .sub(new THREE.Vector3(centerX, centerY, centerZ))
        .normalize();
      const distance = this.camera.position.distanceTo(
        new THREE.Vector3(centerX, centerY, centerZ)
      );
      const newDistance = Math.max(5, Math.min(150, distance + e.deltaY * 0.1));
      this.camera.position = new THREE.Vector3(centerX, centerY, centerZ).add(
        direction.multiplyScalar(newDistance)
      );
      this.camera.lookAt(centerX, centerY, centerZ);
    });
  }

  onCanvasClick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    const intersects = this.raycaster.intersectObjects(
      Array.from(this.zoneObjects.values()),
      false
    );

    if (intersects.length > 0) {
      const selectedObject = intersects[0].object;
      const zoneId = selectedObject.userData.zoneId;
      this.selectZone(zoneId);

      if (this.onZoneSelect) {
        this.onZoneSelect(zoneId);
      }
    } else {
      this.deselectZone();
      if (this.onZoneSelect) {
        this.onZoneSelect(null);
      }
    }
  }

  renderZones(zones) {
    this.zones = zones;

    // Remove old zone objects
    Array.from(this.zoneObjects.values()).forEach((obj) => {
      this.scene.remove(obj);
    });
    this.zoneObjects.clear();

    if (!zones || zones.length === 0) {
      console.log('[Canvas3D] No zones to render');
      return;
    }

    console.log(`[Canvas3D] Rendering ${zones.length} zones`);

    const colorMap = {
      living_room: 0x3b82f6,
      kitchen: 0xf59e0b,
      bedroom: 0xec4899,
      bathroom: 0x10b981,
      staircase: 0x8b5cf6,
      parking: 0x4b5563,
      balcony: 0x14b8a6,
      office: 0x3b82f6,
      corridor: 0x6b7280,
      terrace: 0x06b6d4,
      generic: 0x6b7280,
    };

    zones.forEach((zone) => {
      const color = colorMap[zone.room_type] || 0x6b7280;

      // Create box geometry
      const geometry = new THREE.BoxGeometry(
        Math.max(0.1, zone.width),
        Math.max(0.1, zone.height),
        Math.max(0.1, zone.depth)
      );

      const material = new THREE.MeshStandardMaterial({
        color,
        metalness: 0.3,
        roughness: 0.7,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.zoneId = zone.id;
      mesh.userData.zone = zone;

      // Position: center the zone
      mesh.position.set(
        zone.x + zone.width / 2,
        zone.height / 2,
        zone.y + zone.depth / 2
      );

      // Apply rotation if exists
      if (zone.rotation) {
        mesh.rotation.y = (zone.rotation * Math.PI) / 180;
      }

      this.scene.add(mesh);
      this.zoneObjects.set(zone.id, mesh);

      // Add label as text
      this.addZoneLabel(zone, mesh.position);
    });

    // Auto-fit camera to all zones
    this.fitCamera();

    console.log(`[Canvas3D] Added ${this.zoneObjects.size} zone meshes to scene`);
  }

  addZoneLabel(zone, position) {
    // Create a canvas texture with the zone label
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#e5e7eb';
    ctx.font = 'Bold 24px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(zone.label.substring(0, 15), canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({ map: texture });
    const sprite = new THREE.Sprite(spriteMaterial);

    sprite.scale.set(4, 1, 1);
    sprite.position.copy(position);
    sprite.position.y += zone.height + 0.5;

    this.scene.add(sprite);
  }

  selectZone(zoneId) {
    // Deselect previous
    this.deselectZone();

    // Select new
    const mesh = this.zoneObjects.get(zoneId);
    if (mesh) {
      this.selectedZoneId = zoneId;
      const originalMaterial = mesh.material.clone();
      mesh.userData.originalMaterial = originalMaterial;

      // Highlight
      mesh.material = new THREE.MeshStandardMaterial({
        color: 0xfbbf24,
        metalness: 0.5,
        roughness: 0.3,
        emissive: 0xfbbf24,
        emissiveIntensity: 0.3,
      });
    }
  }

  deselectZone() {
    if (this.selectedZoneId) {
      const mesh = this.zoneObjects.get(this.selectedZoneId);
      if (mesh && mesh.userData.originalMaterial) {
        mesh.material = mesh.userData.originalMaterial;
        mesh.userData.originalMaterial = null;
      }
      this.selectedZoneId = null;
    }
  }

  fitCamera() {
    if (this.zoneObjects.size === 0) return;

    const box = new THREE.Box3();
    this.zoneObjects.forEach((mesh) => {
      box.expandByObject(mesh);
    });

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = this.camera.fov * (Math.PI / 180);
    let cameraZ = maxDim / 2 / Math.tan(fov / 2);

    cameraZ *= 1.5; // Add padding

    this.camera.position.set(
      center.x + cameraZ * 0.3,
      center.y + cameraZ * 0.5,
      center.z + cameraZ
    );
    this.camera.lookAt(center);
  }

  resetCamera() {
    this.camera.position.set(20, 20, 20);
    this.camera.lookAt(0, 0, 0);
    this.deselectZone();
  }

  onWindowResize() {
    if (!this.container) return;

    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.zoneObjects.forEach((mesh) => {
      mesh.geometry.dispose();
      mesh.material.dispose();
    });
    this.zoneObjects.clear();

    this.renderer.dispose();
    if (this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
  }
}

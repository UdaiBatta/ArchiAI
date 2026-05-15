import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { getColorThree } from './colors.js';
import { CANVAS_CONSTANTS, CANVAS_COLORS } from './constants.js';

/**
 * Canvas3D — Hypar-style Three.js editor
 *
 * Coordinate mapping (per spec):
 *   Three.x = zone.x (horizontal)
 *   Three.y = zone.height/2 + zone.z  (vertical/elevation)
 *   Three.z = zone.y (floor-plan depth)
 *
 * Each room = THREE.Group positioned at the centre of the block.
 *   group.position = centre
 *   child mesh uses BoxGeometry(1,1,1) scaled to (width, height, depth)
 *
 * Public API (backward-compatible):
 *   renderZones(zones)       – full refresh
 *   addRoom(zone)            – incremental add
 *   removeRoom(id)           – incremental remove
 *   updateRoom(zone)         – incremental update (from inspector)
 *   selectZone(id)
 *   deselectZone()
 *   setMode(mode)            – 'select'|'translate'|'rotate'|'scale'
 *   setSnapToGrid(bool)
 *   fitCamera()
 *   resetCamera()
 *   toggleGrid()
 *   dispose()
 */
export class Canvas3D {
  constructor(container, onZoneSelect = null, onRoomTransformed = null) {
    this.container        = container;
    this.onZoneSelect     = onZoneSelect;
    this.onRoomTransformed = onRoomTransformed;

    this.scene      = null;
    this.camera     = null;
    this.renderer   = null;
    this.orbit      = null;
    this.transform  = null;

    this.zones       = [];
    this.zoneObjects = new Map(); // id → THREE.Group
    this.selectedId  = null;

    this.showGrid  = true;
    this.gridHelper = null;

    this.mode       = 'select';   // select | translate | rotate | scale
    this.snapToGrid = true;
    this.snapSize   = CANVAS_CONSTANTS.SNAP_SIZE;

    this._isTransforming = false;
    this._clickStart     = null;
    this._animId         = null;
    this._resizeObs      = null;

    this._raycaster = new THREE.Raycaster();
    this._mouse     = new THREE.Vector2();

    this._init();
  }

  /* ══════════════════════════════════════════════════════
     INIT
  ══════════════════════════════════════════════════════ */
  _init() {
    if (!this.container) { console.error('[Canvas3D] No container'); return; }

    const W = this.container.clientWidth  || 800;
    const H = this.container.clientHeight || 600;

    /* Scene */
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(CANVAS_COLORS.BG_3D);
    this.scene.fog = new THREE.FogExp2(CANVAS_COLORS.BG_3D, 0.008);

    /* Camera */
    this.camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 2000);
    this.camera.position.set(25, 22, 28);

    /* Renderer */
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(W, H);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace  = THREE.SRGBColorSpace;
    this.renderer.toneMapping       = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;

    while (this.container.firstChild) this.container.removeChild(this.container.firstChild);
    this.container.appendChild(this.renderer.domElement);

    /* Lighting / Grid / Ground */
    this._setupLighting();
    this._setupGrid();
    this._addGround();

    /* OrbitControls */
    this.orbit = new OrbitControls(this.camera, this.renderer.domElement);
    this.orbit.enableDamping  = true;
    this.orbit.dampingFactor  = 0.08;
    this.orbit.minDistance    = 3;
    this.orbit.maxDistance    = 300;
    this.orbit.maxPolarAngle  = Math.PI / 2 - 0.02;
    this.orbit.target.set(0, 0, 0);

    /* TransformControls */
    this.transform = new TransformControls(this.camera, this.renderer.domElement);
    this.transform.setSize(0.85);
    this.scene.add(this.transform);

    /* Disable orbit while dragging gizmo; commit on release */
    this.transform.addEventListener('dragging-changed', (e) => {
      this.orbit.enabled   = !e.value;
      this._isTransforming = e.value;
      if (!e.value && this.selectedId) this._commitTransform();
    });

    /* Snap during translate drag */
    this.transform.addEventListener('objectChange', () => {
      if (!this.snapToGrid || this.mode !== 'translate') return;
      const grp = this.zoneObjects.get(this.selectedId);
      if (!grp) return;
      const s = this.snapSize;
      grp.position.x = Math.round(grp.position.x / s) * s;
      grp.position.z = Math.round(grp.position.z / s) * s;
    });

    /* Click detection (pointer up after tiny move = click) */
    this.renderer.domElement.addEventListener('pointerdown', (e) => {
      this._clickStart = { x: e.clientX, y: e.clientY };
    });
    this.renderer.domElement.addEventListener('pointerup', (e) => {
      if (!this._clickStart) return;
      const dx = e.clientX - this._clickStart.x;
      const dy = e.clientY - this._clickStart.y;
      if (Math.sqrt(dx * dx + dy * dy) < 5 && !this._isTransforming) {
        this._handleClick(e);
      }
      this._clickStart = null;
    });

    /* Resize observer */
    this._resizeObs = new ResizeObserver(() => this._onResize());
    this._resizeObs.observe(this.container);

    this._animate();
    console.log('[Canvas3D] Initialized — OrbitControls + TransformControls ready');
  }

  /* ══════════════════════════════════════════════════════
     SCENE SETUP
  ══════════════════════════════════════════════════════ */
  _setupLighting() {
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));

    const sun = new THREE.DirectionalLight(0xfff5e4, 1.3);
    sun.position.set(50, 70, 40);
    sun.castShadow = true;
    Object.assign(sun.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, near: 0.1, far: 300 });
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.001;
    this.scene.add(sun);

    const fill = new THREE.DirectionalLight(0x99ccff, 0.35);
    fill.position.set(-40, 20, -30);
    this.scene.add(fill);

    this.scene.add(new THREE.HemisphereLight(0x334466, 0x111111, 0.5));
  }

  _setupGrid() {
    if (this.gridHelper) {
      this.scene.remove(this.gridHelper);
      this.gridHelper.dispose();
    }
    this.gridHelper = new THREE.GridHelper(200, 100, 0x3a3a3a, 0x222222);
    this.gridHelper.position.y = 0.002;
    this.gridHelper.visible = this.showGrid;
    this.scene.add(this.gridHelper);
  }

  _addGround() {
    const geo = new THREE.PlaneGeometry(400, 400);
    const mat = new THREE.MeshStandardMaterial({ color: 0x161616, roughness: 0.95, metalness: 0.0 });
    const ground = new THREE.Mesh(geo, mat);
    ground.rotation.x  = -Math.PI / 2;
    ground.receiveShadow = true;
    ground.userData.isGround = true;
    this.scene.add(ground);
  }

  toggleGrid() {
    this.showGrid = !this.showGrid;
    if (this.gridHelper) this.gridHelper.visible = this.showGrid;
  }

  /* ══════════════════════════════════════════════════════
     ZONE RENDERING
  ══════════════════════════════════════════════════════ */

  /** Full refresh — backward-compatible public method */
  renderZones(zones) {
    this.zones = zones || [];

    // Clear existing meshes
    this.zoneObjects.forEach((grp) => this._disposeGroup(grp));
    this.zoneObjects.clear();
    this.transform.detach();
    this.selectedId = null;

    if (!this.zones.length) return;
    this.zones.forEach((z) => this._buildMesh(z));
    this.fitCamera();
    console.log(`[Canvas3D] Rendered ${this.zones.length} zones`);
  }

  /** Incremental add */
  addRoom(zone) {
    if (this.zoneObjects.has(zone.id)) { this.updateRoom(zone); return; }
    this._buildMesh(zone);
    this.zones = [...this.zones.filter((z) => z.id !== zone.id), zone];
  }

  /** Incremental remove */
  removeRoom(id) {
    const grp = this.zoneObjects.get(id);
    if (grp) { this._disposeGroup(grp); this.zoneObjects.delete(id); }
    this.zones = this.zones.filter((z) => z.id !== id);
    if (this.selectedId === id) { this.transform.detach(); this.selectedId = null; }
  }

  /** Incremental update (e.g. inspector edits) */
  updateRoom(zone) {
    const wasSelected = this.selectedId === zone.id;
    this.removeRoom(zone.id);
    this._buildMesh(zone);
    this.zones = this.zones.map((z) => (z.id === zone.id ? zone : z));
    if (!this.zones.find((z) => z.id === zone.id)) this.zones.push(zone);
    if (wasSelected) this.selectZone(zone.id);
  }

  _buildMesh(zone) {
    const color = getColorThree(zone.room_type);
    const w = Math.max(0.5, zone.width  || 4);
    const h = Math.max(0.5, zone.height || 3);
    const d = Math.max(0.5, zone.depth  || 4);

    /* Centre position:
       Three.x = zone.x + w/2
       Three.y = h/2 + (zone.z || 0)
       Three.z = zone.y + d/2           */
    const px = (zone.x || 0) + w / 2;
    const py = h / 2 + (zone.z || 0);
    const pz = (zone.y || 0) + d / 2;

    /* Main box — unit 1×1×1 scaled to real dimensions */
    const boxGeo = new THREE.BoxGeometry(1, 1, 1);
    const boxMat = new THREE.MeshStandardMaterial({
      color, roughness: 0.65, metalness: 0.15,
      transparent: true, opacity: 0.90,
    });
    const mesh = new THREE.Mesh(boxGeo, boxMat);
    mesh.scale.set(w, h, d);
    mesh.castShadow    = true;
    mesh.receiveShadow = true;
    mesh.userData.zoneId  = zone.id;
    mesh.userData.isRoom  = true;

    /* Wireframe edges */
    const edgeGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1));
    const edgeMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.20 });
    const edges   = new THREE.LineSegments(edgeGeo, edgeMat);
    edges.scale.set(w, h, d);
    edges.userData.isOutline = true;

    /* Label sprite */
    const label = this._makeSprite(zone.label || zone.room_type, color, w, h);

    /* Group — this is the object TransformControls attaches to */
    const grp = new THREE.Group();
    grp.position.set(px, py, pz);
    grp.userData.zoneId = zone.id;
    if (zone.rotation) grp.rotation.y = (zone.rotation * Math.PI) / 180;

    grp.add(mesh, edges, label);
    this.scene.add(grp);
    this.zoneObjects.set(zone.id, grp);
  }

  _makeSprite(text, hexColor, roomW, roomH) {
    const c   = document.createElement('canvas');
    c.width   = 256; c.height = 64;
    const ctx = c.getContext('2d');

    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.beginPath();
    ctx.roundRect(4, 8, 248, 48, 8);
    ctx.fill();

    ctx.fillStyle = `#${hexColor.toString(16).padStart(6, '0')}`;
    ctx.beginPath();
    ctx.arc(22, 32, 7, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#ffffff';
    ctx.font      = 'Bold 20px Arial';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(text.substring(0, 15), 36, 32);

    const tex = new THREE.CanvasTexture(c);
    const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false });
    const spr = new THREE.Sprite(mat);

    // Position at top of box (box is unit 1 centred at origin inside group)
    // half-height of unit box = 0.5, add small clearance
    const sprH = 0.8;
    const sprW = sprH * (256 / 64);
    spr.scale.set(sprW, sprH, 1);
    spr.position.set(0, 0.5 + sprH * 0.5 + 0.1, 0);
    return spr;
  }

  _disposeGroup(grp) {
    this.scene.remove(grp);
    grp.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
        else child.material.dispose();
      }
    });
  }

  /* ══════════════════════════════════════════════════════
     SELECTION
  ══════════════════════════════════════════════════════ */
  _handleClick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this._mouse.x =  ((event.clientX - rect.left) / rect.width)  * 2 - 1;
    this._mouse.y = -((event.clientY - rect.top)  / rect.height) * 2 + 1;
    this._raycaster.setFromCamera(this._mouse, this.camera);

    const meshes = [];
    this.zoneObjects.forEach((grp) =>
      grp.children.forEach((c) => { if (c.isMesh && c.userData.isRoom) meshes.push(c); })
    );

    const hits = this._raycaster.intersectObjects(meshes, false);
    if (hits.length > 0) {
      const id = hits[0].object.userData.zoneId;
      this.selectZone(id);
      if (this.onZoneSelect) this.onZoneSelect(id);
    } else {
      this.deselectZone();
      if (this.onZoneSelect) this.onZoneSelect(null);
    }
  }

  selectZone(zoneId) {
    this.deselectZone();
    const grp = this.zoneObjects.get(zoneId);
    if (!grp) return;
    this.selectedId = zoneId;

    grp.children.forEach((child) => {
      if (child.isMesh && child.userData.isRoom) {
        child.userData.origColor = child.material.color.getHex();
        child.material = child.material.clone();
        child.material.emissive.setHex(0xd6a85a);
        child.material.emissiveIntensity = 0.38;
      }
      if (child.isLineSegments) {
        child.material = child.material.clone();
        child.material.color.setHex(0xd6a85a);
        child.material.opacity = 0.9;
      }
    });

    // Attach gizmo unless in pure-select mode
    if (this.mode !== 'select') this.transform.attach(grp);
  }

  deselectZone() {
    if (!this.selectedId) return;
    const grp = this.zoneObjects.get(this.selectedId);
    if (grp) {
      grp.children.forEach((child) => {
        if (child.isMesh && child.userData.isRoom && child.userData.origColor !== undefined) {
          child.material.emissive.setHex(0x000000);
          child.material.emissiveIntensity = 0;
        }
        if (child.isLineSegments) {
          child.material.color.setHex(0xffffff);
          child.material.opacity = 0.20;
        }
      });
    }
    this.transform.detach();
    this.selectedId = null;
  }

  /* ══════════════════════════════════════════════════════
     TRANSFORM CONTROLS
  ══════════════════════════════════════════════════════ */
  setMode(mode) {
    this.mode = mode;
    if (mode === 'select') {
      this.transform.detach();
    } else {
      this.transform.setMode(mode); // 'translate' | 'rotate' | 'scale'
      if (this.selectedId) {
        const grp = this.zoneObjects.get(this.selectedId);
        if (grp) this.transform.attach(grp);
      }
    }
  }

  setSnapToGrid(snap) {
    this.snapToGrid = snap;
    this.transform.setTranslationSnap(snap ? this.snapSize : null);
    this.transform.setRotationSnap(snap ? THREE.MathUtils.degToRad(15) : null);
    this.transform.setScaleSnap(snap ? 0.25 : null);
  }

  /** Read back mesh state → call onRoomTransformed with updated zone fields */
  _commitTransform() {
    if (!this.selectedId) return;
    const grp = this.zoneObjects.get(this.selectedId);
    if (!grp) return;

    // Find main mesh to read its scale (which represents dimensions)
    const mesh = grp.children.find((c) => c.isMesh && c.userData.isRoom);
    if (!mesh) return;

    /* Effective scale = group.scale × mesh.scale (TransformControls may scale the group) */
    const effW = Math.abs(grp.scale.x * mesh.scale.x);
    const effH = Math.abs(grp.scale.y * mesh.scale.y);
    const effD = Math.abs(grp.scale.z * mesh.scale.z);

    /* Reverse centre → corner:
       zone.x = grp.position.x - effW/2
       zone.y = grp.position.z - effD/2
       zone.z = grp.position.y - effH/2   */
    const updated = {
      id:       this.selectedId,
      x:        +(grp.position.x - effW / 2).toFixed(3),
      y:        +(grp.position.z - effD / 2).toFixed(3),
      z:        +(grp.position.y - effH / 2).toFixed(3),
      width:    +effW.toFixed(3),
      height:   +effH.toFixed(3),
      depth:    +effD.toFixed(3),
      rotation: +(grp.rotation.y * 180 / Math.PI).toFixed(1),
    };

    if (this.onRoomTransformed) this.onRoomTransformed(updated);
  }

  /* ══════════════════════════════════════════════════════
     CAMERA
  ══════════════════════════════════════════════════════ */
  fitCamera() {
    if (!this.zoneObjects.size) return;
    const box = new THREE.Box3();
    this.zoneObjects.forEach((grp) => box.expandByObject(grp));
    if (box.isEmpty()) return;

    const center = box.getCenter(new THREE.Vector3());
    const size   = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov    = this.camera.fov * (Math.PI / 180);
    const dist   = Math.max((maxDim / 2) / Math.tan(fov / 2) * 1.7, 15);

    this.camera.position.set(center.x + dist * 0.5, center.y + dist * 0.55, center.z + dist * 0.8);
    this.orbit.target.copy(center);
    this.orbit.update();
  }

  resetCamera() {
    this.camera.position.set(25, 22, 28);
    this.orbit.target.set(0, 0, 0);
    this.orbit.update();
    this.deselectZone();
  }

  /* ══════════════════════════════════════════════════════
     RENDER LOOP + RESIZE
  ══════════════════════════════════════════════════════ */
  _animate() {
    this._animId = requestAnimationFrame(() => this._animate());
    this.orbit.update();
    this.renderer.render(this.scene, this.camera);
  }

  _onResize() {
    if (!this.container || !this.renderer) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  dispose() {
    if (this._animId) cancelAnimationFrame(this._animId);
    if (this._resizeObs) this._resizeObs.disconnect();
    this.transform.dispose();
    this.orbit.dispose();
    this.zoneObjects.forEach((grp) => this._disposeGroup(grp));
    this.zoneObjects.clear();
    this.renderer.dispose();
    if (this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
  }
}

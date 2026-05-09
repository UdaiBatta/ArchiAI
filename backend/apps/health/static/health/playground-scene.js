(() => {
  const THREE_SRC = 'https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.min.js';
  const CONTROLS_SRC = 'https://cdn.jsdelivr.net/npm/three@0.164.1/examples/js/controls/OrbitControls.js';

  const host = document.getElementById('studio-layout-canvas');
  const emptyState = document.getElementById('studio-layout-empty');
  const frameButton = document.getElementById('scene-frame');
  const topButton = document.getElementById('scene-top');
  const orbitButton = document.getElementById('scene-orbit');

  if (!host || !emptyState) {
    return;
  }

  let state = {
    zones: [],
    selectedZoneId: '',
    selectedFloor: '',
  };

  let THREE = window.THREE;
  let renderer = null;
  let scene = null;
  let camera = null;
  let controls = null;
  let raycaster = null;
  let pointer = null;
  let contentGroup = null;
  let environmentGroup = null;
  let zoneEntries = [];
  let renderKey = '';
  let animationFrameId = 0;

  const palette = {
    living_room: '#5fd1ff',
    bedroom: '#6ee7b7',
    kitchen: '#f9b04c',
    dining_room: '#a78bfa',
    dining: '#a78bfa',
    bath: '#7dd3fc',
    bathroom: '#7dd3fc',
    toilet: '#7dd3fc',
    stair: '#ff5d8f',
    staircase: '#ff5d8f',
    corridor: '#94a3b8',
    lobby: '#f0f4ff',
    parking: '#7cf7d4',
    office: '#fb7185',
    multi_use: '#8b95b8',
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[src="' + src + '"]');
      if (existing) {
        existing.addEventListener('load', resolve, { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Could not load ' + src));
      document.head.appendChild(script);
    });
  }

  function colorFor(roomType) {
    return palette[String(roomType || '').toLowerCase()] || '#8b95b8';
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function zoneLabel(zone) {
    const title = String(zone.room_type || 'space').replace(/_/g, ' ');
    return title.charAt(0).toUpperCase() + title.slice(1);
  }

  function zoneHeight(zone) {
    const baseArea = Number(zone.area_sqm || zone.target_area_sqm || (Number(zone.width_m || 0) * Number(zone.depth_m || 0)) || 0);
    return clamp(Math.sqrt(Math.max(baseArea, 12)) * 0.95, 4.2, 14);
  }

  function zoneKey(zone) {
    return [zone.id, zone.floor, zone.x, zone.y, zone.width_m, zone.depth_m, zone.room_type, zone.area_sqm].join(':');
  }

  function layoutKey(zones) {
    return zones.map(zoneKey).join('|');
  }

  function computeBounds(zones) {
    if (!zones.length) {
      return {
        minX: -12,
        maxX: 12,
        minZ: -12,
        maxZ: 12,
        minY: 0,
        maxY: 16,
        centerX: 0,
        centerY: 8,
        centerZ: 0,
        width: 24,
        depth: 24,
        height: 16,
      };
    }

    let minX = Infinity;
    let minZ = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxZ = -Infinity;
    let maxY = -Infinity;

    zones.forEach(zone => {
      const width = Number(zone.width_m || 0);
      const depth = Number(zone.depth_m || 0);
      const floorOffset = Number(zone.floor || 0) * 8.0;
      const height = zoneHeight(zone);

      minX = Math.min(minX, Number(zone.x || 0));
      minZ = Math.min(minZ, Number(zone.y || 0));
      minY = Math.min(minY, floorOffset);
      maxX = Math.max(maxX, Number(zone.x || 0) + width);
      maxZ = Math.max(maxZ, Number(zone.y || 0) + depth);
      maxY = Math.max(maxY, floorOffset + height);
    });

    const padX = Math.max(12, (maxX - minX) * 0.18);
    const padZ = Math.max(12, (maxZ - minZ) * 0.18);
    const padY = Math.max(8, (maxY - minY) * 0.12);

    minX -= padX;
    maxX += padX;
    minZ -= padZ;
    maxZ += padZ;
    minY -= padY;
    maxY += padY;

    return {
      minX,
      maxX,
      minZ,
      maxZ,
      minY,
      maxY,
      centerX: (minX + maxX) / 2,
      centerY: (minY + maxY) / 2,
      centerZ: (minZ + maxZ) / 2,
      width: maxX - minX,
      depth: maxZ - minZ,
      height: maxY - minY,
    };
  }

  function createLabelSprite(zone, accent) {
    const width = 512;
    const height = 192;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    if (!ctx) {
      return null;
    }

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(6, 11, 24, 0.72)';
    ctx.strokeStyle = accent;
    ctx.lineWidth = 4;
    roundRect(ctx, 8, 8, width - 16, height - 16, 28, true, true);

    ctx.fillStyle = '#f5f7ff';
    ctx.font = '700 36px Inter, system-ui, sans-serif';
    ctx.fillText(zoneLabel(zone), 36, 72);

    ctx.fillStyle = 'rgba(235, 241, 255, 0.78)';
    ctx.font = '500 24px Inter, system-ui, sans-serif';
    ctx.fillText(Number(zone.width_m || 0).toFixed(1) + 'm × ' + Number(zone.depth_m || 0).toFixed(1) + 'm', 36, 118);

    ctx.fillStyle = accent;
    ctx.font = '600 20px Inter, system-ui, sans-serif';
    ctx.fillText('Floor ' + Number(zone.floor || 0), 36, 154);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace || texture.colorSpace;
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(16, 6, 1);
    sprite.userData.disposeTexture = texture;
    return sprite;
  }

  function roundRect(ctx, x, y, w, h, r, fill, stroke) {
    const radius = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
  }

  function disposeObject(object3D) {
    object3D.traverse(node => {
      if (node.geometry) {
        node.geometry.dispose();
      }
      if (node.material) {
        if (Array.isArray(node.material)) {
          node.material.forEach(material => material.dispose && material.dispose());
        } else if (node.material.dispose) {
          node.material.dispose();
        }
      }
      if (node.userData && node.userData.disposeTexture) {
        node.userData.disposeTexture.dispose();
      }
    });
  }

  function buildEnvironment(bounds) {
    if (!environmentGroup) {
      environmentGroup = new THREE.Group();
      scene.add(environmentGroup);
    }

    while (environmentGroup.children.length) {
      const child = environmentGroup.children.pop();
      disposeObject(child);
      environmentGroup.remove(child);
    }

    const gridPrimary = new THREE.GridHelper(Math.max(bounds.width, bounds.depth) + 60, 60, 0x4fd4ff, 0x20304d);
    gridPrimary.material.transparent = true;
    gridPrimary.material.opacity = 0.26;
    environmentGroup.add(gridPrimary);

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(Math.max(bounds.width, bounds.depth) + 180, Math.max(bounds.width, bounds.depth) + 180),
      new THREE.MeshStandardMaterial({ color: 0x07111d, roughness: 1, metalness: 0, transparent: true, opacity: 0.98 })
    );
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = -0.08;
    environmentGroup.add(plane);

    const axisHelper = new THREE.AxesHelper(18);
    axisHelper.position.set(bounds.centerX, 0.25, bounds.centerZ);
    environmentGroup.add(axisHelper);
  }

  function clearContent() {
    if (!contentGroup) return;
    while (contentGroup.children.length) {
      const child = contentGroup.children.pop();
      disposeObject(child);
      contentGroup.remove(child);
    }
    zoneEntries = [];
  }

  function buildScene() {
    if (!scene || !contentGroup) {
      return;
    }

    clearContent();

    const zones = Array.isArray(state.zones) ? state.zones : [];
    emptyState.hidden = zones.length > 0;

    if (!zones.length) {
      emptyState.textContent = 'Run the pipeline to generate a Hypar-ready concept. The workspace will appear here.';
      frameView();
      return;
    }

    const bounds = computeBounds(zones);
    buildEnvironment(bounds);

    const selectedFloor = String(state.selectedFloor || '');
    zones.forEach(zone => {
      const floor = Number(zone.floor || 0);
      const accent = colorFor(zone.room_type);
      const localX = Number(zone.x || 0) - bounds.centerX;
      const localZ = Number(zone.y || 0) - bounds.centerZ;
      const width = Math.max(0.2, Number(zone.width_m || 0));
      const depth = Math.max(0.2, Number(zone.depth_m || 0));
      const height = zoneHeight(zone);
      const floorOffsetY = floor * 8.0;
      const highlight = String(zone.id) === String(state.selectedZoneId);
      const selectedFloorMatch = !selectedFloor || String(floor) === selectedFloor;

      const group = new THREE.Group();
      group.userData.zoneId = String(zone.id);
      group.userData.zone = zone;

      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(accent),
        roughness: 0.32,
        metalness: 0.08,
        transparent: true,
        opacity: selectedFloorMatch ? (highlight ? 0.95 : 0.78) : 0.22,
        emissive: new THREE.Color(accent),
        emissiveIntensity: highlight ? 0.32 : 0.12,
      });

      const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
      mesh.position.set(localX, floorOffsetY + height / 2, localZ);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.zoneId = String(zone.id);
      mesh.userData.zone = zone;

      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(mesh.geometry),
        new THREE.LineBasicMaterial({
          color: highlight ? 0xffffff : 0xc6d1ff,
          transparent: true,
          opacity: highlight ? 0.95 : (selectedFloorMatch ? 0.28 : 0.08),
        })
      );
      outline.position.copy(mesh.position);
      outline.userData.zoneId = String(zone.id);

      const label = createLabelSprite(zone, accent);
      if (label) {
        label.position.set(localX, floorOffsetY + height + 3.2, localZ);
      }

      const pad = 1.05;
      const floorPlate = new THREE.Mesh(
        new THREE.BoxGeometry(width * pad, 0.18, depth * pad),
        new THREE.MeshStandardMaterial({
          color: new THREE.Color(accent),
          transparent: true,
          opacity: selectedFloorMatch ? 0.12 : 0.05,
          roughness: 1,
          metalness: 0,
        })
      );
      floorPlate.position.set(localX, floorOffsetY - 0.1, localZ);

      group.add(floorPlate);
      group.add(mesh);
      group.add(outline);
      if (label) group.add(label);
      contentGroup.add(group);

      zoneEntries.push({
        zoneId: String(zone.id),
        zone,
        group,
        mesh,
        outline,
        label,
      });
    });

    updateSelectionStyles();
    if (!renderKey) {
      frameView();
    }
    emptyState.hidden = true;
  }

  function updateSelectionStyles() {
    const selectedZoneId = String(state.selectedZoneId || '');
    const selectedFloor = String(state.selectedFloor || '');

    zoneEntries.forEach(entry => {
      const zone = entry.zone;
      const isActive = String(zone.id) === selectedZoneId;
      const floorMatch = !selectedFloor || String(zone.floor) === selectedFloor;
      const baseOpacity = floorMatch ? 0.78 : 0.22;

      entry.mesh.material.opacity = isActive ? 0.98 : baseOpacity;
      entry.mesh.material.emissiveIntensity = isActive ? 0.36 : 0.12;
      entry.outline.material.opacity = isActive ? 0.95 : (floorMatch ? 0.28 : 0.08);

      if (entry.label) {
        entry.label.scale.set(isActive ? 18 : 16, isActive ? 6.8 : 6, 1);
      }
    });
  }

  function fitCamera(mode = 'orbit') {
    if (!camera || !controls || !scene) return;

    const boundsBox = new THREE.Box3().setFromObject(contentGroup);
    if (!boundsBox.isEmpty()) {
      const size = boundsBox.getSize(new THREE.Vector3());
      const center = boundsBox.getCenter(new THREE.Vector3());
      const maxSize = Math.max(size.x, size.y, size.z);
      const distance = maxSize / Math.tan((camera.fov * Math.PI) / 360) * 0.62;

      if (mode === 'top') {
        camera.position.set(center.x + 0.01, center.y + Math.max(size.y, 24) * 1.9, center.z + 0.01);
        controls.target.copy(center);
        camera.lookAt(center);
      } else {
        camera.position.set(center.x + distance * 0.78, center.y + distance * 0.48, center.z + distance * 0.96);
        controls.target.copy(center);
      }
    } else {
      const defaultCenter = new THREE.Vector3(0, 0, 0);
      controls.target.copy(defaultCenter);
      camera.position.set(64, 52, 64);
      camera.lookAt(defaultCenter);
    }

    controls.update();
  }

  function frameView() {
    fitCamera('orbit');
  }

  function topView() {
    fitCamera('top');
  }

  function orbitView() {
    fitCamera('orbit');
  }

  function resizeViewport() {
    if (!renderer || !camera) return;
    const rect = host.getBoundingClientRect();
    const width = Math.max(320, rect.width || 320);
    const height = Math.max(320, rect.height || 320);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderOnce();
  }

  function renderOnce() {
    if (!renderer || !scene || !camera) return;
    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  function animate() {
    if (!renderer || !scene || !camera) return;
    animationFrameId = window.requestAnimationFrame(animate);
    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  function resolveZoneId(object3D) {
    let current = object3D;
    while (current) {
      if (current.userData && current.userData.zoneId) {
        return String(current.userData.zoneId);
      }
      current = current.parent;
    }
    return '';
  }

  function setCursorForPointer(event) {
    if (!raycaster || !pointer || !camera) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(zoneEntries.map(entry => entry.mesh), false);
    renderer.domElement.style.cursor = hits.length ? 'pointer' : 'grab';
  }

  function selectZone(zoneId) {
    if (!zoneId) return;
    state.selectedZoneId = String(zoneId);
    updateSelectionStyles();
    window.dispatchEvent(new CustomEvent('archi3d-zone-selected', { detail: { zoneId: String(zoneId) } }));
    renderOnce();
  }

  function onPointerDown(event) {
    if (!raycaster || !pointer || !camera) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(zoneEntries.map(entry => entry.mesh), false);
    if (hits.length) {
      const zoneId = resolveZoneId(hits[0].object);
      if (zoneId) {
        selectZone(zoneId);
      }
    }
  }

  async function bootstrap() {
    try {
      if (!THREE) {
        await loadScript(THREE_SRC);
        THREE = window.THREE;
      }
      if (!THREE.OrbitControls) {
        await loadScript(CONTROLS_SRC);
      }
      initScene();
    } catch (error) {
      initFallbackScene(error);
    }
  }

  function initScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07111d);
    scene.fog = new THREE.Fog(0x07111d, 120, 360);

    camera = new THREE.PerspectiveCamera(38, 1, 0.1, 1200);
    camera.position.set(68, 54, 68);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x07111d, 0);
    renderer.shadowMap.enabled = true;
    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.inset = '0';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';

    host.innerHTML = '';
    host.appendChild(renderer.domElement);
    host.classList.add('is-loading');

    contentGroup = new THREE.Group();
    scene.add(contentGroup);

    const ambient = new THREE.HemisphereLight(0x8be9ff, 0x101623, 1.35);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.8);
    keyLight.position.set(80, 140, 60);
    keyLight.castShadow = true;
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x43f5d0, 0.55);
    rimLight.position.set(-90, 70, -100);
    scene.add(rimLight);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 18;
    controls.maxDistance = 360;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.target.set(0, 0, 0);

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    renderer.domElement.addEventListener('pointermove', setCursorForPointer);
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointerleave', () => {
      renderer.domElement.style.cursor = 'grab';
    });

    if (frameButton) frameButton.addEventListener('click', frameView);
    if (topButton) topButton.addEventListener('click', topView);
    if (orbitButton) orbitButton.addEventListener('click', orbitView);

    window.addEventListener('resize', resizeViewport);
    window.Archi3DStudioScene = {
      update(payload) {
        const nextZones = Array.isArray(payload && payload.zones) ? payload.zones : [];
        const nextSelectedZoneId = String(payload && payload.selectedZoneId ? payload.selectedZoneId : '');
        const nextSelectedFloor = String(payload && payload.selectedFloor ? payload.selectedFloor : '');
        const nextKey = layoutKey(nextZones);

        state = {
          zones: nextZones,
          selectedZoneId: nextSelectedZoneId,
          selectedFloor: nextSelectedFloor,
        };

        if (nextKey !== renderKey) {
          renderKey = nextKey;
          buildScene();
          resizeViewport();
        } else {
          updateSelectionStyles();
          emptyState.hidden = nextZones.length > 0;
          renderOnce();
        }
      },
      frame: frameView,
      top: topView,
      orbit: orbitView,
      resize: resizeViewport,
    };

    buildScene();
    resizeViewport();
    host.classList.remove('is-loading');
    window.dispatchEvent(new Event('archi3d-scene-ready'));
    animate();
  }

  function initFallbackScene(loadError) {
    let yaw = -34;
    let pitch = 68;
    let zoom = 1;
    let dragState = null;
    let viewport = null;
    let world = null;
    let content = null;
    let fallbackKey = '';

    host.innerHTML = '';
    host.classList.add('studio-css3d-stage');

    viewport = document.createElement('div');
    viewport.className = 'studio-css3d-viewport';
    world = document.createElement('div');
    world.className = 'studio-css3d-world';
    content = document.createElement('div');
    content.className = 'studio-css3d-content';
    world.appendChild(content);
    viewport.appendChild(world);
    host.appendChild(viewport);

    const failureNote = document.createElement('div');
    failureNote.className = 'studio-css3d-failure';
    failureNote.textContent = loadError ? 'Using local CSS 3D fallback because the WebGL library did not load.' : 'Local CSS 3D fallback active.';
    host.appendChild(failureNote);

    function applyTransform() {
      world.style.transform = 'translate(-50%, -58%) rotateX(' + pitch + 'deg) rotateY(' + yaw + 'deg) scale(' + zoom + ')';
    }

    function computeSceneScale(bounds) {
      const rect = host.getBoundingClientRect();
      const usableWidth = Math.max(300, rect.width * 0.78);
      const usableHeight = Math.max(300, rect.height * 0.72);
      const fitX = usableWidth / Math.max(bounds.width, 1);
      const fitZ = usableHeight / Math.max(bounds.depth, 1);
      return clamp(Math.min(fitX, fitZ), 12, 22);
    }

    function clearFallbackContent() {
      while (content.children.length) {
        content.removeChild(content.children[0]);
      }
    }

    function renderFallback() {
      const zones = Array.isArray(state.zones) ? state.zones : [];
      const bounds = computeBounds(zones);
      const scale = computeSceneScale(bounds);

      world.style.width = Math.max(bounds.width * scale, 300) + 'px';
      world.style.height = Math.max(bounds.depth * scale, 300) + 'px';
      world.style.marginLeft = '0px';
      world.style.marginTop = '0px';

      clearFallbackContent();
      emptyState.hidden = zones.length > 0;

      const grid = document.createElement('div');
      grid.className = 'studio-css3d-grid';
      grid.style.width = '100%';
      grid.style.height = '100%';
      grid.style.backgroundSize = Math.max(22, scale) + 'px ' + Math.max(22, scale) + 'px';
      content.appendChild(grid);

      const floorPlanes = new Set();
      zones.forEach(zone => floorPlanes.add(Number(zone.floor || 0)));
      Array.from(floorPlanes).sort((a, b) => a - b).forEach(floor => {
        const floorPlane = document.createElement('div');
        floorPlane.className = 'studio-css3d-floor';
        floorPlane.style.left = '0px';
        floorPlane.style.top = '0px';
        floorPlane.style.width = bounds.width * scale + 'px';
        floorPlane.style.height = bounds.depth * scale + 'px';
        floorPlane.style.setProperty('--floor-elevation', String(floor * scale * 8 + 8));
        floorPlane.style.setProperty('--floor-accent', floor % 2 === 0 ? 'rgba(94, 245, 208, 0.08)' : 'rgba(56, 189, 248, 0.08)');
        floorPlane.style.transform = 'translate3d(0px, ' + (floor * 8 * scale) + 'px, 0px)';
        content.appendChild(floorPlane);
      });

      zones.forEach(zone => {
        const floor = Number(zone.floor || 0);
        const zoneWidth = Math.max(0.2, Number(zone.width_m || 0)) * scale;
        const zoneDepth = Math.max(0.2, Number(zone.depth_m || 0)) * scale;
        const height = zoneHeight(zone) * scale * 0.28;
        const accent = colorFor(zone.room_type);
        const highlight = String(zone.id) === String(state.selectedZoneId);
        const floorMatch = !state.selectedFloor || String(zone.floor) === String(state.selectedFloor);
        const zoneEl = document.createElement('button');
        zoneEl.type = 'button';
        zoneEl.className = 'studio-css3d-zone' + (highlight ? ' is-selected' : '') + (floorMatch ? ' is-visible' : ' is-faded');
        zoneEl.style.left = ((Number(zone.x || 0) - bounds.minX) * scale) + 'px';
        zoneEl.style.top = ((Number(zone.y || 0) - bounds.minZ) * scale) + 'px';
        zoneEl.style.width = zoneWidth + 'px';
        zoneEl.style.height = zoneDepth + 'px';
        zoneEl.style.setProperty('--zone-height', height + 'px');
        zoneEl.style.setProperty('--zone-accent', accent);
        zoneEl.style.setProperty('--zone-opacity', floorMatch ? (highlight ? '0.98' : '0.78') : '0.22');
        zoneEl.style.transform = 'translate3d(0px, ' + (floor * 8 * scale) + 'px, 0px)';
        zoneEl.dataset.zoneId = String(zone.id);

        zoneEl.innerHTML = [
          '<span class="studio-css3d-zone__shadow"></span>',
          '<span class="studio-css3d-zone__side"></span>',
          '<span class="studio-css3d-zone__top"></span>',
          '<span class="studio-css3d-zone__label"><strong>' + zoneLabel(zone) + '</strong><span>' + Number(zone.width_m || 0).toFixed(1) + 'm × ' + Number(zone.depth_m || 0).toFixed(1) + 'm</span></span>',
        ].join('');

        zoneEl.addEventListener('click', () => selectZone(String(zone.id)));
        content.appendChild(zoneEl);
      });

      fallbackKey = layoutKey(zones);
      emptyState.hidden = zones.length > 0;
      if (!zones.length) {
        emptyState.textContent = 'Run the pipeline to generate a Hypar-ready concept. The workspace will appear here.';
      }
      applyTransform();
    }

    function updateFallbackSelectionStyles() {
      const selectedZoneId = String(state.selectedZoneId || '');
      const selectedFloor = String(state.selectedFloor || '');
      content.querySelectorAll('.studio-css3d-zone').forEach(node => {
        const zoneId = String(node.dataset.zoneId || '');
        const zone = state.zones.find(item => String(item.id) === zoneId);
        if (!zone) return;
        const isSelected = zoneId === selectedZoneId;
        const visibleFloor = !selectedFloor || String(zone.floor) === selectedFloor;
        node.classList.toggle('is-selected', isSelected);
        node.classList.toggle('is-visible', visibleFloor);
        node.classList.toggle('is-faded', !visibleFloor);
        node.style.setProperty('--zone-opacity', visibleFloor ? (isSelected ? '0.98' : '0.78') : '0.22');
      });
    }

    function frameFallback(mode = 'orbit') {
      const zones = Array.isArray(state.zones) ? state.zones : [];
      const bounds = computeBounds(zones);
      const fit = computeSceneScale(bounds);
      zoom = clamp(fit / 15, 0.75, 1.35);
      if (mode === 'top') {
        pitch = 86;
        yaw = 0;
      } else if (mode === 'orbit') {
        pitch = 68;
        yaw = -34;
      }
      applyTransform();
      updateFallbackSelectionStyles();
    }

    viewport.addEventListener('pointerdown', event => {
      dragState = {
        startX: event.clientX,
        startY: event.clientY,
        startYaw: yaw,
        startPitch: pitch,
      };
      viewport.setPointerCapture(event.pointerId);
      viewport.classList.add('is-dragging');
      event.preventDefault();
    });

    viewport.addEventListener('pointermove', event => {
      if (!dragState) {
        return;
      }
      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;
      yaw = dragState.startYaw + deltaX * 0.15;
      pitch = clamp(dragState.startPitch - deltaY * 0.12, 20, 88);
      applyTransform();
    });

    viewport.addEventListener('pointerup', event => {
      if (dragState && viewport.hasPointerCapture(event.pointerId)) {
        viewport.releasePointerCapture(event.pointerId);
      }
      dragState = null;
      viewport.classList.remove('is-dragging');
    });

    viewport.addEventListener('pointercancel', () => {
      dragState = null;
      viewport.classList.remove('is-dragging');
    });

    viewport.addEventListener('wheel', event => {
      zoom = clamp(zoom - Math.sign(event.deltaY) * 0.05, 0.65, 1.5);
      applyTransform();
      event.preventDefault();
    }, { passive: false });

    if (frameButton) frameButton.addEventListener('click', () => frameFallback('orbit'));
    if (topButton) topButton.addEventListener('click', () => frameFallback('top'));
    if (orbitButton) orbitButton.addEventListener('click', () => frameFallback('orbit'));

    window.Archi3DStudioScene = {
      update(payload) {
        const nextZones = Array.isArray(payload && payload.zones) ? payload.zones : [];
        const nextSelectedZoneId = String(payload && payload.selectedZoneId ? payload.selectedZoneId : '');
        const nextSelectedFloor = String(payload && payload.selectedFloor ? payload.selectedFloor : '');
        const nextKey = layoutKey(nextZones);

        state = {
          zones: nextZones,
          selectedZoneId: nextSelectedZoneId,
          selectedFloor: nextSelectedFloor,
        };

        if (nextKey !== fallbackKey) {
          renderFallback();
          frameFallback('orbit');
          fallbackKey = nextKey;
        } else {
          updateFallbackSelectionStyles();
          emptyState.hidden = nextZones.length > 0;
          applyTransform();
        }
      },
      frame: () => frameFallback('orbit'),
      top: () => frameFallback('top'),
      orbit: () => frameFallback('orbit'),
      resize: () => {
        if (state.zones.length) {
          renderFallback();
        }
      },
    };

    renderFallback();
    frameFallback('orbit');
    host.classList.remove('is-loading');
    window.dispatchEvent(new Event('archi3d-scene-ready'));
  }

  bootstrap();
})();
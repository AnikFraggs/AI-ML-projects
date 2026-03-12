/**
 * renderer3d.js — Three.js 3D trajectory viewport
 *
 * BLACK SCREEN ROOT CAUSE:
 *   results-panel was display:none when init3D() was called.
 *   Three.js read clientWidth=0, created a 0×0 canvas → black.
 *
 * FIX:
 *   init3D() uses a forceMeasure() helper that reads offsetWidth
 *   (triggers a synchronous layout reflow) so we always get real px.
 *   A 300ms setTimeout also ensures paint is fully complete before
 *   creating the WebGLRenderer.
 */

let _renderer = null;
let _animId   = null;
let _orbit    = {
  isDragging: false, lastX: 0, lastY: 0,
  theta: 0.7, phi: 0.85, radius: 12,
  tx: 0, ty: 0, tz: 0
};
let _cleanupFns = [];

// ── Public API ───────────────────────────────────────────────────────────────

function init3D(container, trajectory, colors) {
  // 1. Destroy any previous scene
  _destroy();

  // 2. Make sure container is actually visible
  container.style.display = 'block';

  // 3. Force synchronous layout reflow — reads offsetWidth, discards value.
  //    This makes the browser calculate the real box dimensions NOW.
  void container.offsetWidth;

  // 4. rAF in app.js already waited for paint — no delay needed here.
  //    Use setTimeout(0) only as a safety flush for any remaining microtasks.
  setTimeout(() => _build(container, trajectory, colors), 0);
}

// ── Private ──────────────────────────────────────────────────────────────────

function _destroy() {
  if (_animId) { cancelAnimationFrame(_animId); _animId = null; }
  _cleanupFns.forEach(fn => { try { fn(); } catch (e) {} });
  _cleanupFns = [];
  if (_renderer) {
    _renderer.dispose();
    const el = _renderer.domElement;
    if (el && el.parentNode) el.parentNode.removeChild(el);
    _renderer = null;
  }
}

function _build(container, trajectory, colors) {
  // Read REAL dimensions after layout + paint
  const W = container.offsetWidth  || 700;
  const H = container.offsetHeight || 420;

  if (W < 10) {
    // Still invisible somehow — retry
    setTimeout(() => _build(container, trajectory, colors), 200);
    return;
  }

  // ── WebGL Renderer ───────────────────────────────────────────────────────
  _renderer = new THREE.WebGLRenderer({ antialias: true });
  _renderer.setSize(W, H);
  _renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  _renderer.setClearColor(0x030e1c, 1);
  _renderer.shadowMap.enabled = true;
  container.appendChild(_renderer.domElement);

  const scene  = new THREE.Scene();
  scene.fog    = new THREE.FogExp2(0x030e1c, 0.013);
  const camera = new THREE.PerspectiveCamera(52, W / H, 0.01, 50000);

  // ── Lights ───────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0x223355, 1.5));
  const sun = new THREE.DirectionalLight(0x88aaff, 1.8);
  sun.position.set(15, 25, 10);
  sun.castShadow = true;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0xff6644, 0.5);
  rim.position.set(-10, 5, -5);
  scene.add(rim);

  if (!trajectory || !trajectory.length) {
    _renderer.render(scene, camera);
    return;
  }

  // ── Scene scale ──────────────────────────────────────────────────────────
  const maxX = Math.max(...trajectory.map(p => p.x), 1);
  const maxZ = Math.max(...trajectory.map(p => p.z), 1);
  const span = Math.max(maxX, maxZ, 1);
  const SC   = 10 / span;
  const toV  = p => new THREE.Vector3(p.x * SC, p.z * SC, p.y * SC);

  // ── Ground + grid ────────────────────────────────────────────────────────
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(28, 28),
    new THREE.MeshStandardMaterial({ color: 0x061408, roughness: 0.95 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  scene.add(new THREE.GridHelper(28, 28, 0x0d2e0d, 0x081808));

  // ── Axes ─────────────────────────────────────────────────────────────────
  [
    { dir: new THREE.Vector3(1, 0, 0), col: 0xff3333 },  // X downrange
    { dir: new THREE.Vector3(0, 1, 0), col: 0x33ff88 },  // Y altitude
    { dir: new THREE.Vector3(0, 0, 1), col: 0x3399ff },  // Z lateral
  ].forEach(({ dir, col }) => {
    scene.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), dir.clone().multiplyScalar(11)]),
      new THREE.LineBasicMaterial({ color: col })
    ));
    const tip = new THREE.Mesh(
      new THREE.ConeGeometry(0.18, 0.55, 10),
      new THREE.MeshBasicMaterial({ color: col })
    );
    tip.position.copy(dir.clone().multiplyScalar(11.3));
    tip.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
    scene.add(tip);
  });

  // ── Trajectory tube ──────────────────────────────────────────────────────
  const pts   = trajectory.map(toV);
  const curve = new THREE.CatmullRomCurve3(pts);
  const segs  = Math.min(trajectory.length * 3, 1500);
  const tube  = new THREE.TubeGeometry(curve, segs, 0.065, 8, false);

  const c1 = new THREE.Color(colors[0]);
  const c2 = new THREE.Color(colors[1]);
  const colArr = [];
  for (let i = 0; i < tube.attributes.position.count; i++) {
    const c = new THREE.Color().lerpColors(c1, c2, i / tube.attributes.position.count);
    colArr.push(c.r, c.g, c.b);
  }
  tube.setAttribute('color', new THREE.Float32BufferAttribute(colArr, 3));
  scene.add(new THREE.Mesh(tube, new THREE.MeshPhongMaterial({
    vertexColors: true, shininess: 60, emissive: c1, emissiveIntensity: 0.2
  })));

  // Glow overlay
  scene.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: colors[0], transparent: true, opacity: 0.35 })
  ));

  // Ground shadow
  scene.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(trajectory.map(p => new THREE.Vector3(p.x * SC, 0.003, p.y * SC))),
    new THREE.LineBasicMaterial({ color: 0x002211, transparent: true, opacity: 0.5 })
  ));

  // ── Apogee ───────────────────────────────────────────────────────────────
  const apexPt  = trajectory.reduce((a, b) => b.z > a.z ? b : a);
  const apexPos = toV(apexPt);
  const apexSph = new THREE.Mesh(
    new THREE.SphereGeometry(0.22, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffff00 })
  );
  apexSph.position.copy(apexPos);
  scene.add(apexSph);
  const apexLight = new THREE.PointLight(0xffff44, 1.2, 4);
  apexLight.position.copy(apexPos);
  scene.add(apexLight);

  // ── Launch marker ─────────────────────────────────────────────────────────
  const launch = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 12, 12),
    new THREE.MeshBasicMaterial({ color: colors[0] })
  );
  launch.position.copy(toV(trajectory[0]));
  scene.add(launch);

  // ── Impact marker ─────────────────────────────────────────────────────────
  const impPt  = trajectory[trajectory.length - 1];
  const impPos = new THREE.Vector3(impPt.x * SC, 0, impPt.y * SC);
  const impCone = new THREE.Mesh(
    new THREE.ConeGeometry(0.28, 0.7, 8),
    new THREE.MeshBasicMaterial({ color: 0xff2200 })
  );
  impCone.position.set(impPos.x, 0.35, impPos.z);
  scene.add(impCone);

  // Impact rings
  const rings = [];
  for (let r = 0; r < 3; r++) {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.3 + r * 0.4, 0.5 + r * 0.4, 32),
      new THREE.MeshBasicMaterial({
        color: 0xff3333, side: THREE.DoubleSide,
        transparent: true, opacity: 0.2
      })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(impPos.x, 0.01, impPos.z);
    ring.userData = { phase: r * 2.1 };
    scene.add(ring);
    rings.push(ring);
  }

  // ── Animated dot ─────────────────────────────────────────────────────────
  const dot      = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  const dotLight = new THREE.PointLight(0xffffff, 2.0, 2.5);
  scene.add(dot);
  scene.add(dotLight);

  // ── Camera setup ─────────────────────────────────────────────────────────
  _orbit.tx     = (maxX * SC) / 2;
  _orbit.ty     = (maxZ * SC) * 0.3;
  _orbit.tz     = 0;
  _orbit.radius = Math.max(span * SC * 0.95, 6);
  _orbit.theta  = 0.7;
  _orbit.phi    = 0.85;

  function updateCamera() {
    const { theta, phi, radius, tx, ty, tz } = _orbit;
    camera.position.set(
      tx + radius * Math.sin(phi) * Math.sin(theta),
      ty + radius * Math.cos(phi),
      tz + radius * Math.sin(phi) * Math.cos(theta)
    );
    camera.lookAt(tx, ty, tz);
  }
  updateCamera();

  // ── Render loop ───────────────────────────────────────────────────────────
  let frame = 0;
  function animate() {
    _animId = requestAnimationFrame(animate);
    frame++;

    // Dot animation
    const frac = (frame * 0.007) % 1;
    const raw  = frac * (pts.length - 1);
    const i0   = Math.floor(raw);
    const i1   = Math.min(i0 + 1, pts.length - 1);
    dot.position.lerpVectors(pts[i0], pts[i1], raw - i0);
    dotLight.position.copy(dot.position);

    // Pulse apogee
    const pulse = 1 + 0.22 * Math.sin(frame * 0.07);
    apexSph.scale.setScalar(pulse);
    apexLight.intensity = 1.2 + 0.4 * Math.sin(frame * 0.07);

    // Rings
    rings.forEach(ring => {
      ring.material.opacity = 0.15 + 0.1 * Math.sin(frame * 0.05 + ring.userData.phase);
    });

    updateCamera();
    _renderer.render(scene, camera);
  }
  animate();

  // ── Mouse / touch controls ────────────────────────────────────────────────
  const el = _renderer.domElement;

  const onDown  = e => { _orbit.isDragging = true; _orbit.lastX = e.clientX; _orbit.lastY = e.clientY; };
  const onUp    = ()  => { _orbit.isDragging = false; };
  const onMove  = e  => {
    if (!_orbit.isDragging) return;
    _orbit.theta -= (e.clientX - _orbit.lastX) * 0.007;
    _orbit.phi    = Math.max(0.08, Math.min(Math.PI - 0.08, _orbit.phi + (e.clientY - _orbit.lastY) * 0.007));
    _orbit.lastX  = e.clientX;
    _orbit.lastY  = e.clientY;
  };
  const onWheel = e  => {
    e.preventDefault();
    _orbit.radius = Math.max(0.8, Math.min(400, _orbit.radius * (1 + e.deltaY * 0.001)));
  };

  el.addEventListener('mousedown',  onDown);
  el.addEventListener('wheel',      onWheel, { passive: false });
  window.addEventListener('mouseup',   onUp);
  window.addEventListener('mousemove', onMove);

  // ── Resize ───────────────────────────────────────────────────────────────
  const ro = new ResizeObserver(() => {
    const nw = container.offsetWidth  || 700;
    const nh = container.offsetHeight || 420;
    if (nw > 10 && _renderer) {
      _renderer.setSize(nw, nh);
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
    }
  });
  ro.observe(container);

  // Register cleanups
  _cleanupFns.push(
    () => el.removeEventListener('mousedown',  onDown),
    () => el.removeEventListener('wheel',      onWheel),
    () => window.removeEventListener('mouseup',   onUp),
    () => window.removeEventListener('mousemove', onMove),
    () => ro.disconnect(),
    () => tube.dispose()
  );
}

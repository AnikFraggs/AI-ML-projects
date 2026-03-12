/**
 * app.js — Main application controller
 *
 * KEY FIX for black 3D screen:
 *   results-panel.style.display must be set BEFORE renderCurrentView() runs.
 *   Then 3D init waits 300ms (inside renderer3d.js) so the browser has fully
 *   painted the visible div and offsetWidth returns a real pixel value.
 */

const API_BASE = 'http://localhost:5000';

const WEATHER_PRESETS = [
  { wind_speed: 0,  wind_direction: 0,   temperature: 25,  humidity: 40, pressure: 101325 },
  { wind_speed: 15, wind_direction: 270, temperature: 18,  humidity: 55, pressure: 100800 },
  { wind_speed: 38, wind_direction: 225, temperature: 12,  humidity: 95, pressure: 98500  },
  { wind_speed: 8,  wind_direction: 90,  temperature: 46,  humidity: 8,  pressure: 100200 },
  { wind_speed: 6,  wind_direction: 0,   temperature: -28, humidity: 30, pressure: 102500 },
  { wind_speed: 2,  wind_direction: 180, temperature: 8,   humidity: 99, pressure: 101000 },
  { wind_speed: 22, wind_direction: 315, temperature: 2,   humidity: 18, pressure: 79500  },
  { wind_speed: 28, wind_direction: 45,  temperature: 14,  humidity: 85, pressure: 99000  },
];

const MODE_COLORS = {
  ballistic: ['#ff5533', '#ff0055'],
  sports:    ['#00ccff', '#0044ff'],
  sprinkler: ['#00ff88', '#00aa44'],
  general:   ['#ffcc00', '#ff6600'],
};

let currentMode  = 'sports';
let currentShape = 'sphere';
let currentView  = '3d';
let simResult    = null;

// ── Live air density display ──────────────────────────────────────────────────
function updateLiveStats() {
  const alt  = +document.getElementById('p-alt').value  || 0;
  const temp = +document.getElementById('w-tmp').value  || 15;
  const pres = +document.getElementById('w-prs').value  || 101325;
  const hum  = +document.getElementById('w-hum').value  || 50;
  const vel  = +document.getElementById('p-vel').value  || 30;
  const ws   = +document.getElementById('w-spd').value  || 0;
  const rho  = airDensity(alt, temp, pres, hum);
  const mach = vel / speedOfSound(alt, temp);
  document.getElementById('stat-density').textContent = `DENSITY ${rho.toFixed(4)} kg/m³`;
  document.getElementById('stat-mach').textContent    = `MACH ${mach.toFixed(3)}`;
  document.getElementById('stat-wind').textContent    = `WIND ${ws} m/s`;
  document.getElementById('density-val').textContent  = rho.toFixed(4);
}

// ── Read all form inputs ──────────────────────────────────────────────────────
function getInputs() {
  return {
    params: {
      latitude:  +document.getElementById('p-lat').value,
      longitude: +document.getElementById('p-lon').value,
      altitude:  +document.getElementById('p-alt').value,
      velocity:  +document.getElementById('p-vel').value,
      angle:     +document.getElementById('p-ang').value,
      azimuth:   +document.getElementById('p-az').value,
      mass:      +document.getElementById('p-mass').value,
      area:      +document.getElementById('p-area').value,
      shape:     currentShape,
    },
    weather: {
      wind_speed:     +document.getElementById('w-spd').value,
      wind_direction: +document.getElementById('w-dir').value,
      temperature:    +document.getElementById('w-tmp').value,
      humidity:       +document.getElementById('w-hum').value,
      pressure:       +document.getElementById('w-prs').value,
    },
    export_vtk: document.getElementById('export-vtk').checked,
  };
}

// ── Show results panel ────────────────────────────────────────────────────────
function showResults(data) {
  const aero = data.aerodynamics;
  const res  = data.results;

  // Populate aerodynamics card
  document.getElementById('s-cd').querySelector('.val').textContent     = aero.Cd?.toFixed(5)  || '—';
  document.getElementById('s-cl').querySelector('.val').textContent     = aero.Cl?.toFixed(5)  || '—';
  document.getElementById('s-regime').querySelector('.val').textContent = aero.source === 'ml' ? 'ML MODEL' : 'FALLBACK';
  document.getElementById('s-mach').querySelector('.val').textContent   = (aero.mach ?? res.mach_launch)?.toFixed(3) || '—';
  document.getElementById('aero-source').textContent =
    `Source: ${aero.source}  |  ρ = ${aero.rho?.toFixed(5) || '—'} kg/m³`;

  // Populate results card
  const fmt = v => v > 999 ? `${(v / 1000).toFixed(2)} km` : `${v} m`;
  document.getElementById('r-range').textContent      = fmt(res.range_m);
  document.getElementById('r-height').textContent     = fmt(res.max_height_m);
  document.getElementById('r-tof').textContent        = `${res.time_of_flight_s} s`;
  document.getElementById('r-impact').textContent     = `${res.impact_speed_ms} m/s`;
  document.getElementById('r-impact-kmh').textContent = `${res.impact_speed_kmh} km/h`;
  document.getElementById('r-drift').textContent      = `${res.lateral_drift_m >= 0 ? '+' : ''}${res.lateral_drift_m} m`;
  document.getElementById('r-dr').textContent         = fmt(res.downrange_m);

  // VTK card
  if (data.vtk) {
    document.getElementById('vtk-card').style.display = '';
    document.getElementById('vtk-info').innerHTML =
      `✅ VTK → <code>${data.vtk.vtk_path}</code><br>` +
      `📄 CSV → <code>${data.vtk.csv_path}</code><br>` +
      `Points: ${data.vtk.n_points}`;
  }

  // ── CRITICAL ORDER ────────────────────────────────────────────────────────
  // 1. Hide loading / empty screens
  document.getElementById('loading').style.display      = 'none';
  document.getElementById('empty-state').style.display  = 'none';

  // 2. Make results panel VISIBLE first — before calling renderCurrentView
  //    Without this step, #viewport-3d has offsetWidth=0 and Three.js
  //    creates a 0×0 canvas → black screen.
  document.getElementById('results-panel').style.display = '';

  // 3. Store result for re-renders
  simResult = data;

  // 4. NOW render (3D renderer waits an extra 300ms internally)
  renderCurrentView();
}

// ── Render whichever view tab is active ───────────────────────────────────────
function renderCurrentView() {
  if (!simResult) return;

  const vp3d   = document.getElementById('viewport-3d');
  const c2d    = document.getElementById('canvas-2d');
  const ctop   = document.getElementById('canvas-top');
  const legend = document.getElementById('legend-3d');

  // Show/hide viewports
  vp3d.style.display   = currentView === '3d'  ? 'block' : 'none';
  c2d.style.display    = currentView === '2d'  ? 'block' : 'none';
  ctop.style.display   = currentView === 'top' ? 'block' : 'none';
  legend.style.display = currentView === '3d'  ? 'flex'  : 'none';

  const traj   = simResult.trajectory;
  const colors = MODE_COLORS[currentMode] || MODE_COLORS.general;

  if (currentView === '3d') {
    vp3d.style.display = 'block';
    vp3d.style.width   = '100%';
    vp3d.style.height  = '420px';

    // ── FIX: wait for TWO animation frames so the browser has
    //    actually laid out and painted the newly-visible panel.
    //    Only then does offsetWidth return a real pixel value.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        init3D(vp3d, traj, colors);
      });
    });
  } else if (currentView === '2d') {
    draw2D(c2d, traj, simResult.results, currentMode);
  } else {
    drawTopDown(ctop, traj, simResult.results, currentMode);
  }
}

// ── 2D Side View ─────────────────────────────────────────────────────────────
function draw2D(c, traj, res, mode) {
  c.width  = c.offsetWidth  || 680;
  c.height = 420;
  const ctx = c.getContext('2d');
  const W = c.width, H = c.height;
  ctx.fillStyle = '#020c1a'; ctx.fillRect(0, 0, W, H);

  const maxX = Math.max(...traj.map(p => p.x), 1);
  const maxZ = Math.max(...traj.map(p => p.z), 1);
  const pad  = { l: 52, r: 16, t: 18, b: 38 };
  const W2   = W - pad.l - pad.r;
  const H2   = H - pad.t - pad.b;
  const tx   = x => pad.l + (x / maxX) * W2;
  const tz   = z => H - pad.b - (z / (maxZ * 1.15)) * H2;

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'; ctx.lineWidth = 1;
  for (let i = 0; i <= 8; i++) {
    ctx.beginPath(); ctx.moveTo(pad.l + (i / 8) * W2, pad.t); ctx.lineTo(pad.l + (i / 8) * W2, H - pad.b); ctx.stroke();
  }
  for (let i = 0; i <= 5; i++) {
    ctx.beginPath(); ctx.moveTo(pad.l, pad.t + (i / 5) * H2); ctx.lineTo(W - pad.r, pad.t + (i / 5) * H2); ctx.stroke();
  }

  // Ground line
  ctx.strokeStyle = 'rgba(0,255,100,0.2)'; ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
  ctx.setLineDash([]);

  // Trajectory
  const cols = { ballistic: ['#ff5533','#ff0044'], sports: ['#00d4ff','#0066ff'], sprinkler: ['#00ff88','#00aa44'], general: ['#ffcc00','#ff6600'] };
  const [c1, c2] = cols[mode] || cols.general;
  const grad = ctx.createLinearGradient(pad.l, 0, W - pad.r, 0);
  grad.addColorStop(0, c1); grad.addColorStop(1, c2);
  ctx.strokeStyle = grad; ctx.lineWidth = 2.5;
  ctx.shadowColor = c1; ctx.shadowBlur = 5;
  ctx.beginPath();
  traj.forEach((p, i) => i === 0 ? ctx.moveTo(tx(p.x), tz(p.z)) : ctx.lineTo(tx(p.x), tz(p.z)));
  ctx.stroke(); ctx.shadowBlur = 0;

  // Apogee
  const apex = traj.reduce((a, b) => b.z > a.z ? b : a);
  ctx.fillStyle = '#ffff00'; ctx.shadowColor = '#ffff00'; ctx.shadowBlur = 12;
  ctx.beginPath(); ctx.arc(tx(apex.x), tz(apex.z), 5, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,0,0.8)'; ctx.font = "9px 'Courier New'";
  ctx.fillText(`▲ ${res.max_height_m > 999 ? (res.max_height_m/1000).toFixed(1)+'km' : res.max_height_m+'m'}`, tx(apex.x) + 8, tz(apex.z) - 4);

  // Impact X
  const imp = traj[traj.length - 1];
  ctx.strokeStyle = '#ff3333'; ctx.lineWidth = 2; ctx.shadowColor = '#ff3333'; ctx.shadowBlur = 10;
  ctx.beginPath();
  ctx.moveTo(tx(imp.x) - 6, H - pad.b - 6); ctx.lineTo(tx(imp.x) + 6, H - pad.b + 6);
  ctx.moveTo(tx(imp.x) + 6, H - pad.b - 6); ctx.lineTo(tx(imp.x) - 6, H - pad.b + 6);
  ctx.stroke(); ctx.shadowBlur = 0;

  // Labels
  ctx.fillStyle = 'rgba(150,180,210,0.5)'; ctx.font = "9px 'Courier New'";
  ctx.fillText(maxX > 999 ? `${(maxX/1000).toFixed(1)}km` : `${maxX.toFixed(0)}m`, W - pad.r - 28, H - pad.b + 13);
  ctx.fillText('Range (X) →', W / 2 - 28, H - 4);
  ctx.save(); ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillText('Altitude (Z) ↑', -30, 0); ctx.restore();
}

// ── Top-Down View ─────────────────────────────────────────────────────────────
function drawTopDown(c, traj, res, mode) {
  c.width  = c.offsetWidth  || 680;
  c.height = 420;
  const ctx = c.getContext('2d');
  const W = c.width, H = c.height;
  ctx.fillStyle = '#020c1a'; ctx.fillRect(0, 0, W, H);

  const xs = traj.map(p => p.x), ys = traj.map(p => p.y);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanY = Math.max(Math.abs(maxY - minY), maxX * 0.06, 1);
  const pad   = { l: 48, r: 16, t: 16, b: 34 };
  const W2    = W - pad.l - pad.r, H2 = H - pad.t - pad.b;
  const midY  = (minY + maxY) / 2;
  const tx    = x => pad.l + (x / maxX) * W2;
  const ty    = y => pad.t + H2 / 2 - ((y - midY) / spanY) * H2 * 0.85;

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'; ctx.lineWidth = 1;
  for (let i = 0; i <= 8; i++) {
    ctx.beginPath(); ctx.moveTo(pad.l + (i/8)*W2, pad.t); ctx.lineTo(pad.l + (i/8)*W2, H-pad.b); ctx.stroke();
  }

  // Centreline
  ctx.strokeStyle = 'rgba(0,255,100,0.15)'; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(pad.l, ty(0)); ctx.lineTo(W - pad.r, ty(0)); ctx.stroke();
  ctx.setLineDash([]);

  // Trajectory
  const cols = { ballistic: '#ff5533', sports: '#00d4ff', sprinkler: '#00ff88', general: '#ffcc00' };
  const col  = cols[mode] || cols.general;
  ctx.strokeStyle = col; ctx.lineWidth = 2.5;
  ctx.shadowColor = col; ctx.shadowBlur = 6;
  ctx.beginPath();
  traj.forEach((p, i) => i === 0 ? ctx.moveTo(tx(p.x), ty(p.y)) : ctx.lineTo(tx(p.x), ty(p.y)));
  ctx.stroke(); ctx.shadowBlur = 0;

  // Launch dot
  ctx.fillStyle = col; ctx.shadowColor = col; ctx.shadowBlur = 8;
  ctx.beginPath(); ctx.arc(pad.l, ty(0), 6, 0, Math.PI * 2); ctx.fill();

  // Impact dot
  const imp = traj[traj.length - 1];
  ctx.fillStyle = '#ff3333'; ctx.shadowColor = '#ff3333'; ctx.shadowBlur = 10;
  ctx.beginPath(); ctx.arc(tx(imp.x), ty(imp.y), 6, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0;

  // Drift label
  const drift = res.lateral_drift_m;
  ctx.fillStyle = '#cc88ff'; ctx.font = "10px 'Courier New'";
  ctx.fillText(`${drift >= 0 ? 'RIGHT' : 'LEFT'} DRIFT: ${Math.abs(drift)} m`, pad.l + 4, pad.t + 14);

  // Labels
  ctx.fillStyle = 'rgba(150,180,210,0.5)'; ctx.font = "9px 'Courier New'";
  ctx.fillText('Range (X) →', W / 2 - 28, H - 4);
  ctx.save(); ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillText('Lateral (Y)', -22, 0); ctx.restore();
}

// ── Run simulation pipeline ────────────────────────────────────────────────────
async function runSimulation() {
  const inputs = getInputs();
  const btn    = document.getElementById('btn-run');
  btn.disabled = true; btn.textContent = '⟳  SIMULATING…';

  document.getElementById('empty-state').style.display    = 'none';
  document.getElementById('results-panel').style.display  = 'none';
  document.getElementById('loading').style.display        = '';
  document.getElementById('loading-phase').textContent    = 'Calling API pipeline…';

  try {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(inputs),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    showResults(data);
  } catch (err) {
    console.warn('API offline, local physics fallback:', err.message);
    document.getElementById('loading-phase').textContent = 'API offline — local physics…';
    await new Promise(r => setTimeout(r, 100));
    const { params, weather } = inputs;
    const mach = params.velocity / speedOfSound(params.altitude, weather.temperature || 15);
    const Cd   = mach < 0.8 ? 0.47 : mach < 1.0 ? 0.47 + 1.2*(mach-0.8)**1.5 : Math.max(0.9/mach+0.1, 0.25);
    showResults(simulateLocal(params, weather, Cd, 0.0));
  }

  btn.disabled = false; btn.textContent = '▶  RUN FULL SIMULATION';
}

// ── Wire up all UI events ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // Mode buttons
  document.querySelectorAll('.mode').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.mode').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    currentMode = b.dataset.mode;
    if (currentMode === 'ballistic') document.getElementById('p-vel').max = 8000;
    else document.getElementById('p-vel').max = 200;
    if (simResult) renderCurrentView();
  }));

  // Shape buttons
  document.querySelectorAll('.shape').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.shape').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    currentShape = b.dataset.shape;
  }));

  // Weather presets
  document.querySelectorAll('.wp').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.wp').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const wp = WEATHER_PRESETS[+b.dataset.preset];
    document.getElementById('w-spd').value = wp.wind_speed;
    document.getElementById('w-dir').value = wp.wind_direction;
    document.getElementById('w-tmp').value = wp.temperature;
    document.getElementById('w-hum').value = wp.humidity;
    document.getElementById('w-prs').value = wp.pressure;
    updateLiveStats();
  }));

  // View tabs
  document.querySelectorAll('.vtab').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.vtab').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    currentView = b.dataset.view;
    renderCurrentView();
  }));

  // Sliders with live labels
  const velSlider = document.getElementById('p-vel');
  velSlider.addEventListener('input', () => {
    document.getElementById('p-vel-v').textContent = `${velSlider.value} m/s`;
    updateLiveStats();
  });
  const angSlider = document.getElementById('p-ang');
  angSlider.addEventListener('input', () => {
    document.getElementById('p-ang-v').textContent = `${angSlider.value}°`;
  });

  // Any input → update live stats
  document.querySelectorAll('input').forEach(i => i.addEventListener('input', updateLiveStats));

  // Run button
  document.getElementById('btn-run').addEventListener('click', runSimulation);

  updateLiveStats();
});

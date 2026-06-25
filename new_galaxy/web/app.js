const chartElement = document.getElementById("music-graph");
const loadingElement = document.getElementById("loading");
const genreFilter = document.getElementById("genre-filter");
const sourceFilter = document.getElementById("source-filter");
const resetButton = document.getElementById("reset-filter");
const btnPlay = document.getElementById("btn-play");
const playerWave = document.getElementById("player-wave");
const playTimeEl = document.getElementById("play-time");

/* ── Visualizer overlay ─────────────────────────────── */
const vizOverlay = document.getElementById("visualizer-overlay");
const vizCanvas = document.getElementById("viz-canvas");
const vizCtx = vizCanvas.getContext("2d");
const vizClose = document.getElementById("viz-close");
const vizPlay = document.getElementById("viz-play");
const vizTime = document.getElementById("viz-time");
const vizTitle = document.getElementById("viz-title");
const vizArtist = document.getElementById("viz-artist");
const vizGenre = document.getElementById("viz-genre");

let chart;
let graphData;
let currentNode = null;

/* ── Audio state ────────────────────────────────────── */
let audioCtx = null;
let audioAnalyser = null;
let audioSource = null;
let audioElement = null;
let currentTrackUrl = null;
let isPlaying = false;
let analyserData = null;
let prevBass = 0;
let beatEnergy = 0;
let beatDecay = 0.92;
let animFrameId = null;
let particles = [];

const genreColors = [
  "#8d7bff", "#52d5ff", "#ff7bb0", "#ffc66b",
  "#5ce1a4", "#ff835c", "#6f9dff", "#d884ff", "#a8d65d",
];

const PARTICLE_COUNT = 150;

/* ═══════════════════════════════════════════════════════
   Audio playback
   ═══════════════════════════════════════════════════════ */

async function ensureAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") await audioCtx.resume();
}

function resolveAudioUrl(node) {
  if (!node || !node.path) return null;
  return "../" + node.path.replace(/\\/g, "/");
}

async function playTrack(node) {
  const url = resolveAudioUrl(node);
  if (!url) return;

  if (currentTrackUrl === url) {
    togglePlay();
    return;
  }

  await ensureAudioContext();
  stopAudio();

  audioElement = new Audio();
  audioElement.crossOrigin = "anonymous";
  audioElement.src = url;

  audioSource = audioCtx.createMediaElementSource(audioElement);
  audioAnalyser = audioCtx.createAnalyser();
  audioAnalyser.fftSize = 512;
  audioAnalyser.smoothingTimeConstant = 0.65;
  audioSource.connect(audioAnalyser);
  audioAnalyser.connect(audioCtx.destination);

  audioElement.addEventListener("ended", () => {
    setPlayingState(false);
  });
  audioElement.addEventListener("error", () => {
    setPlayingState(false);
  });

  currentTrackUrl = url;
  analyserData = new Uint8Array(audioAnalyser.frequencyBinCount);

  await audioElement.play();
  setPlayingState(true);
  openVisualizer(node);
}

function togglePlay() {
  if (!audioElement) return;
  if (audioElement.paused) {
    audioElement.play();
    setPlayingState(true);
    if (vizOverlay.classList.contains("hidden")) {
      openVisualizer(currentNode);
    }
  } else {
    audioElement.pause();
    setPlayingState(false);
  }
}

function stopAudio() {
  if (audioSource) {
    try { audioSource.disconnect(); } catch (_) { /* ignore */ }
    audioSource = null;
  }
  if (audioElement) {
    audioElement.pause();
    audioElement.src = "";
    audioElement = null;
  }
  currentTrackUrl = null;
  beatEnergy = 0;
  prevBass = 0;
  setPlayingState(false);
}

function setPlayingState(on) {
  isPlaying = on;
  btnPlay.innerHTML = on ? "&#9646;&#9646;" : "&#9654;";
  btnPlay.classList.toggle("playing", on);
  vizPlay.innerHTML = on ? "&#9646;&#9646;" : "&#9654;";
  vizPlay.classList.toggle("playing", on);
  if (!on && animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  if (on && !animFrameId) {
    animFrameId = requestAnimationFrame(vizLoop);
  }
}

/* ═══════════════════════════════════════════════════════
   Visualizer overlay
   ═══════════════════════════════════════════════════════ */

function openVisualizer(node) {
  if (!node) return;
  vizTitle.textContent = node.title;
  vizArtist.textContent = node.artist;
  vizGenre.textContent = node.genre;
  vizGenre.style.background =
    genreColors[node.category % genreColors.length] + "33";
  vizGenre.style.color = genreColors[node.category % genreColors.length];
  resizeVizCanvas();
  initParticles();
  vizOverlay.classList.remove("hidden");
}

function closeVisualizer() {
  vizOverlay.classList.add("hidden");
  if (isPlaying) {
    stopAudio();
  }
}

vizClose.addEventListener("click", closeVisualizer);
vizPlay.addEventListener("click", () => {
  if (currentNode) playTrack(currentNode);
});

function resizeVizCanvas() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  vizCanvas.width = w;
  vizCanvas.height = h;
  vizCanvas.style.width = w + "px";
  vizCanvas.style.height = h + "px";
}

/* ═══════════════════════════════════════════════════════
   Particle system — aggregate / disperse by frequency
   ═══════════════════════════════════════════════════════ */

function initParticles() {
  const w = vizCanvas.width;
  const h = vizCanvas.height;
  particles = [];
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push(createParticle(w, h, true));
  }
}

function createParticle(w, h, random) {
  const cx = w / 2;
  const cy = h / 2;
  const angle = Math.random() * Math.PI * 2;
  const maxDist = Math.min(w, h) * 0.48;
  const dist = random ? 30 + Math.random() * maxDist : 30 + Math.random() * 120;
  return {
    x: cx + Math.cos(angle) * dist,
    y: cy + Math.sin(angle) * dist,
    vx: 0,
    vy: 0,
    baseRadius: 1.2 + Math.random() * 3.5,
    radius: 1.2 + Math.random() * 3.5,
    hue: genreColors[Math.floor(Math.random() * genreColors.length)],
    trail: [],
    maxTrail: 5 + Math.floor(Math.random() * 10),
  };
}

function vizLoop() {
  animFrameId = requestAnimationFrame(vizLoop);
  const w = vizCanvas.width;
  const h = vizCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const ctx = vizCtx;
  const screenDiag = Math.min(w, h);

  /* ── Read frequency data ─────────────────────────── */
  let bass = 0.05, mid = 0.05, high = 0.05;
  if (audioAnalyser && isPlaying && analyserData) {
    audioAnalyser.getByteFrequencyData(analyserData);
    bass = analyserData.slice(0, 16).reduce((a, b) => a + b, 0) / 16 / 255;
    mid  = analyserData.slice(16, 80).reduce((a, b) => a + b, 0) / 64 / 255;
    high = analyserData.slice(80, 200).reduce((a, b) => a + b, 0) / 120 / 255;
  }

  /* ── Beat detection ──────────────────────────────── */
  const bassDelta = bass - prevBass;
  if (bass > 0.2 && bass > prevBass * 1.25) {
    beatEnergy = Math.min(1, beatEnergy + 0.85);
  }
  beatEnergy *= beatDecay;
  prevBass = bass + (prevBass - bass) * 0.6;

  /* ── Orbit parameters ────────────────────────────── */
  const orbitRadius = screenDiag * 0.18 + bass * screenDiag * 0.06 + beatEnergy * screenDiag * 0.04;
  const bassRising = bassDelta > 0.012;
  const bassFalling = bassDelta < -0.012;
  const orbitTightness = bassRising ? 8 + bass * 12 + beatEnergy * 15
                        : bassFalling ? 1.5 + high * 3
                        : 3 + mid * 4;
  const orbitAlpha = 0.12 + bass * 0.4 + beatEnergy * 0.3;

  /* ── Render ──────────────────────────────────────── */
  ctx.clearRect(0, 0, w, h);

  // --- Central star (subtle) ---
  const starR = 4 + bass * 18 + beatEnergy * 15;
  const starGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, starR * 4);
  starGrad.addColorStop(0, "rgba(240,230,255," + (0.6 + beatEnergy * 0.35) + ")");
  starGrad.addColorStop(0.3, "rgba(140,120,220,0.2)");
  starGrad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = starGrad;
  ctx.beginPath(); ctx.arc(cx, cy, starR * 4, 0, Math.PI * 2); ctx.fill();

  // --- Orbit ring glow ---
  const ringGlow = ctx.createRadialGradient(cx, cy, orbitRadius * 0.82, cx, cy, orbitRadius * 1.18);
  ringGlow.addColorStop(0, "rgba(0,0,0,0)");
  ringGlow.addColorStop(0.35, "rgba(150,130,240," + orbitAlpha + ")");
  ringGlow.addColorStop(0.65, "rgba(120,100,210," + (orbitAlpha * 0.7) + ")");
  ringGlow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = ringGlow;
  ctx.beginPath(); ctx.arc(cx, cy, orbitRadius * 1.18, 0, Math.PI * 2); ctx.fill();

  // --- Orbit reference ring (subtle dashed hint) ---
  ctx.beginPath();
  ctx.arc(cx, cy, orbitRadius, 0, Math.PI * 2);
  ctx.strokeStyle = "rgba(160,150,220," + (0.06 + orbitAlpha * 0.5) + ")";
  ctx.lineWidth = 0.8;
  ctx.setLineDash([3, 12]);
  ctx.stroke();
  ctx.setLineDash([]);

  // --- Beat shockwave — expanding from the orbit ---
  if (beatEnergy > 0.05) {
    for (let ring = 1; ring <= 3; ring++) {
      const swR = orbitRadius + beatEnergy * 200 * (1 - (ring - 1) * 0.2);
      const swAlpha = beatEnergy * (0.5 - ring * 0.13);
      if (swAlpha <= 0) continue;
      ctx.beginPath();
      ctx.arc(cx, cy, swR, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(180,160,255," + swAlpha + ")";
      ctx.lineWidth = 1 + beatEnergy * 3 * (1 - ring * 0.22);
      ctx.stroke();
    }
  }

  // --- Particles ---
  for (const p of particles) {
    const dx = cx - p.x;
    const dy = cy - p.y;
    const dist = Math.hypot(dx, dy) || 1;
    const nx = dx / dist;
    const ny = dy / dist;
    const offsetFromOrbit = dist - orbitRadius;

    /* ── Orbit attraction: pull particles TOWARD the orbit ring ─── */
    // If particle is outside the orbit → pull it IN
    // If particle is inside the orbit → push it OUT
    // Force scales with how far from the orbit AND with orbitTightness
    const orbitForce = offsetFromOrbit * orbitTightness * 0.04;
    p.vx += nx * orbitForce;
    p.vy += ny * orbitForce;

    /* ── Disperse: bassFalling → weaken orbit, widen spread ─── */
    if (bassFalling) {
      const scatter = Math.abs(bassDelta) * 8 + high * 1.2;
      p.vx -= nx * offsetFromOrbit * scatter * 0.03;
      p.vy -= ny * offsetFromOrbit * scatter * 0.03;
    }

    /* ── Tangential / orbital rotation ────────────────────────── */
    const orbitSpeed = mid * 0.12 + high * 0.06 + bass * 0.04;
    p.vx += -ny * orbitSpeed;
    p.vy += nx * orbitSpeed;

    /* ── Beat kick: on beat, give tangential burst ────────────── */
    if (beatEnergy > 0.3) {
      const kickDir = (p.phase || 0) < Math.PI ? 1 : -1;
      p.vx += -ny * beatEnergy * 0.2 * kickDir;
      p.vy += nx * beatEnergy * 0.2 * kickDir;
    }

    // Random jitter
    const jitter = 0.02 + (bass + high) * 0.06;
    p.vx += (Math.random() - 0.5) * jitter;
    p.vy += (Math.random() - 0.5) * jitter;

    // Speed cap
    const maxSpeed = 4 + bass * 8 + high * 6;
    const speed = Math.hypot(p.vx, p.vy);
    if (speed > maxSpeed) { p.vx *= maxSpeed / speed; p.vy *= maxSpeed / speed; }

    // Damping
    p.vx *= 0.935;
    p.vy *= 0.935;

    p.x += p.vx;
    p.y += p.vy;

    // Screen wrap
    const margin = 40;
    if (p.x < -margin) p.x = w + margin;
    if (p.x > w + margin) p.x = -margin;
    if (p.y < -margin) p.y = h + margin;
    if (p.y > h + margin) p.y = -margin;

    // Radius — pulses with energy
    const energy = bass * 2.5 + high * 1.0 + beatEnergy * 3.0;
    const targetR = p.baseRadius * (0.5 + energy);
    p.radius += (targetR - p.radius) * 0.28;

    // Trail
    p.trail.push({ x: p.x, y: p.y, r: p.radius });
    if (p.trail.length > p.maxTrail) p.trail.shift();

    // Draw trail
    if (p.trail.length > 1) {
      for (let i = 1; i < p.trail.length; i++) {
        const t = i / p.trail.length;
        const tr = p.trail[i];
        ctx.beginPath();
        ctx.arc(tr.x, tr.y, p.radius * t * 0.7, 0, Math.PI * 2);
        ctx.fillStyle = p.hue;
        ctx.globalAlpha = t * 0.14;
        ctx.fill();
      }
    }

    // Draw particle — brighter when close to the orbit
    const onOrbitBonus = Math.max(0, 1 - Math.abs(offsetFromOrbit) / (orbitRadius * 0.4));
    const alpha = 0.2 + (bass + high) * 0.5 + beatEnergy * 0.35 + onOrbitBonus * 0.4;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
    ctx.fillStyle = p.hue;
    ctx.globalAlpha = Math.min(1, alpha);
    ctx.fill();

    // Glow — larger when dispersed away from orbit
    const glowMult = Math.abs(offsetFromOrbit) > orbitRadius * 0.3 ? 5 : 2.5;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.radius * glowMult, 0, Math.PI * 2);
    ctx.fillStyle = p.hue;
    ctx.globalAlpha = Math.min(0.5, alpha * 0.08);
    ctx.fill();
  }

  ctx.globalAlpha = 1;

  // Update time
  updateVizTime();

  // Frequency ring (at a larger radius)
  if (analyserData && isPlaying) {
    drawFreqRing(ctx, cx, cy, screenDiag, bass, mid, high);
  }
}

/* ── Frequency ring around center ─────────────────── */

function drawFreqRing(ctx, cx, cy, screenDiag, bass, mid, high) {
  const ringBase = screenDiag * 0.31;
  const ringWidth = screenDiag * 0.05;
  const segments = 64;
  const band = analyserData.length / segments;

  for (let i = 0; i < segments; i++) {
    const startIdx = Math.floor(i * band);
    const endIdx = Math.floor((i + 1) * band);
    let sum = 0;
    for (let j = startIdx; j < endIdx; j++) sum += analyserData[j];
    const val = sum / (endIdx - startIdx) / 255;

    const angle = (i / segments) * Math.PI * 2 - Math.PI / 2;
    const innerR = ringBase + val * ringWidth * 0.15;
    const outerR = ringBase + val * ringWidth;

    const hueIdx = Math.floor((i / segments) * genreColors.length);
    const color = genreColors[hueIdx % genreColors.length];

    ctx.beginPath();
    ctx.arc(cx, cy, outerR, angle - 0.04, angle + 0.04);
    ctx.arc(cx, cy, innerR, angle + 0.04, angle - 0.04, true);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.15 + val * 0.75;
    ctx.fill();
  }

  // Highlight dots at peak frequencies
  for (let peak = 0; peak < 4; peak++) {
    let maxVal = 0, maxIdx = 0;
    const rangeStart = Math.floor(peak * analyserData.length / 4);
    const rangeEnd = Math.floor((peak + 1) * analyserData.length / 4);
    for (let j = rangeStart; j < rangeEnd; j++) {
      if (analyserData[j] > maxVal) { maxVal = analyserData[j]; maxIdx = j; }
    }
    const peakVal = maxVal / 255;
    const peakAngle = (maxIdx / analyserData.length) * Math.PI * 2 - Math.PI / 2;
    const peakR = ringBase + ringWidth * 0.5;
    const px = cx + Math.cos(peakAngle) * peakR;
    const py = cy + Math.sin(peakAngle) * peakR;

    ctx.beginPath();
    ctx.arc(px, py, 2.5 + peakVal * 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.globalAlpha = 0.3 + peakVal * 0.7;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(px, py, 5 + peakVal * 14, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.globalAlpha = (0.3 + peakVal * 0.7) * 0.12;
    ctx.fill();
  }

  ctx.globalAlpha = 1;
}

function updateVizTime() {
  if (!audioElement || audioElement.paused) return;
  const t = audioElement.currentTime;
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  vizTime.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ═══════════════════════════════════════════════════════
   Graph rendering (unchanged logic, adapted)
   ═══════════════════════════════════════════════════════ */

function nodeStyle(node) {
  return {
    color: genreColors[node.category % genreColors.length],
    borderColor: node.isPersonal ? "#ffffff" : "rgba(255,255,255,0.28)",
    borderWidth: node.isPersonal ? 3 : 1,
    shadowBlur: node.isPersonal ? 22 : 9,
    shadowColor: node.isPersonal ? "#58d6ff" : "rgba(80,100,220,0.35)",
  };
}

function tooltipFormatter(params) {
  if (params.dataType === "edge") {
    return `<strong>相似关系</strong><br>相似度：${Number(params.data.value).toFixed(3)}`;
  }
  const node = params.data;
  const hasAudio = node.path && (node.source === "fma" || node.source === "personal");
  return `
    <strong>${escapeHtml(node.title)}</strong><br>
    ${escapeHtml(node.artist)} · ${escapeHtml(node.genre)}<br>
    来源：${escapeHtml(node.source)}<br>
    BPM：${Number(node.tempo).toFixed(1)}<br>
    Energy：${Number(node.energy).toFixed(3)}<br>
    ${hasAudio ? '<em style="color:#58d6ff">点击播放</em>' : ""}
  `;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value ?? "");
  return div.innerHTML;
}

function renderGraph() {
  const genre = genreFilter.value;
  const source = sourceFilter.value;
  const nodes = graphData.nodes
    .filter((n) => genre === "all" || n.genre === genre)
    .filter((n) => source === "all" || n.source === source)
    .map((n) => ({ ...n, itemStyle: nodeStyle(n) }));
  const visibleIds = new Set(nodes.map((n) => n.id));
  const links = graphData.links.filter(
    (l) => visibleIds.has(String(l.source)) && visibleIds.has(String(l.target)),
  );

  chart.setOption({
    animationDurationUpdate: 500,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item", confine: true, padding: 12,
      borderWidth: 1, borderColor: "rgba(141,123,255,.35)",
      backgroundColor: "rgba(10,13,28,.94)",
      textStyle: { color: "#eef1ff", fontSize: 12, lineHeight: 20 },
      formatter: tooltipFormatter,
    },
    legend: {
      type: "scroll", orient: "vertical", left: 16, top: 18, bottom: 18,
      data: graphData.categories.map((c) => c.name),
      textStyle: { color: "#8992b3", fontSize: 10 },
      pageTextStyle: { color: "#8992b3" },
      pageIconColor: "#8d7bff", pageIconInactiveColor: "#343a58",
    },
    series: [{
      type: "graph", layout: "force", data: nodes, links,
      categories: graphData.categories, roam: true, draggable: true, cursor: "pointer",
      label: {
        show: nodes.length <= 45, position: "right",
        color: "rgba(240,243,255,.72)", fontSize: 9, formatter: "{b}",
      },
      emphasis: {
        focus: "adjacency",
        label: { show: true, color: "#fff", fontSize: 11 },
        lineStyle: { width: 2.2, opacity: 0.9 },
      },
      lineStyle: { color: "source", width: 0.8, opacity: 0.18, curveness: 0.08 },
      force: {
        repulsion: nodes.length > 80 ? 135 : 175, gravity: 0.085,
        edgeLength: [55, 125], friction: 0.62, layoutAnimation: true,
      },
    }],
  }, true);

  document.getElementById("track-count").textContent = nodes.length;
  document.getElementById("edge-count").textContent = links.length;
  document.getElementById("genre-count").textContent =
    new Set(nodes.map((n) => n.genre)).size;
}

function showDetail(node) {
  currentNode = node;
  document.getElementById("empty-detail").classList.add("hidden");
  document.getElementById("song-detail").classList.remove("hidden");
  document.getElementById("detail-source").textContent = node.source;
  document.getElementById("detail-genre").textContent = node.genre;
  document.getElementById("detail-title").textContent = node.title;
  document.getElementById("detail-artist").textContent = node.artist;
  document.getElementById("detail-tempo").textContent = Number(node.tempo).toFixed(1);
  document.getElementById("detail-energy").textContent = Number(node.energy).toFixed(4);
  document.getElementById("detail-centroid").textContent =
    `${Math.round(Number(node.spectral_centroid))} Hz`;

  const hasAudio = node.path && (node.source === "fma" || node.source === "personal");
  btnPlay.style.display = hasAudio ? "" : "none";
  playerWave.style.display = hasAudio ? "" : "none";
  playTimeEl.style.display = hasAudio ? "" : "none";

  if (hasAudio) {
    const url = resolveAudioUrl(node);
    if (currentTrackUrl === url && isPlaying) {
      btnPlay.innerHTML = "&#9646;&#9646;";
      btnPlay.classList.add("playing");
    } else {
      btnPlay.innerHTML = "&#9654;";
      btnPlay.classList.remove("playing");
    }
  }

  const list = document.getElementById("recommendation-list");
  const recs = graphData.recommendations[node.id] || [];
  list.innerHTML = recs.map((item) => `
    <li>
      <b title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</b>
      <small>${escapeHtml(item.artist)} · ${escapeHtml(item.genre)}</small>
      <em>${(Number(item.similarity) * 100).toFixed(1)}%</em>
    </li>
  `).join("");
}

/* ═══════════════════════════════════════════════════════
   Init
   ═══════════════════════════════════════════════════════ */

async function loadGraph() {
  if (typeof echarts === "undefined") {
    throw new Error("ECharts 未加载。请检查网络连接或改用本地 ECharts 文件。");
  }
  const resp = await fetch("music_graph.json");
  if (!resp.ok) throw new Error(`music_graph.json 加载失败 (${resp.status})`);
  graphData = await resp.json();
  chart = echarts.init(chartElement, null, { renderer: "canvas" });

  graphData.categories.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat.name;
    opt.textContent = cat.name;
    genreFilter.appendChild(opt);
  });

  chart.on("click", (params) => {
    if (params.dataType === "node") showDetail(params.data);
  });
  window.addEventListener("resize", () => {
    chart.resize();
    if (!vizOverlay.classList.contains("hidden")) resizeVizCanvas();
  });
  genreFilter.addEventListener("change", renderGraph);
  sourceFilter.addEventListener("change", renderGraph);
  resetButton.addEventListener("click", () => {
    genreFilter.value = "all";
    sourceFilter.value = "all";
    renderGraph();
  });
  btnPlay.addEventListener("click", () => {
    if (currentNode) playTrack(currentNode);
  });

  // Keyboard shortcut: Esc to close visualizer
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !vizOverlay.classList.contains("hidden")) {
      closeVisualizer();
    }
  });

  loadingElement.remove();
  renderGraph();
}

loadGraph().catch((error) => {
  loadingElement.classList.add("error");
  loadingElement.innerHTML = `
    <div>
      <strong>星图加载失败</strong><br>
      ${escapeHtml(error.message)}<br>
      请在项目根目录运行 <code>python -m http.server 8000</code>，再访问
      <code>http://localhost:8000/web/</code>。
    </div>
  `;
  console.error(error);
});

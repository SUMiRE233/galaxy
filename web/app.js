const chartElement = document.getElementById("music-graph");
const loadingElement = document.getElementById("loading");
const genreFilter = document.getElementById("genre-filter");
const sourceFilter = document.getElementById("source-filter");
const resetButton = document.getElementById("reset-filter");
const topKSlider = document.getElementById("topk-slider");
const topKValue = document.getElementById("topk-value");
const DEFAULT_TOP_K = 5;
const API_BASE_URL = "http://127.0.0.1:8001";
const uploadDropzone = document.getElementById("upload-dropzone");
const audioUploadInput = document.getElementById("audio-upload-input");
const chooseAudioButton = document.getElementById("choose-audio-button");
const exportPersonalButton = document.getElementById("export-personal-button");
const resetPersonalButton = document.getElementById("reset-personal-button");
const deletePersonalButton = document.getElementById("delete-personal-button");
const uploadStatus = document.getElementById("upload-status");
const genreModal = document.getElementById("genre-modal");
const pendingFilename = document.getElementById("pending-filename");
const pendingTitle = document.getElementById("pending-title");
const pendingArtist = document.getElementById("pending-artist");
const pendingAlbum = document.getElementById("pending-album");
const pendingGenreSelect = document.getElementById("pending-genre-select");
const unknownGenreNote = document.getElementById("unknown-genre-note");
const confirmGenreButton = document.getElementById("confirm-genre-button");
const cancelGenreButton = document.getElementById("cancel-genre-button");
const playerBar = document.getElementById("player-bar");
const btnPlay = document.getElementById("btn-play");
const playerWave = document.getElementById("player-wave");
const playTimeEl = document.getElementById("play-time");
const vizOverlay = document.getElementById("visualizer-overlay");
const vizCanvas = document.getElementById("viz-canvas");
const vizCtx = vizCanvas?.getContext("2d");
const vizClose = document.getElementById("viz-close");
const vizPlay = document.getElementById("viz-play");
const vizTime = document.getElementById("viz-time");
const vizTitle = document.getElementById("viz-title");
const vizArtist = document.getElementById("viz-artist");
const vizGenre = document.getElementById("viz-genre");

let chart;
let graphData;
let selectedNodeId = null;
let pendingUploadTempId = null;
let currentNode = null;
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

function nodeStyle(node) {
  const personal = node.isPersonal || node.source === "personal";
  return {
    color: genreColors[node.category % genreColors.length],
    borderColor: personal ? "#ffffff" : "rgba(255,255,255,0.28)",
    borderWidth: personal ? 3 : 1,
    shadowBlur: personal ? 26 : 9,
    shadowColor: personal ? "#58d6ff" : "rgba(80,100,220,0.35)",
  };
}

function tooltipFormatter(params) {
  if (params.dataType === "edge") {
    return `
      <strong>相似关系</strong><br>
      相似度：${Number(params.data.value).toFixed(3)}
    `;
  }
  const node = params.data;
  return `
    <strong>${escapeHtml(node.title)}</strong><br>
    ${escapeHtml(node.artist)} · ${escapeHtml(node.genre)}<br>
    来源：${node.source === "personal" ? "My Music" : escapeHtml(node.source)}<br>
    BPM：${Number(node.tempo).toFixed(1)}<br>
    Energy：${Number(node.energy).toFixed(3)}<br>
    ${node.path && ["personal", "gtzan"].includes(node.source)
      ? '<em style="color:#58d6ff">点击节点后可播放</em>'
      : ""}
  `;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function getVisibleTopK() {
  return Number(topKSlider?.value || DEFAULT_TOP_K);
}

const buildVisibleLinks = window.MusicGraphUtils.buildVisibleLinks;

async function ensureAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") await audioCtx.resume();
}

function resolveAudioUrl(node) {
  if (!node || !node.path) return null;
  const cleanPath = String(node.path).replace(/\\/g, "/");
  return `${API_BASE_URL}/api/audio?path=${encodeURIComponent(cleanPath)}`;
}

async function playTrack(node) {
  const url = resolveAudioUrl(node);
  if (!url) return;

  currentNode = node;
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
  audioAnalyser.smoothingTimeConstant = 0.8;
  audioSource.connect(audioAnalyser);
  audioAnalyser.connect(audioCtx.destination);
  analyserData = new Uint8Array(audioAnalyser.frequencyBinCount);
  currentTrackUrl = url;

  audioElement.addEventListener("ended", () => setPlayingState(false));
  audioElement.addEventListener("error", () => setPlayingState(false));
  await audioElement.play();
  setPlayingState(true);
  openVisualizer(node);
}

function togglePlay() {
  if (!audioElement) return;
  if (audioElement.paused) {
    audioElement.play();
    setPlayingState(true);
    if (vizOverlay?.classList.contains("hidden")) openVisualizer(currentNode);
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
  updateVizTime();
}

function setPlayingState(on) {
  isPlaying = on;
  if (btnPlay) {
    btnPlay.innerHTML = on ? "&#9646;&#9646;" : "&#9654;";
    btnPlay.classList.toggle("playing", on);
  }
  if (vizPlay) {
    vizPlay.innerHTML = on ? "&#9646;&#9646;" : "&#9654;";
    vizPlay.classList.toggle("playing", on);
  }
  if (!on && animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  if (on && !animFrameId) {
    animFrameId = requestAnimationFrame(vizLoop);
  }
}

function openVisualizer(node) {
  if (!node || !vizOverlay || !vizCanvas) return;
  if (vizTitle) vizTitle.textContent = node.title;
  if (vizArtist) vizArtist.textContent = node.artist;
  if (vizGenre) {
    vizGenre.textContent = node.genre;
    const color = genreColors[node.category % genreColors.length];
    vizGenre.style.background = `${color}33`;
    vizGenre.style.color = color;
  }
  resizeVizCanvas();
  initParticles();
  vizOverlay.classList.remove("hidden");
}

function closeVisualizer() {
  vizOverlay?.classList.add("hidden");
  if (isPlaying) stopAudio();
}

function resizeVizCanvas() {
  if (!vizCanvas) return;
  vizCanvas.width = window.innerWidth;
  vizCanvas.height = window.innerHeight;
  vizCanvas.style.width = `${window.innerWidth}px`;
  vizCanvas.style.height = `${window.innerHeight}px`;
}

function initParticles() {
  if (!vizCanvas) return;
  particles = [];
  for (let i = 0; i < PARTICLE_COUNT; i += 1) {
    particles.push(createParticle(vizCanvas.width, vizCanvas.height, true));
  }
}

function createParticle(w, h, random = true) {
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

function updatePlayerWave(bass = 0.05, mid = 0.05, high = 0.05) {
  if (!playerWave) return;
  if (!playerWave.children.length) {
    for (let i = 0; i < 28; i += 1) {
      playerWave.appendChild(document.createElement("span"));
    }
  }
  [...playerWave.children].forEach((bar, index) => {
    const wave = Math.sin(index * 0.8 + performance.now() * 0.006) * 0.5 + 0.5;
    const level = 8 + (bass * 12 + mid * 10 + high * 8) * wave;
    bar.style.height = `${Math.max(4, Math.min(28, level))}px`;
    bar.style.background = isPlaying ? "var(--cyan)" : "var(--accent)";
  });
}

function vizLoop() {
  animFrameId = requestAnimationFrame(vizLoop);
  if (!vizCtx || !vizCanvas) return;

  const w = vizCanvas.width;
  const h = vizCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const screen = Math.min(w, h);
  let bass = 0.05;
  let mid = 0.05;
  let high = 0.05;

  if (audioAnalyser && isPlaying && analyserData) {
    audioAnalyser.getByteFrequencyData(analyserData);
    bass = analyserData.slice(0, 16).reduce((a, b) => a + b, 0) / 16 / 255;
    mid = analyserData.slice(16, 80).reduce((a, b) => a + b, 0) / 64 / 255;
    high = analyserData.slice(80, 200).reduce((a, b) => a + b, 0) / 120 / 255;
  }

  if (bass > 0.2 && bass > prevBass * 1.25) beatEnergy = Math.min(1, beatEnergy + 0.85);
  beatEnergy *= beatDecay;
  prevBass = bass + (prevBass - bass) * 0.6;
  updatePlayerWave(bass, mid, high);

  vizCtx.clearRect(0, 0, w, h);
  const orbitRadius = screen * 0.18 + bass * screen * 0.06 + beatEnergy * screen * 0.04;
  const starR = 4 + bass * 18 + beatEnergy * 15;
  const starGrad = vizCtx.createRadialGradient(cx, cy, 0, cx, cy, starR * 4);
  starGrad.addColorStop(0, `rgba(240,230,255,${0.6 + beatEnergy * 0.35})`);
  starGrad.addColorStop(0.3, "rgba(140,120,220,0.2)");
  starGrad.addColorStop(1, "rgba(0,0,0,0)");
  vizCtx.fillStyle = starGrad;
  vizCtx.beginPath();
  vizCtx.arc(cx, cy, starR * 4, 0, Math.PI * 2);
  vizCtx.fill();

  for (const p of particles) {
    const dx = cx - p.x;
    const dy = cy - p.y;
    const dist = Math.hypot(dx, dy) || 1;
    const nx = dx / dist;
    const ny = dy / dist;
    const offset = dist - orbitRadius;
    const force = offset * (3 + mid * 5) * 0.04;
    p.vx += nx * force - ny * (mid * 0.12 + high * 0.06);
    p.vy += ny * force + nx * (mid * 0.12 + high * 0.06);
    p.vx += (Math.random() - 0.5) * (0.02 + high * 0.08);
    p.vy += (Math.random() - 0.5) * (0.02 + high * 0.08);
    p.vx *= 0.935;
    p.vy *= 0.935;
    p.x += p.vx;
    p.y += p.vy;

    if (p.x < -40) p.x = w + 40;
    if (p.x > w + 40) p.x = -40;
    if (p.y < -40) p.y = h + 40;
    if (p.y > h + 40) p.y = -40;

    p.radius += (p.baseRadius * (0.5 + bass * 2.5 + high + beatEnergy * 3) - p.radius) * 0.28;
    p.trail.push({ x: p.x, y: p.y });
    if (p.trail.length > p.maxTrail) p.trail.shift();

    p.trail.forEach((point, index) => {
      vizCtx.beginPath();
      vizCtx.arc(point.x, point.y, p.radius * (index / p.trail.length) * 0.7, 0, Math.PI * 2);
      vizCtx.fillStyle = p.hue;
      vizCtx.globalAlpha = (index / p.trail.length) * 0.14;
      vizCtx.fill();
    });
    vizCtx.beginPath();
    vizCtx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
    vizCtx.fillStyle = p.hue;
    vizCtx.globalAlpha = Math.min(1, 0.25 + bass * 0.5 + high * 0.5 + beatEnergy * 0.35);
    vizCtx.fill();
  }
  vizCtx.globalAlpha = 1;
  if (analyserData && isPlaying) drawFreqRing(vizCtx, cx, cy, screen);
  updateVizTime();
}

function drawFreqRing(ctx, cx, cy, screen) {
  const ringBase = screen * 0.31;
  const ringWidth = screen * 0.05;
  const segments = 64;
  const band = analyserData.length / segments;
  for (let i = 0; i < segments; i += 1) {
    const startIdx = Math.floor(i * band);
    const endIdx = Math.floor((i + 1) * band);
    let sum = 0;
    for (let j = startIdx; j < endIdx; j += 1) sum += analyserData[j];
    const val = sum / (endIdx - startIdx) / 255;
    const angle = (i / segments) * Math.PI * 2 - Math.PI / 2;
    const innerR = ringBase + val * ringWidth * 0.15;
    const outerR = ringBase + val * ringWidth;
    const color = genreColors[Math.floor((i / segments) * genreColors.length) % genreColors.length];
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, angle - 0.04, angle + 0.04);
    ctx.arc(cx, cy, innerR, angle + 0.04, angle - 0.04, true);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.15 + val * 0.75;
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function updateVizTime() {
  const t = audioElement ? audioElement.currentTime : 0;
  const text = `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
  if (vizTime) vizTime.textContent = text;
  if (playTimeEl) playTimeEl.textContent = text;
}

function renderGraph() {
  const genre = genreFilter.value;
  const source = sourceFilter.value;
  const topK = getVisibleTopK();
  const nodes = graphData.nodes
    .filter((node) => genre === "all" || node.genre === genre)
    .filter((node) => source === "all" || node.source === source)
    .map((node) => {
      const personal = node.isPersonal || node.source === "personal";
      return {
        ...node,
        isPersonal: personal,
        symbolSize: Number(node.symbolSize || 16) + (personal ? 8 : 0),
        itemStyle: nodeStyle(node),
      };
    });
  const visibleIds = new Set(nodes.map((node) => String(node.id)));
  const links = buildVisibleLinks(graphData, visibleIds, topK);

  chart.setOption(
    {
      animationDurationUpdate: 500,
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        confine: true,
        padding: 12,
        borderWidth: 1,
        borderColor: "rgba(141,123,255,.35)",
        backgroundColor: "rgba(10,13,28,.94)",
        textStyle: { color: "#eef1ff", fontSize: 12, lineHeight: 20 },
        formatter: tooltipFormatter,
      },
      legend: {
        type: "scroll",
        orient: "vertical",
        left: 16,
        top: 18,
        bottom: 18,
        data: graphData.categories.map((item) => item.name),
        textStyle: { color: "#8992b3", fontSize: 10 },
        pageTextStyle: { color: "#8992b3" },
        pageIconColor: "#8d7bff",
        pageIconInactiveColor: "#343a58",
      },
      series: [
        {
          id: "music-galaxy-force",
          type: "graph",
          layout: "force",
          data: nodes,
          links,
          edges: links,
          categories: graphData.categories,
          roam: true,
          draggable: true,
          cursor: "pointer",
          label: {
            show: nodes.length <= 45,
            position: "right",
            color: "rgba(240,243,255,.72)",
            fontSize: 9,
            formatter: "{b}",
          },
          emphasis: {
            focus: "adjacency",
            label: { show: true, color: "#fff", fontSize: 11 },
            lineStyle: { width: 2.2, opacity: 0.9 },
          },
          lineStyle: {
            color: "source",
            width: 0.8,
            opacity: 0.18,
            curveness: 0.08,
          },
          force: {
            repulsion: nodes.length > 80 ? 135 : 175,
            gravity: 0.085,
            edgeLength: [55, 125],
            friction: 0.62,
            layoutAnimation: true,
          },
        },
      ],
    },
    { notMerge: true, replaceMerge: ["series"], lazyUpdate: false },
  );

  document.getElementById("track-count").textContent = nodes.length;
  document.getElementById("edge-count").textContent = links.length;
  document.getElementById("genre-count").textContent =
    new Set(nodes.map((node) => node.genre)).size;
}

function showDetail(node) {
  currentNode = node;
  selectedNodeId = String(node.id);
  document.getElementById("empty-detail").classList.add("hidden");
  document.getElementById("song-detail").classList.remove("hidden");
  document.getElementById("detail-source").textContent =
    node.source === "personal" ? "My Music" : node.source;
  document.getElementById("detail-genre").textContent = node.genre;
  document.getElementById("detail-title").textContent = node.title;
  document.getElementById("detail-artist").textContent = node.artist;
  document.getElementById("detail-tempo").textContent = Number(node.tempo).toFixed(1);
  document.getElementById("detail-energy").textContent = Number(node.energy).toFixed(4);
  document.getElementById("detail-centroid").textContent =
    `${Math.round(Number(node.spectral_centroid))} Hz`;

  const hasAudio = node.path && ["personal", "gtzan"].includes(node.source);
  playerBar?.classList.toggle("hidden", !hasAudio);
  deletePersonalButton?.classList.toggle("hidden", node.source !== "personal");
  if (hasAudio) {
    const url = resolveAudioUrl(node);
    const playingThisTrack = currentTrackUrl === url && isPlaying;
    if (btnPlay) {
      btnPlay.innerHTML = playingThisTrack ? "&#9646;&#9646;" : "&#9654;";
      btnPlay.classList.toggle("playing", playingThisTrack);
    }
    updatePlayerWave();
  }

  const list = document.getElementById("recommendation-list");
  const heading = document.querySelector(".recommendation-block h3");
  const topK = getVisibleTopK();
  const recommendations = graphData.recommendations?.[node.id] || [];
  const visibleRecommendations = recommendations.slice(0, topK);
  if (heading) heading.textContent = `Top ${topK} 相似歌曲`;
  list.innerHTML = visibleRecommendations.map((item) => `
    <li>
      <b title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</b>
      <small>${escapeHtml(item.artist)} · ${escapeHtml(item.genre)}</small>
      <em>${(Number(item.similarity) * 100).toFixed(1)}%</em>
    </li>
  `).join("");
}

function setUploadStatus(message, type = "") {
  if (!uploadStatus) return;
  uploadStatus.textContent = message;
  uploadStatus.className = `upload-status ${type}`.trim();
}

function populateGenreFilter() {
  const current = genreFilter.value || "all";
  genreFilter.innerHTML = '<option value="all">全部流派</option>';
  graphData.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.name;
    option.textContent = category.name;
    genreFilter.appendChild(option);
  });
  genreFilter.value = [...genreFilter.options].some((option) => option.value === current)
    ? current
    : "all";
}

async function parseApiResponse(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.message || `请求失败 (${response.status})`);
  }
  return body;
}

async function refreshGraph(options = {}) {
  const response = await fetch(`${API_BASE_URL}/api/graph`);
  graphData = await parseApiResponse(response);
  populateGenreFilter();
  renderGraph();

  if (options.selectLatestPersonal) {
    const personalNodes = graphData.nodes.filter((node) => node.source === "personal");
    const latest = personalNodes[personalNodes.length - 1];
    if (latest) {
      selectedNodeId = String(latest.id);
      showDetail(latest);
    }
  }
}

function showGenreModal(payload) {
  pendingUploadTempId = payload.temp_id;
  const metadata = payload.metadata || {};
  pendingFilename.textContent = metadata.filename || "--";
  pendingTitle.textContent = metadata.title || "--";
  pendingArtist.textContent = metadata.artist || "--";
  pendingAlbum.textContent = metadata.album || "--";
  pendingGenreSelect.value = "Pop";
  unknownGenreNote.classList.add("hidden");
  genreModal.classList.remove("hidden");
}

async function uploadPersonalAudio(file) {
  if (!file) return;
  const extension = file.name.split(".").pop()?.toLowerCase();
  const supported = ["mp3", "wav", "flac", "ogg", "m4a", "aac"];
  if (!file.type.startsWith("audio/") && !supported.includes(extension)) {
    setUploadStatus("请选择 MP3、WAV、FLAC、M4A 等音频文件。", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  setUploadStatus("正在上传并提取音频特征，请稍候...");

  try {
    const response = await fetch(`${API_BASE_URL}/api/upload-personal`, {
      method: "POST",
      body: formData,
    });
    const result = await parseApiResponse(response);
    if (result.need_genre) {
      setUploadStatus("已提取特征，请选择歌曲流派后加入星图。");
      showGenreModal(result);
      return;
    }
    setUploadStatus(result.message || "个人歌曲已加入 Music Galaxy。", "success");
    await refreshGraph({ selectLatestPersonal: true });
  } catch (error) {
    const backendHint = error instanceof TypeError
      ? "请先运行 python scripts/server.py 启动本地处理服务。"
      : error.message;
    setUploadStatus(backendHint, "error");
  } finally {
    if (audioUploadInput) audioUploadInput.value = "";
  }
}

async function confirmPersonalGenre() {
  if (!pendingUploadTempId) return;
  setUploadStatus("正在加入个人音乐并重建星图...");
  confirmGenreButton.disabled = true;
  try {
    const response = await fetch(`${API_BASE_URL}/api/confirm-personal-genre`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        temp_id: pendingUploadTempId,
        genre: pendingGenreSelect.value,
      }),
    });
    const result = await parseApiResponse(response);
    genreModal.classList.add("hidden");
    pendingUploadTempId = null;
    setUploadStatus(result.message || "个人歌曲已加入 Music Galaxy。", "success");
    await refreshGraph({ selectLatestPersonal: true });
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    confirmGenreButton.disabled = false;
  }
}

async function cancelPendingUpload() {
  const tempId = pendingUploadTempId;
  if (!tempId) {
    genreModal.classList.add("hidden");
    return;
  }

  cancelGenreButton.disabled = true;
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/pending-personal/${encodeURIComponent(tempId)}`,
      { method: "DELETE" },
    );
    await parseApiResponse(response);
    genreModal.classList.add("hidden");
    pendingUploadTempId = null;
    setUploadStatus("已取消加入该音频。");
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    cancelGenreButton.disabled = false;
  }
}


function clearSelectedDetail() {
  stopAudio();
  currentNode = null;
  selectedNodeId = null;
  document.getElementById("song-detail").classList.add("hidden");
  document.getElementById("empty-detail").classList.remove("hidden");
}


async function downloadPersonalExport() {
  exportPersonalButton.disabled = true;
  setUploadStatus("正在导出个人音乐数据...");
  try {
    const response = await fetch(`${API_BASE_URL}/api/personal/export`);
    if (!response.ok) await parseApiResponse(response);
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const filename = match?.[1] || "music-galaxy-personal.zip";
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setUploadStatus("个人数据已导出。", "success");
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    exportPersonalButton.disabled = false;
  }
}


async function deleteSelectedPersonalTrack() {
  if (!currentNode || currentNode.source !== "personal") return;
  if (!window.confirm(`确定删除个人节点“${currentNode.title}”及其本地音频吗？`)) return;

  deletePersonalButton.disabled = true;
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/personal/${encodeURIComponent(currentNode.id)}`,
      { method: "DELETE" },
    );
    const result = await parseApiResponse(response);
    clearSelectedDetail();
    await refreshGraph();
    setUploadStatus(result.message || "个人节点已删除。", "success");
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    deletePersonalButton.disabled = false;
  }
}


async function resetAllPersonalData() {
  const confirmed = window.confirm(
    "这会删除全部个人节点、本地上传音频和待确认记录。建议先导出。是否继续？",
  );
  if (!confirmed) return;

  resetPersonalButton.disabled = true;
  try {
    const response = await fetch(`${API_BASE_URL}/api/personal/reset`, {
      method: "POST",
    });
    const result = await parseApiResponse(response);
    clearSelectedDetail();
    await refreshGraph();
    setUploadStatus(result.message || "已恢复初始化状态。", "success");
  } catch (error) {
    setUploadStatus(error.message, "error");
  } finally {
    resetPersonalButton.disabled = false;
  }
}


async function loadGraph() {
  if (typeof echarts === "undefined") {
    throw new Error("ECharts 未加载。请检查网络连接或改用本地 ECharts 文件。");
  }
  let graphUrl = "music_graph.json";
  let response = await fetch(graphUrl);
  if (!response.ok) {
    graphUrl = "music_graph.example.json";
    response = await fetch(graphUrl);
  }
  if (!response.ok) {
    throw new Error(`星图数据加载失败 (${response.status})`);
  }

  graphData = await response.json();
  console.info(`Loaded Music Galaxy graph: ${graphUrl}`);
  chart = echarts.init(chartElement, null, { renderer: "canvas" });
  if (topKSlider) topKSlider.value = String(DEFAULT_TOP_K);
  if (topKValue) topKValue.textContent = String(DEFAULT_TOP_K);

  populateGenreFilter();

  chart.on("click", (params) => {
    if (params.dataType === "node") {
      selectedNodeId = String(params.data.id);
      showDetail(params.data);
    }
  });
  window.addEventListener("resize", () => {
    chart.resize();
    if (vizOverlay && !vizOverlay.classList.contains("hidden")) resizeVizCanvas();
  });
  genreFilter.addEventListener("change", renderGraph);
  sourceFilter.addEventListener("change", renderGraph);
  const updateTopK = () => {
    topKValue.textContent = topKSlider.value;
    renderGraph();

    if (selectedNodeId) {
      const selectedNode = graphData.nodes.find(
        (node) => String(node.id) === String(selectedNodeId),
      );
      if (selectedNode) showDetail(selectedNode);
    }
  };
  topKSlider?.addEventListener("input", updateTopK);
  topKSlider?.addEventListener("change", updateTopK);
  resetButton.addEventListener("click", () => {
    genreFilter.value = "all";
    sourceFilter.value = "all";
    if (topKSlider) topKSlider.value = String(DEFAULT_TOP_K);
    if (topKValue) topKValue.textContent = String(DEFAULT_TOP_K);
    selectedNodeId = null;
    renderGraph();
  });
  chooseAudioButton?.addEventListener("click", () => audioUploadInput?.click());
  audioUploadInput?.addEventListener("change", () => {
    uploadPersonalAudio(audioUploadInput.files?.[0]);
  });
  uploadDropzone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    uploadDropzone.classList.add("drag-over");
  });
  uploadDropzone?.addEventListener("dragleave", () => {
    uploadDropzone.classList.remove("drag-over");
  });
  uploadDropzone?.addEventListener("drop", (event) => {
    event.preventDefault();
    uploadDropzone.classList.remove("drag-over");
    uploadPersonalAudio(event.dataTransfer.files?.[0]);
  });
  pendingGenreSelect?.addEventListener("change", () => {
    unknownGenreNote.classList.toggle("hidden", pendingGenreSelect.value !== "Unknown");
  });
  confirmGenreButton?.addEventListener("click", confirmPersonalGenre);
  cancelGenreButton?.addEventListener("click", cancelPendingUpload);
  btnPlay?.addEventListener("click", () => {
    if (currentNode) playTrack(currentNode);
  });
  vizClose?.addEventListener("click", closeVisualizer);
  vizPlay?.addEventListener("click", () => {
    if (currentNode) playTrack(currentNode);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && vizOverlay && !vizOverlay.classList.contains("hidden")) {
      closeVisualizer();
    }
  });
  exportPersonalButton?.addEventListener("click", downloadPersonalExport);
  resetPersonalButton?.addEventListener("click", resetAllPersonalData);
  deletePersonalButton?.addEventListener("click", deleteSelectedPersonalTrack);

  loadingElement.remove();
  renderGraph();
}

loadGraph().catch((error) => {
  loadingElement.classList.add("error");
  loadingElement.innerHTML = `
    <div>
      <strong>星图加载失败</strong><br>
      ${escapeHtml(error.message)}<br>
      请在 web 目录运行 <code>python -m http.server 8000</code>，再访问
      <code>http://localhost:8000</code>。
    </div>
  `;
  console.error(error);
});

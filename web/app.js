const chartElement = document.getElementById("music-graph");
const loadingElement = document.getElementById("loading");
const genreFilter = document.getElementById("genre-filter");
const sourceFilter = document.getElementById("source-filter");
const resetButton = document.getElementById("reset-filter");

let chart;
let graphData;

const genreColors = [
  "#8d7bff", "#52d5ff", "#ff7bb0", "#ffc66b",
  "#5ce1a4", "#ff835c", "#6f9dff", "#d884ff", "#a8d65d",
];

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
    return `
      <strong>相似关系</strong><br>
      相似度：${Number(params.data.value).toFixed(3)}
    `;
  }
  const node = params.data;
  return `
    <strong>${escapeHtml(node.title)}</strong><br>
    ${escapeHtml(node.artist)} · ${escapeHtml(node.genre)}<br>
    来源：${escapeHtml(node.source)}<br>
    BPM：${Number(node.tempo).toFixed(1)}<br>
    Energy：${Number(node.energy).toFixed(3)}
  `;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function renderGraph() {
  const genre = genreFilter.value;
  const source = sourceFilter.value;
  const nodes = graphData.nodes
    .filter((node) => genre === "all" || node.genre === genre)
    .filter((node) => source === "all" || node.source === source)
    .map((node) => ({ ...node, itemStyle: nodeStyle(node) }));
  const visibleIds = new Set(nodes.map((node) => node.id));
  const links = graphData.links.filter(
    (link) => visibleIds.has(String(link.source)) && visibleIds.has(String(link.target)),
  );

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
          type: "graph",
          layout: "force",
          data: nodes,
          links,
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
    true,
  );

  document.getElementById("track-count").textContent = nodes.length;
  document.getElementById("edge-count").textContent = links.length;
  document.getElementById("genre-count").textContent =
    new Set(nodes.map((node) => node.genre)).size;
}

function showDetail(node) {
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

  const list = document.getElementById("recommendation-list");
  const recommendations = graphData.recommendations[node.id] || [];
  list.innerHTML = recommendations.map((item) => `
    <li>
      <b title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</b>
      <small>${escapeHtml(item.artist)} · ${escapeHtml(item.genre)}</small>
      <em>${(Number(item.similarity) * 100).toFixed(1)}%</em>
    </li>
  `).join("");
}

async function loadGraph() {
  if (typeof echarts === "undefined") {
    throw new Error("ECharts 未加载。请检查网络连接或改用本地 ECharts 文件。");
  }
  const response = await fetch("music_graph.json");
  if (!response.ok) {
    throw new Error(`music_graph.json 加载失败 (${response.status})`);
  }
  graphData = await response.json();
  chart = echarts.init(chartElement, null, { renderer: "canvas" });

  graphData.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.name;
    option.textContent = category.name;
    genreFilter.appendChild(option);
  });

  chart.on("click", (params) => {
    if (params.dataType === "node") showDetail(params.data);
  });
  window.addEventListener("resize", () => chart.resize());
  genreFilter.addEventListener("change", renderGraph);
  sourceFilter.addEventListener("change", renderGraph);
  resetButton.addEventListener("click", () => {
    genreFilter.value = "all";
    sourceFilter.value = "all";
    renderGraph();
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
      请在 web 目录运行 <code>python -m http.server 8000</code>，再访问
      <code>http://localhost:8000</code>。
    </div>
  `;
  console.error(error);
});


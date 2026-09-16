(function initMusicGraphUtils(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.MusicGraphUtils = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createMusicGraphUtils() {
  function buildVisibleLinks(graphData, visibleIds, topK) {
    if (graphData.recommendations) {
      const links = [];
      const seen = new Set();

      graphData.nodes.forEach((node) => {
        const source = String(node.id);
        if (!visibleIds.has(source)) return;

        const recs = graphData.recommendations?.[source] || [];
        recs.slice(0, topK).forEach((rec) => {
          const target = String(rec.id);
          if (!visibleIds.has(target)) return;

          const key = [source, target].sort().join("__");
          if (seen.has(key)) return;
          seen.add(key);

          links.push({
            source,
            target,
            value: Number(rec.similarity || 0),
          });
        });
      });

      return links;
    }

    return (graphData.links || [])
      .filter((link) => visibleIds.has(String(link.source)) && visibleIds.has(String(link.target)))
      .sort((a, b) => Number(b.value || 0) - Number(a.value || 0))
      .slice(0, visibleIds.size * topK);
  }

  return { buildVisibleLinks };
});

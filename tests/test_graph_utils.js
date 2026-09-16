const test = require("node:test");
const assert = require("node:assert/strict");

const { buildVisibleLinks } = require("../web/graph_utils.js");

const graphData = {
  nodes: [{ id: "a" }, { id: "b" }, { id: "c" }],
  recommendations: {
    a: [
      { id: "b", similarity: 0.9 },
      { id: "c", similarity: 0.8 },
    ],
    b: [
      { id: "a", similarity: 0.9 },
      { id: "c", similarity: 0.7 },
    ],
    c: [
      { id: "a", similarity: 0.8 },
      { id: "b", similarity: 0.7 },
    ],
  },
};

test("Top-K changes the visible edge set", () => {
  const ids = new Set(["a", "b", "c"]);
  const topOne = buildVisibleLinks(graphData, ids, 1);
  const topTwo = buildVisibleLinks(graphData, ids, 2);

  assert.equal(topOne.length, 2);
  assert.equal(topTwo.length, 3);
  assert.ok(topTwo.length > topOne.length);
});

test("filtered nodes never leak into visible edges", () => {
  const ids = new Set(["a", "b"]);
  const links = buildVisibleLinks(graphData, ids, 2);

  assert.deepEqual(links, [{ source: "a", target: "b", value: 0.9 }]);
});

test("undirected duplicates are removed", () => {
  const ids = new Set(["a", "b", "c"]);
  const links = buildVisibleLinks(graphData, ids, 2);
  const keys = links.map((link) => [link.source, link.target].sort().join("__"));

  assert.equal(keys.length, new Set(keys).size);
});

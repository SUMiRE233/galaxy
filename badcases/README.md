# Badcase and regression suite

No private audio or identifying metadata belongs in this directory. Each case
must use synthetic/public identifiers or a redacted description.

## BC-001: Top-K slider appeared to have no effect

**Failure:** Changing Top-K did not visibly change the graph.

**Root cause:** The frontend rendered a precomputed global link collection
instead of reconstructing the visible edge set from per-node ranked neighbors.

**Fix:** Build visible links from `recommendations`, apply the selected K per
visible node, and deduplicate undirected pairs.

**Expected behavior:** Top-1, Top-5, and Top-20 produce different valid edge sets.

**Regression control:** `tests/test_graph_utils.js`.

## BC-002: Uploaded personal track was not playable

**Failure:** A successfully processed personal node did not expose playback.

**Root cause:** The audio path was missing from one stage of the shared schema.

**Fix:** Preserve the project-relative path through feature rows, merged data,
graph nodes, and the local audio endpoint.

**Expected behavior:** A valid personal node has a safe project-relative audio
path and the player is shown.

**Regression control:** Server upload/path tests; a public audio integration
fixture is still needed before claiming codec coverage.

## BC-003: GTZAN nodes had empty playback paths

**Failure:** Imported GTZAN nodes could not be played even when local WAV files existed.

**Root cause:** The precomputed feature importer did not resolve feature
filenames back to the optional local genre directory.

**Fix:** Resolve candidate paths under the GTZAN audio root and emit only
project-relative paths.

**Expected behavior:** Existing audio resolves; absent audio produces an empty
path without pretending playback is available.

**Regression control:** `tests/test_gtzan_import.py`.

## BC-004: Cross-source feature-space separation

**Failure:** Historical diagnostics showed almost no GTZAN-to-other-source
neighbors, which can undermine the personal-to-library comparison.

**Root cause:** Historical GTZAN precomputed statistics and locally extracted
personal features did not share a proven extraction implementation. The retired
FMA data was also unrecoverable, so that historical mixed graph cannot be used
as a reproducible evaluation baseline.

**Fix:** GTZAN is now re-extracted from restored WAV files with the same
`extract_audio_features` implementation used for personal uploads. The FMA
chain was removed. A real cross-source retrieval claim remains deferred until a
frozen, non-private personal query set exists.

**Expected behavior:** Cross-source behavior is reported and justified; it is
never inferred from a synthetic demo or an unreproducible historical artifact.

**Regression risk:** Any per-source normalization may improve mixing while
damaging actual similarity, so it requires frozen human evaluation before adoption.

## BC-005: One restored GTZAN WAV cannot be decoded

**Failure:** Full extraction produced 999 feature rows from 1000 WAV files.

**Affected public identifier:** `jazz/jazz.00054.wav`.

**Root cause:** The restored file cannot be decoded by the current local audio
stack. The pipeline catches the per-file exception and continues instead of
discarding the other 999 valid tracks.

**Expected behavior:** The output contains 999 unique GTZAN IDs, jazz contains
99 nodes, every emitted node has a project-relative playback path, and no
personal node is present after a clean rebuild.

**Regression control:** `tests/test_gtzan_import.py` covers per-file failure
isolation with a mocked extractor; the local full-data validation records the
999-row result in `evaluation/results/gtzan_similarity.json`.

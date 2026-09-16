# Music Galaxy — Final Project Audit

Audit date: 2026-09-16
Repository: `https://github.com/SUMiRE233/galaxy`
Release branch: `main`
Final status: complete; feature expansion stopped.

## 1. Current definition

Music Galaxy is an AI-assisted course-project MVP for local music-similarity
exploration. It converts audio metadata and 18 aggregate audio features into a
Top-K cosine-similarity graph, then renders the result as an interactive ECharts
force graph.

It is not a trained classifier, collaborative recommender, online recognition
service, or claim of subjective musical understanding.

## 2. Current architecture

```text
deterministic demo ─┐
restored GTZAN WAV ─┼─> unified feature schema
personal audio ─────┘       │
                            v
                      StandardScaler
                            │
                            v
                     cosine similarity
                            │
                            v
                    per-node Top-K graph
                            │
                            v
                 static ECharts web client

personal upload/export/delete/reset <-> local FastAPI service
```

Supported sources are `demo`, `gtzan`, and `personal`. The unrecoverable FMA
chain has been retired from extraction, merging, API validation, and frontend
filters.

## 3. Data and reproducibility boundary

- Git contains a deterministic synthetic feature fixture and sanitized browser graph.
- Raw audio, personal metadata, generated feature tables, and generated local graph files are ignored.
- `web/music_graph.example.json` contains 30 demo nodes, zero personal nodes, and zero audio paths.
- The restored local GTZAN collection contains 1000 WAV files across 10 genres.
- `jazz/jazz.00054.wav` cannot be decoded by the current local stack; the valid frozen feature table therefore contains 999 unique tracks.
- The current generated local graph contains 999 GTZAN nodes, 14,368 links, Top-K 20, zero personal nodes, and 999 project-relative playback paths.
- The owner used local personal audio to validate the deletion lifecycle. No personal audio remains in the repository working data, public fixture, or Git.

## 4. Personal-data lifecycle

The local service now supports:

- ZIP export of personal features, metadata, pending records, and local audio;
- deletion of one selected personal node and its corresponding audio;
- reset of all personal nodes, pending records, and personal audio;
- snapshot-and-rollback of affected CSV/JSON files when graph rebuilding fails;
- audio deletion only after a successful rebuild;
- cancellation and cleanup of an unconfirmed upload.

The export is a private backup artifact. Automatic import/restore is not yet implemented.

## 5. Verification evidence

### Automated tests

- Python unit/integration tests: 30 passing after the frozen-evaluation and annotation-preview tests were added.
- Frontend graph utility tests: 3 passing.
- Python compilation and JavaScript syntax checks pass.
- The demo pipeline runs in a clean temporary workspace.
- Upload validation, path traversal rejection, pending-upload cancellation,
  personal export, one-node deletion, and reset are covered with temporary data.

### Browser validation

A headless Edge run loaded the generated 999-node graph. Export, reset, and
delete controls and their handlers were present; no page or console errors were
reported. ECharts was replaced with a minimal test double only to avoid a CDN
dependency in the local validation environment.

The owner subsequently completed an interactive local acceptance test covering
server startup, personal-audio upload, playback, selected-node deletion, graph
refresh, and reset. The workflow behaved as documented and the test personal
audio was removed.

### Engineering benchmark

| Tracks | Build time | Peak RSS | JSON size |
|---:|---:|---:|---:|
| 100 | 0.31 s | 142 MiB | 0.32 MiB |
| 1000 | 3.27 s | 163 MiB | 3.29 MiB |
| 5000 | 16.29 s | 403 MiB | 16.74 MiB |

The local stop threshold is 5000 tracks in under 30 seconds and under 512 MiB.
The current dense implementation passes, so approximate-neighbor infrastructure
is intentionally out of scope.

## 6. Similarity evaluation

### Structural proxy result

The 999-track GTZAN feature table produced the following Top-5 results:

| Method | Same-genre Precision@5 | Same-genre NDCG@5 |
|---|---:|---:|
| Standardized cosine | 0.498298 | 0.516958 |
| Unscaled cosine | 0.361161 | 0.379144 |
| Seeded random | 0.100701 | 0.101479 |

These are genre-structure proxies, not evidence of subjective similarity.

### Frozen human-evaluation package

`evaluation/frozen/gtzan_human_v2/` is frozen with:

- dataset SHA-256 recorded in the manifest;
- seed 42;
- 10 queries, exactly 1 per genre;
- standardized cosine and seeded-random baseline;
- Top-3 per method, 60 retrieval rows and 60 audible pairs;
- an annotation template containing no method, track ID, genre, or path;
- separate playback and retrieval keys;
- generator hash and dependency versions.

The scorer supports missing labels and `NA`; multi-annotator agreement remains
available but is not required for this owner-only review. The owner completed
all 60 blinded comparisons with no `NA` labels. Standardized cosine reached
Precision@3 `0.733333`, versus `0.200000` for seeded random (absolute difference
`+0.533333`; 3.67x the baseline). The aggregate, hash-linked result is stored in
`evaluation/results/human_similarity.json`; private row-level labels remain in
the ignored local annotation directory.

## 7. Badcases and important iterations

1. **Top-K appeared ineffective.** The frontend used a global deduplicated edge
   collection. It now reconstructs visible edges from each node's ranked
   recommendations, with JavaScript regression tests.
2. **Uploaded personal nodes were not playable.** The project-relative path was
   missing or stale at one pipeline stage. Path preservation and safe audio
   serving are now tested.
3. **GTZAN playback paths were empty.** The old importer wrote an empty path.
   Raw GTZAN extraction now emits real project-relative paths.
4. **Cross-source feature mismatch.** GTZAN previously depended on external
   precomputed statistics while personal audio used the common extractor.
   Restored GTZAN WAV is now processed by the same implementation.
5. **Corrupt GTZAN sample.** `jazz.00054.wav` is isolated and skipped without
   discarding the remaining 999 valid tracks.
6. **Frontend personal controls were syntactically valid but incorrectly
   scoped.** Browser-level validation found and fixed the runtime scope and CSS
   boundary errors that `node --check` could not detect.

## 8. Repository and privacy audit

Current-tree controls:

- generated and private data are ignored;
- tracked generated graphs and personal metadata are staged for removal;
- the public fixture has no personal nodes or audio paths;
- no current tracked FMA path remains;
- no common API-key/private-key signature was found in current Git history;
- no audio blob is present in Git history.

The redacted machine-readable evidence is saved at
`evaluation/results/git_history_privacy_audit.json` and can be regenerated with
`scripts/12_audit_git_history.py`.

Historical privacy finding and owner decision:

- commits `b4182dbd`, `a11e5839`, and `68d42f10` each contain two personal nodes
  with non-empty title, artist, and relative path in `web/music_graph.json`;
- the same commits contain two rows in `data/raw/personal/personal_tracks.csv`;
- removing these files in the next commit does not remove them from old commits;
- the owner decided not to rewrite published history and accepts retaining these
  historical records as regression evidence for the personal-deletion lifecycle;
- active deletion tests continue to use equivalent synthetic metadata so the
  real titles are not copied back into the current tree or test output.

## 9. Defensible project story

### 30-second version

Music Galaxy is an AI-assisted local music-similarity visualization project. I
defined a unified audio-feature schema, used standardized cosine similarity to
build per-track Top-K relationships, and rendered them as an interactive force
graph. I hardened the original prototype with deterministic public fixtures,
tests, performance and similarity baselines, restored GTZAN extraction, and a
safe local lifecycle for exporting or deleting personal data.

### Contribution boundary

Large portions of implementation were generated or revised with Codex. The
user contribution is best represented by problem framing, architecture and
privacy constraints, rejection of unsafe replacements, debugging across data
and frontend boundaries, validation design, and acceptance criteria. The
project should be described as AI-assisted development, not fully hand-written
independent implementation.

## 10. Known limitations

- Aggregate handcrafted features are only an interpretable baseline.
- The human result is based on one owner, 10 queries, and 3 retrieved tracks per method; it does not measure inter-rater agreement or population-level preference.
- The frozen evaluation currently uses one dataset/source and cannot establish cross-source quality.
- One GTZAN WAV is undecodable.
- Upload extraction is synchronous and intended for small local use.
- Dense pairwise cosine is O(n²), intentionally capped by the tested 5000-track scope.
- ECharts is loaded from a CDN in normal browser use.
- Personal export has no automatic import/restore path.
- Published Git history intentionally retains historical personal metadata by owner decision.
- Project-authored code and documentation use the MIT License. Dataset audio,
  personal audio, generated private annotations, dependencies, and third-party
  assets are not relicensed by it.

## 11. Stop condition and final disposition

Engineering implementation is feature-complete. Do not add accounts, cloud
services, deep recommendation models, or a database.

The stop condition is satisfied:

1. deterministic public fixture and documented Quick Start are available;
2. Python and JavaScript regression suites pass;
3. the 5000-track benchmark is below the time and memory thresholds;
4. structural and frozen owner-judged similarity results are recorded;
5. personal-data deletion received automated and manual acceptance coverage;
6. privacy boundaries and the historical-metadata decision are documented;
7. the MIT license decision is recorded;
8. the final release is published from `main` and verified from a clean clone.

Future work is maintenance only unless a new, explicitly versioned evaluation
question justifies reopening development.

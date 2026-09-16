# Final Publication Decisions

All previously deferred owner decisions have been resolved. This file preserves
the final decisions as release evidence; no approval item remains open.

## 1. Recorded decision: keep public Git history

Read-only evidence:

- commits `b4182dbd`, `a11e5839`, and `68d42f10` each contain two personal nodes
  with non-empty title, artist, and relative path in `web/music_graph.json`;
- those commits also contain two rows in `data/raw/personal/personal_tracks.csv`;
- Git history contains no tracked audio blob;
- the common credential-signature scan found no potential secret path.

The owner decided not to rewrite history. Historical records may remain as
regression evidence for the personal-deletion lifecycle. Current automated
tests use equivalent synthetic metadata and do not copy real titles into the
working tree. No force-push is planned.

## 2. Recorded result: owner listening complete

All 60 frozen pairs were labeled by the owner with no `NA` values. Standardized
cosine Precision@3 is `0.733333`, versus `0.200000` for seeded random. The
aggregate result is recorded in `evaluation/results/human_similarity.json`;
private row-level labels remain ignored.

## 3. Recorded result: personal-data lifecycle accepted

The owner manually tested local server startup, upload, playback, selected-node
deletion, graph refresh, and reset. The workflow behaved normally and no test
personal audio remains in the repository data.

## 4. Recorded decision: MIT license

The owner selected the MIT License for project-authored code and documentation.
Dataset audio, personal audio, private annotations, dependencies, and
third-party assets retain their own terms.

## 5. Recorded decision: publish the final version

The owner approved final verification, an Angular Conventional Commit, push to
the configured `origin`, and clean-clone verification. History rewriting remains
explicitly rejected. A release tag is optional and is not part of this final
publication request.

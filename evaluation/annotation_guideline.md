# Human Similarity Annotation Guideline

## Purpose

Measure whether Music Galaxy's frozen Top-3 neighbors are audibly useful for local
similarity exploration. This is the primary quality evaluation. Genre-based
metrics remain secondary structural proxies.

## Frozen set

- Package: `evaluation/frozen/gtzan_human_v2/`
- 10 queries, 1 per GTZAN genre
- 2 hidden methods (standardized cosine and random), Top-3 each
- 60 retrieval rows and 60 audible pairs
- Dataset, artifact, generator, environment, and seed information are recorded in `manifest.json`

Once labeling begins, do not regenerate or edit the frozen package.

## Blinding

- Listeners receive only an opaque `pair_id` and two audio clips.
- Hide method, rank, filename, track ID, genre, and source metadata.
- `playback_index.csv` and `retrieval_key.csv` are coordinator-only files.
- Randomize presentation using the order already frozen in `pairs.csv`.

## Labels

- `1` — similar: the pair shares at least two salient audible dimensions, such
  as rhythm/tempo feel, energy/dynamics, timbre/instrumentation, or overall style.
- `0` — not similar: the transition is clearly inconsistent on most salient dimensions.
- `NA` — cannot judge: missing/corrupt audio, severe quality mismatch, or genuine ambiguity.

Artist identity, filename, popularity, album, and genre text must not determine
the label. Listen to audio rather than infer from metadata.

Optional confidence uses `1` (low), `2` (medium), or `3` (high). Notes should be
short and must not include personal information.

## Listening protocol

1. Use the same headphones/speakers and roughly constant volume.
2. Listen to enough of both clips to judge; do not rely only on the first transient.
3. Judge overall exploration usefulness, not whether the tracks are identical.
4. Enter one label for every `pair_id`; use `NA` instead of guessing.
5. Do not inspect neighboring pairs, methods, genres, or filenames while deciding.
6. Double-click `start_evaluation.cmd` for the intended blinded interface.

## Multiple annotators and adjudication

- Use a stable, non-identifying `annotator_id`.
- This v2 evaluation is explicitly owner-only; a second annotator is not required.
- Keep original labels; do not overwrite disagreement rows.
- Add a new row with `annotator_id=adjudicated` for every disagreement.
- Report raw agreement and the number of adjudicated pairs.

## Metrics

Primary: owner-labeled standardized-cosine Precision@3.

Secondary:

- valid-label and pair-label coverage;
- raw unanimous agreement only if a second annotator is added later;
- seeded-random baseline;
- complete-query Precision@3;
- per-genre slices;
- structural same-genre Precision@5 and NDCG@5;
- `NA` and unresolved-disagreement counts.

## Freeze and iteration rule

The v1 set is final evaluation data. Do not tune feature weights or thresholds
from individual v1 examples. Any later algorithm change must replay the whole
package and save a new immutable result. A deliberately changed dataset or
sampling protocol must use a new version directory instead of overwriting v1.

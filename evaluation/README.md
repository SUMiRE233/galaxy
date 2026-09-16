# Evaluation

Music Galaxy separates engineering validation, structural proxy metrics, and
human-judged similarity. Node counts, passing tests, and HTTP 200 responses are
engineering evidence; they are not similarity-quality metrics.

## 1. Graph benchmark

Run:

```powershell
python scripts/08_benchmark_graph.py --sizes 100 1000 5000 --top-k 20 --seed 42
```

The saved manifest records the Git state, platform, seed, elapsed time, sampled
RSS, estimated dense-matrix size, and serialized graph size.

Current local baseline:

| Tracks | Build time | Peak RSS | JSON size |
|---:|---:|---:|---:|
| 100 | 0.31 s | 142 MiB | 0.32 MiB |
| 1000 | 3.27 s | 163 MiB | 3.29 MiB |
| 5000 | 16.29 s | 403 MiB | 16.74 MiB |

## 2. Structural proxy evaluation

Run:

```powershell
python scripts/09_evaluate_similarity.py data/processed/gtzan_features.csv `
  --top-k 5 --seed 42 `
  --output evaluation/results/gtzan_similarity.json
```

This compares standardized cosine, unscaled cosine, and seeded random
neighbors. Same-genre Precision@K and NDCG@K are structural proxies only. They
must not be described as subjective music-similarity accuracy.

Current 999-track GTZAN Top-5 proxy:

| Method | Precision@5 | NDCG@5 |
|---|---:|---:|
| Standardized cosine | 0.498298 | 0.516958 |
| Unscaled cosine | 0.361161 | 0.379144 |
| Random | 0.100701 | 0.101479 |

## 3. Compact owner review

The final quality metric is owner-judged Precision@3. Version 2 is frozen at:

```text
evaluation/frozen/gtzan_human_v2/
├── manifest.json
├── pairs.csv
├── playback_index.csv
├── retrieval_key.csv
└── labels_template.csv
```

Properties:

- 10 stratified GTZAN queries, 1 per genre;
- standardized cosine versus seeded random;
- 2 methods × Top-3 = 60 retrieval rows and 60 audible pairs;
- seed, dataset hash, generator hash, environment, and artifact hashes recorded;
- `pairs.csv` and `labels_template.csv` reveal no method, track ID, genre, or path;
- method and playback information are separate coordinator-only files.

Regenerate only when intentionally creating a new evaluation version:

```powershell
python scripts/10_freeze_human_evaluation.py `
  data/processed/gtzan_features.csv `
  --output-dir evaluation/frozen/gtzan_human_v2 `
  --query-count 10 --top-k 3 --seed 42 `
  --methods standardized_cosine random
```

The command refuses to overwrite an existing frozen package unless `--force`
is explicitly supplied. Do not overwrite v1 after annotation begins.

## 4. Annotation boundary

Copy the template to a private ignored location before entering labels:

```powershell
New-Item -ItemType Directory -Force evaluation/local_annotations
Copy-Item evaluation/frozen/gtzan_human_v2/labels_template.csv `
  evaluation/local_annotations/annotator_1.csv
```

The owner can instead double-click `start_evaluation.cmd`. It opens a local,
blinded page with two audio players, keyboard shortcuts, progress, confidence,
and optional notes. Labels are saved atomically under the ignored
`evaluation/local_annotations/` directory.

Use `0`, `1`, or `NA` according to `annotation_guideline.md`. The page hides
IDs, filenames, genre, method, and rank. Do not edit `retrieval_key.csv` or the
frozen package.

This v2 review is owner-only. The scorer retains optional multi-annotator and
adjudication support, but no second annotator is required.

## 5. Scoring

```powershell
python scripts/11_score_human_evaluation.py `
  evaluation/frozen/gtzan_human_v2 `
  evaluation/local_annotations/annotator_1.csv `
  --output evaluation/results/human_similarity.json
```

The scorer reports label coverage, agreement, unresolved disagreements,
per-method Precision@3, complete-query Precision@3, and per-genre slices. It
sets `primary_metric_ready` only after every frozen pair has a label and all
disagreements are adjudicated. `NA` is reported and excluded from precision
denominators.

## 6. Repository privacy audit

Run:

```powershell
python scripts/12_audit_git_history.py `
  --output evaluation/results/git_history_privacy_audit.json
```

The report scans every reachable commit for personal graph/metadata records,
tracked audio paths, and a conservative set of common credential signatures.
It reports counts and paths but deliberately omits personal title and artist
values. Signature scanning is useful evidence, not proof that no secret exists.

## 7. Final owner result

The owner completed all 60 blinded comparisons. Coverage is `60/60`, with no
`NA` labels or unresolved disagreements. Standardized cosine reached
Precision@3 `0.733333`; seeded random reached `0.200000`. The absolute
difference is `+0.533333`, and standardized cosine is 3.67x the baseline.

The aggregate result and input hashes are stored in
`results/human_similarity.json`. Row-level labels remain private and ignored.
Because this is a 10-query, single-owner evaluation, it supports the local
course-project conclusion but does not establish inter-rater agreement or broad
listener preference. The retired FMA chain and private personal audio are not
part of this evaluation.

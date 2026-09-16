from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from common import NUMERIC_FEATURE_COLUMNS, PROJECT_ROOT


METHODS = ("standardized_cosine", "unscaled_cosine", "random")
PACKAGE_VERSION = 1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state() -> dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"commit": commit or None, "dirty": bool(dirty)}


def validate_frame(frame: pd.DataFrame, query_count: int, top_k: int) -> pd.DataFrame:
    required = {"id", "genre", "source", "path", *NUMERIC_FEATURE_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Evaluation input is missing columns: {missing}")
    if query_count < 1:
        raise ValueError("query_count must be at least 1.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if len(frame) <= top_k:
        raise ValueError("Evaluation input must contain more tracks than top_k.")
    if query_count > len(frame):
        raise ValueError("query_count cannot exceed the number of tracks.")

    result = frame.copy().reset_index(drop=True)
    result["id"] = result["id"].astype(str)
    if result["id"].duplicated().any():
        raise ValueError("Evaluation track IDs must be unique.")
    if result["path"].fillna("").astype(str).str.strip().eq("").any():
        raise ValueError("Human evaluation requires a playback path for every track.")
    return result


def select_query_indices(frame: pd.DataFrame, query_count: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    by_genre: dict[str, list[int]] = {}
    for genre, group in frame.groupby(frame["genre"].fillna("Unknown").astype(str), sort=True):
        indices = group.index.to_numpy(dtype=int, copy=True)
        rng.shuffle(indices)
        by_genre[genre] = indices.tolist()

    selected: list[int] = []
    genres = sorted(by_genre)
    while len(selected) < query_count:
        progressed = False
        for genre in genres:
            if by_genre[genre] and len(selected) < query_count:
                selected.append(by_genre[genre].pop())
                progressed = True
        if not progressed:
            break
    if len(selected) != query_count:
        raise ValueError("Unable to select the requested number of query tracks.")
    return selected


def compute_rankings(
    frame: pd.DataFrame,
    query_indices: list[int],
    top_k: int,
    seed: int,
) -> dict[str, dict[int, list[int]]]:
    numeric = frame[NUMERIC_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(numeric.median()).fillna(0.0).to_numpy(dtype=float)
    standardized = StandardScaler().fit_transform(numeric)
    standardized_scores = cosine_similarity(standardized)
    unscaled_scores = cosine_similarity(numeric)
    np.fill_diagonal(standardized_scores, -np.inf)
    np.fill_diagonal(unscaled_scores, -np.inf)

    rankings: dict[str, dict[int, list[int]]] = {
        "standardized_cosine": {},
        "unscaled_cosine": {},
        "random": {},
    }
    for query_index in query_indices:
        rankings["standardized_cosine"][query_index] = np.argsort(
            -standardized_scores[query_index], kind="stable"
        )[:top_k].tolist()
        rankings["unscaled_cosine"][query_index] = np.argsort(
            -unscaled_scores[query_index], kind="stable"
        )[:top_k].tolist()

    rng = np.random.default_rng(seed + 1)
    all_indices = np.arange(len(frame))
    for query_index in query_indices:
        candidates = all_indices[all_indices != query_index]
        rankings["random"][query_index] = rng.choice(
            candidates,
            size=top_k,
            replace=False,
        ).tolist()
    return rankings


def build_package(
    frame: pd.DataFrame,
    query_count: int = 30,
    top_k: int = 5,
    seed: int = 42,
    methods: tuple[str, ...] = METHODS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    frame = validate_frame(frame, query_count=query_count, top_k=top_k)
    unknown_methods = sorted(set(methods) - set(METHODS))
    if unknown_methods:
        raise ValueError(f"Unsupported methods: {unknown_methods}")
    if not methods:
        raise ValueError("At least one evaluation method is required.")
    query_indices = select_query_indices(frame, query_count=query_count, seed=seed)
    rankings = compute_rankings(frame, query_indices, top_k=top_k, seed=seed)

    pair_keys: set[tuple[str, str]] = set()
    raw_key_rows: list[dict[str, object]] = []
    for query_index in query_indices:
        query = frame.iloc[query_index]
        for method in methods:
            for rank, candidate_index in enumerate(rankings[method][query_index], start=1):
                candidate = frame.iloc[candidate_index]
                pair_key = (str(query["id"]), str(candidate["id"]))
                pair_keys.add(pair_key)
                raw_key_rows.append(
                    {
                        "query_id": pair_key[0],
                        "candidate_id": pair_key[1],
                        "query_genre": str(query["genre"]),
                        "method": method,
                        "rank": rank,
                    }
                )

    shuffled_pairs = sorted(pair_keys)
    np.random.default_rng(seed + 2).shuffle(shuffled_pairs)
    pair_ids = {
        pair_key: f"pair_{position:04d}"
        for position, pair_key in enumerate(shuffled_pairs, start=1)
    }

    pairs = pd.DataFrame(
        [
            {"pair_id": pair_ids[pair_key], "presentation_order": position}
            for position, pair_key in enumerate(shuffled_pairs, start=1)
        ]
    )
    frame_by_id = frame.set_index("id", drop=False)
    playback_rows = []
    for query_id, candidate_id in shuffled_pairs:
        playback_rows.append(
            {
                "pair_id": pair_ids[(query_id, candidate_id)],
                "query_id": query_id,
                "candidate_id": candidate_id,
                "query_path": str(frame_by_id.loc[query_id, "path"]),
                "candidate_path": str(frame_by_id.loc[candidate_id, "path"]),
            }
        )
    playback = pd.DataFrame(playback_rows)

    key = pd.DataFrame(raw_key_rows)
    key["pair_id"] = [
        pair_ids[(row["query_id"], row["candidate_id"])] for row in raw_key_rows
    ]
    key = key[["pair_id", "query_id", "candidate_id", "query_genre", "method", "rank"]]
    key = key.sort_values(["method", "query_id", "rank"], kind="stable").reset_index(drop=True)

    labels_template = pairs[["pair_id"]].copy()
    labels_template["annotator_id"] = "annotator_1"
    labels_template["relevance"] = ""
    labels_template["confidence"] = ""
    labels_template["notes"] = ""

    query_genres = frame.iloc[query_indices]["genre"].fillna("Unknown").astype(str)
    manifest = {
        "schema_version": PACKAGE_VERSION,
        "purpose": "frozen_blinded_human_similarity_evaluation",
        "config": {
            "query_count": query_count,
            "top_k": top_k,
            "seed": seed,
            "methods": list(methods),
        },
        "counts": {
            "tracks": len(frame),
            "queries": len(query_indices),
            "retrieval_rows": len(key),
            "unique_pairs_to_label": len(pairs),
        },
        "query_genre_distribution": {
            str(genre): int(count)
            for genre, count in query_genres.value_counts().sort_index().items()
        },
        "blinding": {
            "annotation_file_contains_method": False,
            "annotation_file_contains_track_ids": False,
            "playback_index_must_not_be_shown_to_annotators": True,
        },
    }
    return pairs, playback, key, labels_template, manifest


def write_package(
    input_path: Path,
    output_dir: Path,
    query_count: int,
    top_k: int,
    seed: int,
    methods: tuple[str, ...],
    force: bool,
) -> dict[str, object]:
    targets = {
        "pairs": output_dir / "pairs.csv",
        "playback_index": output_dir / "playback_index.csv",
        "retrieval_key": output_dir / "retrieval_key.csv",
        "labels_template": output_dir / "labels_template.csv",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in targets.values() if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "Frozen package already exists; pass --force only when intentionally creating a new version."
        )

    frame = pd.read_csv(input_path)
    pairs, playback, key, labels_template, manifest = build_package(
        frame,
        query_count=query_count,
        top_k=top_k,
        seed=seed,
        methods=methods,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(targets["pairs"], index=False, encoding="utf-8")
    playback.to_csv(targets["playback_index"], index=False, encoding="utf-8")
    key.to_csv(targets["retrieval_key"], index=False, encoding="utf-8")
    labels_template.to_csv(targets["labels_template"], index=False, encoding="utf-8")

    manifest.update(
        {
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "git": git_state(),
            "dataset": {
                "path": str(input_path),
                "sha256": sha256_file(input_path),
                "usage": "frozen_final_evaluation_only",
            },
            "generator": {
                "path": "scripts/10_freeze_human_evaluation.py",
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "environment": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "artifacts": {
                name: {"path": path.name, "sha256": sha256_file(path)}
                for name, path in targets.items()
                if name != "manifest"
            },
        }
    )
    targets["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a blinded human similarity package.")
    parser.add_argument("input", type=Path, help="Frozen feature CSV with playable tracks.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "frozen" / "gtzan_human_v2",
    )
    parser.add_argument("--query-count", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = write_package(
        args.input,
        args.output_dir,
        query_count=args.query_count,
        top_k=args.top_k,
        seed=args.seed,
        methods=tuple(args.methods),
        force=args.force,
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print(f"Frozen package: {args.output_dir}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from common import NUMERIC_FEATURE_COLUMNS, PROJECT_ROOT


def dataset_hash(path: Path) -> str:
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


def ranking_metrics(
    neighbors: np.ndarray,
    labels: np.ndarray,
    sources: np.ndarray,
) -> dict[str, float]:
    precisions = []
    ndcgs = []
    cross_source_rates = []
    discounts = 1.0 / np.log2(np.arange(neighbors.shape[1]) + 2)

    for query_index, ranked in enumerate(neighbors):
        relevance = (labels[ranked] == labels[query_index]).astype(float)
        precisions.append(float(relevance.mean()))

        relevant_total = int(np.sum(labels == labels[query_index]) - 1)
        ideal_count = min(relevant_total, len(ranked))
        ideal_dcg = float(discounts[:ideal_count].sum())
        dcg = float((relevance * discounts).sum())
        ndcgs.append(dcg / ideal_dcg if ideal_dcg else 0.0)

        cross_source_rates.append(float(np.mean(sources[ranked] != sources[query_index])))

    return {
        "same_genre_precision_at_k": round(float(np.mean(precisions)), 6),
        "same_genre_ndcg_at_k": round(float(np.mean(ndcgs)), 6),
        "cross_source_rate_at_k": round(float(np.mean(cross_source_rates)), 6),
    }


def evaluate(frame: pd.DataFrame, top_k: int = 5, seed: int = 42) -> dict[str, object]:
    if len(frame) < 2:
        raise ValueError("Evaluation requires at least two tracks.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    required = {"genre", "source", *NUMERIC_FEATURE_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Evaluation input is missing columns: {missing}")

    numeric = frame[NUMERIC_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(numeric.median()).fillna(0.0).to_numpy(dtype=float)
    labels = frame["genre"].fillna("Unknown").astype(str).to_numpy()
    sources = frame["source"].fillna("unknown").astype(str).to_numpy()
    effective_k = min(top_k, len(frame) - 1)

    standardized = StandardScaler().fit_transform(numeric)
    standardized_scores = cosine_similarity(standardized)
    unscaled_scores = cosine_similarity(numeric)
    np.fill_diagonal(standardized_scores, -np.inf)
    np.fill_diagonal(unscaled_scores, -np.inf)

    standardized_neighbors = np.argsort(standardized_scores, axis=1)[:, ::-1][:, :effective_k]
    unscaled_neighbors = np.argsort(unscaled_scores, axis=1)[:, ::-1][:, :effective_k]

    rng = np.random.default_rng(seed)
    random_neighbors = np.empty((len(frame), effective_k), dtype=int)
    indices = np.arange(len(frame))
    for query_index in range(len(frame)):
        candidates = indices[indices != query_index]
        random_neighbors[query_index] = rng.choice(candidates, size=effective_k, replace=False)

    return {
        "tracks": len(frame),
        "top_k": effective_k,
        "genres": int(len(np.unique(labels))),
        "sources": sorted(np.unique(sources).tolist()),
        "metrics_are_proxy_only": True,
        "methods": {
            "standardized_cosine": ranking_metrics(standardized_neighbors, labels, sources),
            "unscaled_cosine": ranking_metrics(unscaled_neighbors, labels, sources),
            "random": ranking_metrics(random_neighbors, labels, sources),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Music Galaxy similarity proxy metrics.")
    parser.add_argument("input", type=Path, help="Frozen feature CSV used only for evaluation.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "similarity_evaluation.json",
    )
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    result = {
        "run_id": datetime.now(timezone.utc).strftime("similarity_%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "dataset": {
            "path": str(args.input),
            "sha256": dataset_hash(args.input),
            "usage": "frozen_evaluation_only",
        },
        "config": {"top_k": args.top_k, "seed": args.seed},
        "result": evaluate(frame, top_k=args.top_k, seed=args.seed),
        "limitation": "Same-genre metrics are structural proxies, not subjective similarity ground truth.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["result"], ensure_ascii=False, indent=2))
    try:
        display_path = args.output.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = args.output
    print(f"Saved: {display_path}")


if __name__ == "__main__":
    main()

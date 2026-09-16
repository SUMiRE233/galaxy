from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common import PROJECT_ROOT


VALID_LABELS = {"0", "1", "NA"}


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


def normalize_labels(labels: pd.DataFrame) -> pd.DataFrame:
    required = {"pair_id", "annotator_id", "relevance"}
    missing = sorted(required - set(labels.columns))
    if missing:
        raise ValueError(f"Labels file is missing columns: {missing}")
    result = labels.copy()
    result["pair_id"] = result["pair_id"].astype(str).str.strip()
    result["annotator_id"] = result["annotator_id"].astype(str).str.strip()
    result["relevance"] = result["relevance"].astype(str).str.strip().str.upper()
    result = result[result["relevance"].ne("")].reset_index(drop=True)
    invalid = sorted(set(result["relevance"]) - VALID_LABELS)
    if invalid:
        raise ValueError(f"Unsupported relevance labels: {invalid}")
    if result.duplicated(["pair_id", "annotator_id"]).any():
        raise ValueError("Each annotator may label a pair only once.")
    return result


def resolve_pair_labels(labels: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    labels = normalize_labels(labels)
    resolved_rows = []
    multi_annotator_pairs = 0
    unanimous_pairs = 0
    unresolved_disagreements = 0

    for pair_id, group in labels.groupby("pair_id", sort=True):
        adjudicated = group[group["annotator_id"].str.lower().eq("adjudicated")]
        if len(adjudicated) > 1:
            raise ValueError(f"Pair {pair_id} has multiple adjudicated labels.")
        if len(adjudicated) == 1:
            label = adjudicated.iloc[0]["relevance"]
            resolution = "adjudicated"
        else:
            numeric = group[group["relevance"].isin(["0", "1"])]["relevance"]
            if len(numeric) >= 2:
                multi_annotator_pairs += 1
                if numeric.nunique() == 1:
                    unanimous_pairs += 1
            if len(numeric) and numeric.nunique() == 1:
                label = numeric.iloc[0]
                resolution = "consensus"
            elif len(group) == 1:
                label = group.iloc[0]["relevance"]
                resolution = "single_annotator"
            elif group["relevance"].eq("NA").all():
                label = "NA"
                resolution = "consensus_na"
            else:
                label = "UNRESOLVED"
                resolution = "needs_adjudication"
                unresolved_disagreements += 1
        resolved_rows.append(
            {"pair_id": pair_id, "resolved_label": label, "resolution": resolution}
        )

    agreement = (
        round(unanimous_pairs / multi_annotator_pairs, 6)
        if multi_annotator_pairs
        else None
    )
    resolved = pd.DataFrame(
        resolved_rows,
        columns=["pair_id", "resolved_label", "resolution"],
    )
    return resolved, {
        "multi_annotator_pairs": multi_annotator_pairs,
        "raw_unanimous_agreement": agreement,
        "unresolved_disagreements": unresolved_disagreements,
    }


def score(key: pd.DataFrame, labels: pd.DataFrame) -> dict[str, object]:
    required = {"pair_id", "query_id", "query_genre", "method", "rank"}
    missing = sorted(required - set(key.columns))
    if missing:
        raise ValueError(f"Retrieval key is missing columns: {missing}")
    resolved, agreement = resolve_pair_labels(labels)
    merged = key.merge(resolved, on="pair_id", how="left")
    merged["resolved_label"] = merged["resolved_label"].fillna("MISSING")

    all_pair_ids = set(key["pair_id"].astype(str))
    supplied_pair_ids = set(normalize_labels(labels)["pair_id"].astype(str))
    unknown_pair_ids = sorted(supplied_pair_ids - all_pair_ids)
    if unknown_pair_ids:
        raise ValueError(f"Labels contain unknown pair IDs: {unknown_pair_ids[:5]}")

    methods: dict[str, object] = {}
    for method, method_rows in merged.groupby("method", sort=True):
        numeric = method_rows[method_rows["resolved_label"].isin(["0", "1"])].copy()
        numeric["relevance"] = numeric["resolved_label"].astype(int)
        per_query = numeric.groupby("query_id").agg(
            judged=("relevance", "size"),
            relevant=("relevance", "sum"),
        )
        expected_per_query = int(method_rows.groupby("query_id").size().max())
        per_query["precision"] = per_query["relevant"] / per_query["judged"]
        complete = per_query[per_query["judged"].eq(expected_per_query)]

        genre_metrics = {}
        for genre, genre_rows in numeric.groupby("query_genre", sort=True):
            genre_metrics[str(genre)] = {
                "valid_pairs": int(len(genre_rows)),
                "precision": round(float(genre_rows["relevance"].mean()), 6),
            }
        methods[str(method)] = {
            "retrieval_rows": int(len(method_rows)),
            "valid_labeled_rows": int(len(numeric)),
            "valid_label_coverage": round(len(numeric) / len(method_rows), 6),
            "precision_at_k_valid_labels": (
                round(float(numeric["relevance"].mean()), 6) if len(numeric) else None
            ),
            "mean_query_precision_on_valid_labels": (
                round(float(per_query["precision"].mean()), 6) if len(per_query) else None
            ),
            "complete_queries": int(len(complete)),
            "complete_query_precision_at_k": (
                round(float(complete["precision"].mean()), 6) if len(complete) else None
            ),
            "per_genre": genre_metrics,
        }

    total_pairs = len(all_pair_ids)
    labeled_pairs = len(supplied_pair_ids)
    unresolved = int((merged["resolved_label"] == "UNRESOLVED").sum())
    result = {
        "primary_metric": "standardized_cosine.precision_at_k_valid_labels",
        "primary_metric_ready": labeled_pairs == total_pairs and unresolved == 0,
        "unique_pairs": total_pairs,
        "labeled_pairs": labeled_pairs,
        "pair_label_coverage": round(labeled_pairs / total_pairs, 6) if total_pairs else 0.0,
        "agreement": agreement,
        "methods": methods,
        "limitations": [
            "NA labels are excluded from precision denominators.",
            "A final claim requires all pairs labeled and all disagreements adjudicated.",
        ],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a frozen human similarity evaluation.")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "human_similarity.json",
    )
    args = parser.parse_args()

    key_path = args.package_dir / "retrieval_key.csv"
    manifest_path = args.package_dir / "manifest.json"
    key = pd.read_csv(key_path)
    labels = pd.read_csv(args.labels, keep_default_na=False)
    result = score(key, labels)
    output = {
        "run_id": datetime.now(timezone.utc).strftime("human_similarity_%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "inputs": {
            "package_manifest_sha256": sha256_file(manifest_path),
            "retrieval_key_sha256": sha256_file(key_path),
            "labels_sha256": sha256_file(args.labels),
        },
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

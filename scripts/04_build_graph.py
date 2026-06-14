from __future__ import annotations

import argparse
import json
import shutil

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from common import NUMERIC_FEATURE_COLUMNS, PROCESSED_DIR, WEB_DIR, ensure_directories


def clean_number(value: object, fallback: float = 0.0) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


def build_graph(frame: pd.DataFrame, top_k: int = 5) -> dict:
    if len(frame) < 2:
        raise ValueError("至少需要两首歌曲才能构建相似关系图。")

    numeric = frame[NUMERIC_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(numeric.median()).fillna(0.0)
    scaled = StandardScaler().fit_transform(numeric)
    similarity = cosine_similarity(scaled)
    np.fill_diagonal(similarity, -1.0)

    genres = sorted(frame["genre"].fillna("Unknown").astype(str).unique())
    genre_index = {genre: index for index, genre in enumerate(genres)}
    rms_values = numeric["rms"].to_numpy()
    rms_min, rms_max = float(rms_values.min()), float(rms_values.max())

    def symbol_size(rms: float, personal: bool) -> float:
        normalized = (rms - rms_min) / (rms_max - rms_min + 1e-9)
        return round(12 + normalized * 17 + (5 if personal else 0), 2)

    nodes = []
    for index, row in frame.iterrows():
        genre = str(row.get("genre") or "Unknown")
        personal = str(row.get("source")) == "personal"
        rms = clean_number(row.get("rms"))
        nodes.append(
            {
                "id": str(row["id"]),
                "name": str(row.get("title") or row["id"]),
                "title": str(row.get("title") or "Unknown Title"),
                "artist": str(row.get("artist") or "Unknown Artist"),
                "genre": genre,
                "source": str(row.get("source") or "unknown"),
                "isPersonal": personal,
                "category": genre_index[genre],
                "symbolSize": symbol_size(rms, personal),
                "tempo": round(clean_number(row.get("tempo")), 2),
                "energy": round(rms, 4),
                "rms": round(rms, 4),
                "zcr": round(clean_number(row.get("zcr")), 4),
                "spectral_centroid": round(clean_number(row.get("spectral_centroid")), 2),
            }
        )

    edge_keys: set[tuple[int, int]] = set()
    links = []
    recommendations: dict[str, list[dict]] = {}
    effective_k = min(top_k, len(frame) - 1)

    for source_index in range(len(frame)):
        nearest = np.argsort(similarity[source_index])[::-1][:effective_k]
        source_id = str(frame.iloc[source_index]["id"])
        recommendations[source_id] = []

        for target_index in nearest:
            score = max(0.0, clean_number(similarity[source_index, target_index]))
            target = frame.iloc[target_index]
            recommendations[source_id].append(
                {
                    "id": str(target["id"]),
                    "title": str(target.get("title") or "Unknown Title"),
                    "artist": str(target.get("artist") or "Unknown Artist"),
                    "genre": str(target.get("genre") or "Unknown"),
                    "similarity": round(score, 4),
                }
            )
            key = tuple(sorted((source_index, int(target_index))))
            if key not in edge_keys:
                edge_keys.add(key)
                links.append(
                    {
                        "source": str(frame.iloc[key[0]]["id"]),
                        "target": str(frame.iloc[key[1]]["id"]),
                        "value": round(max(0.0, clean_number(similarity[key[0], key[1]])), 4),
                    }
                )

    return {
        "nodes": nodes,
        "links": links,
        "categories": [{"name": genre} for genre in genres],
        "recommendations": recommendations,
        "meta": {"trackCount": len(nodes), "edgeCount": len(links), "topK": effective_k},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="计算相似度并生成前端图数据")
    parser.add_argument("--top-k", type=int, default=5, choices=range(1, 11))
    args = parser.parse_args()
    ensure_directories()

    input_path = PROCESSED_DIR / "music_features_all.csv"
    if not input_path.exists():
        parser.error("未找到 music_features_all.csv，请先运行 03_merge_features.py")
    frame = pd.read_csv(input_path).fillna("")
    try:
        graph = build_graph(frame, args.top_k)
    except ValueError as exc:
        parser.error(str(exc))

    output_path = PROCESSED_DIR / "music_graph.json"
    output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(output_path, WEB_DIR / "music_graph.json")
    print(f"已生成: data/processed/music_graph.json ({len(graph['nodes'])} 节点)")
    print("已复制: web/music_graph.json")

    personal_rows = []
    by_id = frame.set_index(frame["id"].astype(str))
    for node in graph["nodes"]:
        if not node["isPersonal"]:
            continue
        for item in graph["recommendations"][node["id"]]:
            personal_rows.append(
                {
                    "personal_id": node["id"],
                    "personal_title": node["title"],
                    "recommended_id": item["id"],
                    "recommended_title": item["title"],
                    "recommended_artist": item["artist"],
                    "recommended_genre": item["genre"],
                    "recommended_source": str(by_id.loc[item["id"], "source"]),
                    "similarity": item["similarity"],
                }
            )
    pd.DataFrame(personal_rows).to_csv(
        PROCESSED_DIR / "personal_recommendations.csv",
        index=False,
        encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()


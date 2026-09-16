from __future__ import annotations

import argparse

import pandas as pd

from common import PROCESSED_DIR, ensure_directories, normalize_feature_frame, write_csv


SOURCE_FILES = {
    "demo": "demo_features.csv",
    "personal": "personal_features.csv",
    "gtzan": "gtzan_features.csv",
}


def merge_features(sources: list[str]) -> pd.DataFrame:
    frames = []
    for source in sources:
        path = PROCESSED_DIR / SOURCE_FILES[source]
        if not path.exists():
            print(f"提示: {path.name} 不存在，跳过。")
            continue
        frame = normalize_feature_frame(pd.read_csv(path))
        if frame.empty:
            print(f"提示: {path.name} 没有有效歌曲，跳过。")
            continue
        frames.append(frame)

    if not frames:
        raise RuntimeError("没有可合并的数据，请先生成 demo 或提取音频特征。")

    merged = pd.concat(frames, ignore_index=True)
    merged["id"] = merged["id"].astype(str)
    duplicate_ids = merged["id"].duplicated()
    if duplicate_ids.any():
        merged.loc[duplicate_ids, "id"] += "_" + merged.index[duplicate_ids].astype(str)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="合并多个来源的音乐特征")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SOURCE_FILES),
        default=list(SOURCE_FILES),
    )
    args = parser.parse_args()
    ensure_directories()
    try:
        merged = merge_features(args.sources)
    except RuntimeError as exc:
        parser.error(str(exc))
    write_csv(merged, PROCESSED_DIR / "music_features_all.csv")


if __name__ == "__main__":
    main()


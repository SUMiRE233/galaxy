from __future__ import annotations

import argparse

import pandas as pd

from common import (
    PROCESSED_DIR,
    RAW_DIR,
    empty_feature_frame,
    ensure_directories,
    extract_audio_features,
    find_audio_files,
    write_csv,
)


def extract_fma(limit: int | None = None) -> pd.DataFrame:
    fma_dir = RAW_DIR / "fma_small"
    audio_files = find_audio_files(fma_dir)
    if not audio_files:
        print("提示: data/raw/fma_small/ 中没有音频，跳过 FMA。")
        return empty_feature_frame()
    if limit:
        audio_files = audio_files[:limit]

    rows = []
    for index, audio_path in enumerate(audio_files):
        try:
            features = extract_audio_features(audio_path)
        except Exception as exc:
            print(f"跳过: {audio_path.name} 特征提取失败: {exc}")
            continue

        track_id = audio_path.stem
        rows.append(
            {
                "id": f"fma_{track_id}",
                "track_id": track_id,
                "title": f"FMA Track {track_id}",
                "artist": "FMA Artist",
                "genre": "Unknown",
                "source": "fma",
                "filename": audio_path.name,
                "path": str(audio_path.relative_to(fma_dir.parent.parent.parent)),
                **features,
            }
        )
        print(f"已处理 FMA: {audio_path.name}")

    print("说明: 当前 FMA 接口从文件名生成基础元数据，可后续接入 tracks.csv 丰富标题/艺人/流派。")
    return pd.DataFrame(rows) if rows else empty_feature_frame()


def main() -> None:
    parser = argparse.ArgumentParser(description="提取 FMA small 音频特征")
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少首")
    args = parser.parse_args()
    ensure_directories()
    write_csv(extract_fma(args.limit), PROCESSED_DIR / "fma_features.csv")


if __name__ == "__main__":
    main()


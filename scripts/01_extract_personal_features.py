from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common import (
    PROCESSED_DIR,
    RAW_DIR,
    empty_feature_frame,
    ensure_directories,
    extract_audio_features,
    first_nonempty,
    write_csv,
)


def extract_personal(limit: int | None = None) -> pd.DataFrame:
    metadata_path = RAW_DIR / "personal" / "personal_tracks.csv"
    audio_dir = RAW_DIR / "personal" / "audios"

    if not metadata_path.exists():
        print("提示: 未找到 personal_tracks.csv，跳过个人音乐。")
        return empty_feature_frame()

    metadata = pd.read_csv(metadata_path).fillna("")
    required = {"filename", "title", "artist", "genre"}
    missing = required - set(metadata.columns)
    if missing:
        print(f"提示: personal_tracks.csv 缺少字段 {sorted(missing)}，跳过个人音乐。")
        return empty_feature_frame()

    if limit:
        metadata = metadata.head(limit)

    rows = []
    for index, track in metadata.iterrows():
        filename = str(track["filename"]).strip()
        audio_path = audio_dir / filename
        if not filename or not audio_path.exists():
            print(f"跳过: 找不到音频 {filename or '(空文件名)'}")
            continue
        try:
            features = extract_audio_features(audio_path)
        except Exception as exc:
            print(f"跳过: {filename} 特征提取失败: {exc}")
            continue

        rows.append(
            {
                "id": f"personal_{index:04d}",
                "track_id": f"P{index:04d}",
                "title": first_nonempty([track["title"], audio_path.stem], audio_path.stem),
                "artist": first_nonempty([track["artist"]], "Unknown Artist"),
                "genre": first_nonempty([track["genre"]], "Unknown"),
                "source": "personal",
                "filename": filename,
                "path": str(Path("data/raw/personal/audios") / filename),
                **features,
            }
        )
        print(f"已处理个人音乐: {filename}")

    return pd.DataFrame(rows) if rows else empty_feature_frame()


def main() -> None:
    parser = argparse.ArgumentParser(description="提取个人音乐的 librosa 特征")
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少首")
    args = parser.parse_args()
    ensure_directories()
    write_csv(extract_personal(args.limit), PROCESSED_DIR / "personal_features.csv")


if __name__ == "__main__":
    main()


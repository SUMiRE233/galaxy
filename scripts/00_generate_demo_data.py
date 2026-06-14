from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from common import FEATURE_COLUMNS, PROCESSED_DIR, ensure_directories, write_csv


GENRE_PROFILES = {
    "Pop": (118, 0.18, 0.075, 2450, 4700),
    "Rock": (132, 0.24, 0.095, 2850, 5400),
    "Electronic": (126, 0.22, 0.085, 3150, 6100),
    "Folk": (102, 0.13, 0.055, 1900, 3900),
    "Hip-Hop": (92, 0.21, 0.070, 2250, 4500),
    "Classical": (82, 0.10, 0.040, 1450, 3100),
    "Jazz": (110, 0.15, 0.060, 2050, 4200),
    "Metal": (150, 0.28, 0.115, 3450, 6600),
}

TITLE_WORDS = [
    "Neon", "Midnight", "Echo", "Solar", "Velvet", "Crystal", "Electric",
    "Silent", "Golden", "Parallel", "Northern", "Lunar", "Distant", "Blue",
]
TITLE_NOUNS = [
    "Skies", "Pulse", "Dream", "Signal", "River", "Orbit", "Memory",
    "Horizon", "Fire", "Garden", "Static", "Voyage", "Lights", "Rain",
]
ARTISTS = [
    "Nova Lane", "The Satellites", "Mira Chen", "Glass Harbor", "Low Gravity",
    "Aster Club", "Night Circuit", "June Atlas", "Paper Comets", "Mono Bloom",
]


def generate_demo(count: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    genres = list(GENRE_PROFILES)
    rows = []

    for index in range(count):
        genre = genres[index % len(genres)]
        tempo, rms, zcr, centroid, rolloff = GENRE_PROFILES[genre]
        genre_index = genres.index(genre)
        mfcc_base = np.linspace(-155 + genre_index * 5, 28 + genre_index * 2, 13)
        mfcc_values = mfcc_base + rng.normal(0, 8, 13)
        title = f"{rng.choice(TITLE_WORDS)} {rng.choice(TITLE_NOUNS)}"

        row = {
            "id": f"demo_{index:03d}",
            "track_id": f"D{index:04d}",
            "title": title,
            "artist": rng.choice(ARTISTS),
            "genre": genre,
            "source": "demo",
            "filename": "",
            "path": "",
            "tempo": max(45, rng.normal(tempo, 9)),
            "rms": max(0.02, rng.normal(rms, 0.025)),
            "zcr": max(0.005, rng.normal(zcr, 0.012)),
            "spectral_centroid": max(300, rng.normal(centroid, 260)),
            "spectral_rolloff": max(600, rng.normal(rolloff, 430)),
        }
        row.update({f"mfcc_{i + 1}": value for i, value in enumerate(mfcc_values)})
        rows.append(row)

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Music Galaxy demo 特征数据")
    parser.add_argument("--count", type=int, default=120, help="生成歌曲数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    if not 20 <= args.count <= 1000:
        parser.error("--count 应在 20 到 1000 之间")

    ensure_directories()
    write_csv(generate_demo(args.count, args.seed), PROCESSED_DIR / "demo_features.csv")


if __name__ == "__main__":
    main()


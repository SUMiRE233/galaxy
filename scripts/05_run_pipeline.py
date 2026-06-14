from __future__ import annotations

import argparse
import subprocess
import sys

from common import PROJECT_ROOT, RAW_DIR, ensure_directories, find_audio_files


SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def run_script(name: str, *args: str) -> None:
    command = [sys.executable, str(SCRIPTS_DIR / name), *args]
    print(f"\n>>> {' '.join(command)}")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def has_personal_data() -> bool:
    return (
        (RAW_DIR / "personal" / "personal_tracks.csv").exists()
        and bool(find_audio_files(RAW_DIR / "personal" / "audios"))
    )


def has_fma_data() -> bool:
    return bool(find_audio_files(RAW_DIR / "fma_small"))


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Music Galaxy 完整数据管线")
    parser.add_argument("--mode", choices=["demo", "personal", "all"], default="demo")
    parser.add_argument("--demo-count", type=int, default=120)
    parser.add_argument("--top-k", type=int, default=5, choices=range(1, 11))
    parser.add_argument("--limit", type=int, default=None, help="限制 personal/FMA 处理数量")
    args = parser.parse_args()
    ensure_directories()

    sources: list[str] = []
    limit_args = ["--limit", str(args.limit)] if args.limit else []

    if args.mode in {"demo", "all"}:
        run_script("00_generate_demo_data.py", "--count", str(args.demo_count))
        sources.append("demo")

    if args.mode in {"personal", "all"}:
        if has_personal_data():
            run_script("01_extract_personal_features.py", *limit_args)
            sources.append("personal")
        else:
            print("\n提示: 未发现完整的个人音乐数据，自动使用 demo 数据。")
            if "demo" not in sources:
                run_script("00_generate_demo_data.py", "--count", str(args.demo_count))
                sources.append("demo")

    if args.mode == "all":
        if has_fma_data():
            run_script("02_extract_fma_features.py", *limit_args)
            sources.append("fma")
        else:
            print("\n提示: 未发现 FMA small 音频，已跳过。")

    run_script("03_merge_features.py", "--sources", *sources)
    run_script("04_build_graph.py", "--top-k", str(args.top_k))
    print("\nMusic Galaxy 数据管线运行完成。")
    print("下一步: cd web && python -m http.server 8000")
    print("然后访问: http://localhost:8000")


if __name__ == "__main__":
    main()


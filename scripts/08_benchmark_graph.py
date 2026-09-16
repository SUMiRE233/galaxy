from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import psutil

from common import PROJECT_ROOT


def load_script(filename: str, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_state() -> dict[str, object]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    return {
        "commit": run("rev-parse", "HEAD") or None,
        "dirty": bool(run("status", "--porcelain")),
    }


def benchmark_size(count: int, top_k: int, seed: int) -> dict[str, object]:
    if count < 2:
        raise ValueError("Benchmark sizes must be at least 2.")

    demo_module = load_script("00_generate_demo_data.py", f"benchmark_demo_{count}")
    graph_module = load_script("04_build_graph.py", f"benchmark_graph_{count}")
    process = psutil.Process()
    gc.collect()
    baseline_rss = process.memory_info().rss
    peak_rss = baseline_rss
    stop = threading.Event()

    def sample_memory() -> None:
        nonlocal peak_rss
        while not stop.wait(0.01):
            peak_rss = max(peak_rss, process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        frame = demo_module.generate_demo(count=count, seed=seed)
        graph = graph_module.build_graph(frame, top_k=top_k)
        encoded_size = len(json.dumps(graph, ensure_ascii=False).encode("utf-8"))
    finally:
        elapsed = time.perf_counter() - started
        peak_rss = max(peak_rss, process.memory_info().rss)
        stop.set()
        sampler.join()

    return {
        "songs": count,
        "top_k": min(top_k, count - 1),
        "nodes": len(graph["nodes"]),
        "links": len(graph["links"]),
        "elapsed_seconds": round(elapsed, 4),
        "baseline_rss_mib": round(baseline_rss / (1024**2), 2),
        "peak_rss_mib": round(peak_rss / (1024**2), 2),
        "rss_increase_mib": round((peak_rss - baseline_rss) / (1024**2), 2),
        "similarity_matrix_estimate_mib": round((count * count * 8) / (1024**2), 2),
        "graph_json_mib": round(encoded_size / (1024**2), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Music Galaxy graph construction.")
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 1000, 5000])
    parser.add_argument("--top-k", type=int, default=20, choices=range(1, 21))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "graph_benchmark.json",
    )
    args = parser.parse_args()

    manifest = {
        "run_id": datetime.now(timezone.utc).strftime("benchmark_%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "python": sys.version,
        "platform": platform.platform(),
        "config": {"sizes": args.sizes, "top_k": args.top_k, "seed": args.seed},
        "results": [],
    }

    for count in args.sizes:
        result = benchmark_size(count=count, top_k=args.top_k, seed=args.seed)
        manifest["results"].append(result)
        print(json.dumps(result, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        display_path = args.output.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = args.output
    print(f"Saved: {display_path}")


if __name__ == "__main__":
    main()

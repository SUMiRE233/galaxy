from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from common import PROJECT_ROOT


def load_script(filename: str, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_public_fixture(count: int = 30, top_k: int = 5, seed: int = 42) -> tuple[Path, Path]:
    if count < 2:
        raise ValueError("Public fixture requires at least two demo tracks.")

    demo_module = load_script("00_generate_demo_data.py", "music_galaxy_fixture_demo")
    graph_module = load_script("04_build_graph.py", "music_galaxy_fixture_graph")

    frame = demo_module.generate_demo(count=count, seed=seed)
    graph = graph_module.build_graph(frame, top_k=top_k)

    if any(node.get("source") != "demo" or node.get("path") for node in graph["nodes"]):
        raise RuntimeError("Public fixture must contain synthetic demo nodes without audio paths.")

    feature_path = PROJECT_ROOT / "data" / "examples" / "demo_features.csv"
    graph_path = PROJECT_ROOT / "web" / "music_graph.example.json"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.parent.mkdir(parents=True, exist_ok=True)

    frame.to_csv(feature_path, index=False, encoding="utf-8")
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return feature_path, graph_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the sanitized public Music Galaxy fixture.")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5, choices=range(1, 21))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    feature_path, graph_path = build_public_fixture(args.count, args.top_k, args.seed)
    print(f"Generated: {feature_path.relative_to(PROJECT_ROOT)}")
    print(f"Generated: {graph_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

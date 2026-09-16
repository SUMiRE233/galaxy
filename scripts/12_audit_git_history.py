from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import PROJECT_ROOT


AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
SECRET_PATTERNS = {
    "openai_like_key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def git(*args: str, text: bool = True) -> str | bytes:
    text_options = {"encoding": "utf-8", "errors": "replace"} if text else {}
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=text,
        **text_options,
    )
    if result.returncode:
        return "" if text else b""
    return result.stdout


def git_state() -> dict[str, object]:
    commit = str(git("rev-parse", "HEAD")).strip()
    dirty = bool(str(git("status", "--porcelain")).strip())
    return {"commit": commit or None, "dirty": dirty}


def commits() -> list[str]:
    return [line for line in str(git("rev-list", "--all")).splitlines() if line]


def show_text(commit: str, path: str) -> str:
    return str(git("show", f"{commit}:{path}"))


def personal_metadata_findings() -> list[dict[str, object]]:
    findings = []
    for commit in commits():
        graph_text = show_text(commit, "web/music_graph.json")
        if graph_text:
            graph = json.loads(graph_text)
            personal = [
                node for node in graph.get("nodes", []) if node.get("source") == "personal"
            ]
            if personal:
                findings.append(
                    {
                        "commit": commit,
                        "path": "web/music_graph.json",
                        "personal_records": len(personal),
                        "nonempty_titles": sum(bool(node.get("title")) for node in personal),
                        "nonempty_artists": sum(bool(node.get("artist")) for node in personal),
                        "nonempty_paths": sum(bool(node.get("path")) for node in personal),
                    }
                )

        tracks_text = show_text(commit, "data/raw/personal/personal_tracks.csv")
        if tracks_text:
            rows = list(csv.DictReader(io.StringIO(tracks_text)))
            if rows:
                findings.append(
                    {
                        "commit": commit,
                        "path": "data/raw/personal/personal_tracks.csv",
                        "personal_records": len(rows),
                        "nonempty_titles": sum(bool(row.get("title")) for row in rows),
                        "nonempty_artists": sum(bool(row.get("artist")) for row in rows),
                        "nonempty_paths": 0,
                    }
                )
    return findings


def object_index() -> list[tuple[str, str]]:
    objects = []
    for line in str(git("rev-list", "--objects", "--all")).splitlines():
        object_id, _, path = line.partition(" ")
        if object_id:
            objects.append((object_id, path))
    return objects


def tracked_audio_paths(objects: list[tuple[str, str]]) -> list[str]:
    return sorted(
        {
            path
            for _, path in objects
            if path and Path(path).suffix.lower() in AUDIO_SUFFIXES
        }
    )


def secret_signature_findings(
    objects: list[tuple[str, str]],
    max_blob_bytes: int = 5_000_000,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    seen_blobs: set[str] = set()
    for object_id, path in objects:
        if object_id in seen_blobs:
            continue
        object_type = str(git("cat-file", "-t", object_id)).strip()
        if object_type != "blob":
            continue
        seen_blobs.add(object_id)
        size_text = str(git("cat-file", "-s", object_id)).strip()
        if not size_text.isdigit() or int(size_text) > max_blob_bytes:
            continue
        content = git("cat-file", "-p", object_id, text=False)
        assert isinstance(content, bytes)
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(
                    {
                        "object": object_id,
                        "path": path or "<unresolved>",
                        "signature": pattern_name,
                    }
                )
    return findings


def audit() -> dict[str, object]:
    objects = object_index()
    metadata = personal_metadata_findings()
    audio_paths = tracked_audio_paths(objects)
    secret_findings = secret_signature_findings(objects)
    return {
        "scope": "all_reachable_git_history",
        "git": git_state(),
        "summary": {
            "commits_scanned": len(commits()),
            "personal_metadata_findings": len(metadata),
            "commits_with_personal_metadata": len(
                {finding["commit"] for finding in metadata}
            ),
            "tracked_audio_paths": len(audio_paths),
            "potential_secret_signatures": len(secret_findings),
        },
        "personal_metadata": metadata,
        "tracked_audio_paths": audio_paths,
        "potential_secret_signatures": secret_findings,
        "limitations": [
            "Signature scanning covers common key formats and is not a proof that no secret exists.",
            "The report intentionally omits personal title and artist values.",
            "Removing current files does not remove historical blobs; rewriting history requires explicit authorization.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit reachable Git history for privacy risks.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "git_history_privacy_audit.json",
    )
    args = parser.parse_args()
    result = {
        "run_id": datetime.now(timezone.utc).strftime("git_history_audit_%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": audit(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["result"]["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

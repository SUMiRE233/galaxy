from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import (  # noqa: E402
    AUDIO_EXTENSIONS,
    FEATURE_COLUMNS,
    PROCESSED_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    WEB_DIR,
    ensure_directories,
    extract_audio_features,
    normalize_feature_frame,
    write_csv,
)


MAX_UPLOAD_SIZE = 50 * 1024 * 1024
PENDING_PATH = PROCESSED_DIR / "pending_personal_uploads.json"
PERSONAL_AUDIO_DIR = RAW_DIR / "personal" / "audios"
PERSONAL_TRACKS_PATH = RAW_DIR / "personal" / "personal_tracks.csv"
PERSONAL_FEATURES_PATH = PROCESSED_DIR / "personal_features.csv"
GRAPH_PATH = WEB_DIR / "music_graph.json"

app = FastAPI(title="Music Galaxy Local Processor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfirmGenreRequest(BaseModel):
    temp_id: str
    genre: str


class RebuildGraphRequest(BaseModel):
    sources: list[str] | None = None
    top_k: int = 20


def load_script_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_module = load_script_module("03_merge_features.py", "music_galaxy_merge")
graph_module = load_script_module("04_build_graph.py", "music_galaxy_graph")
demo_module = load_script_module("00_generate_demo_data.py", "music_galaxy_demo")


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "uploaded_audio").name
    stem = Path(name).stem.strip() or "uploaded_audio"
    suffix = Path(name).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._") or "uploaded_audio"
    return f"{safe_stem}{suffix}"


def unique_upload_path(folder: Path, filename: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    candidate = folder / safe_name
    index = 1
    while candidate.exists():
        candidate = folder / f"{Path(safe_name).stem}_{index}{Path(safe_name).suffix}"
        index += 1
    return candidate


def clean_tag_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip()


def parse_filename_metadata(filename: str) -> dict[str, str]:
    stem = Path(filename).stem.replace("_", " ").strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return {"artist": artist.strip(), "title": title.strip()}
    return {"artist": "", "title": stem or "Uploaded Song"}


def read_audio_metadata(audio_path: Path) -> dict[str, str]:
    parsed = parse_filename_metadata(audio_path.name)
    metadata = {
        "filename": audio_path.name,
        "title": parsed["title"],
        "artist": parsed["artist"] or "Unknown Artist",
        "album": "",
        "genre": "",
        "year": "",
        "track_number": "",
        "source_method": "filename",
    }

    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(audio_path, easy=True)
        if audio:
            metadata.update(
                {
                    "title": clean_tag_value(audio.get("title")) or metadata["title"],
                    "artist": clean_tag_value(audio.get("artist")) or metadata["artist"],
                    "album": clean_tag_value(audio.get("album")),
                    "genre": clean_tag_value(audio.get("genre")),
                    "year": clean_tag_value(audio.get("date")),
                    "track_number": clean_tag_value(audio.get("tracknumber")),
                    "source_method": "id3",
                }
            )
    except Exception:
        pass

    metadata["title"] = metadata["title"] or Path(audio_path.name).stem
    metadata["artist"] = metadata["artist"] or "Unknown Artist"
    metadata["genre"] = metadata["genre"] or "Unknown"
    return metadata


def load_pending_uploads() -> dict[str, Any]:
    ensure_directories()
    if not PENDING_PATH.exists():
        PENDING_PATH.write_text("{}", encoding="utf-8")
        return {}
    try:
        return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_pending_uploads(data: dict[str, Any]) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_personal_feature_row(metadata: dict[str, str], features: dict[str, float]) -> dict[str, Any]:
    personal_id = f"personal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    row = {
        "id": personal_id,
        "track_id": personal_id,
        "title": metadata.get("title") or Path(metadata["filename"]).stem,
        "artist": metadata.get("artist") or "Unknown Artist",
        "genre": metadata.get("genre") or "Unknown",
        "source": "personal",
        "filename": metadata["filename"],
        "path": str(Path("data/raw/personal/audios") / metadata["filename"]),
        **features,
    }
    return {column: row.get(column, "") for column in FEATURE_COLUMNS}


def append_personal_feature(row: dict[str, Any]) -> None:
    if PERSONAL_FEATURES_PATH.exists():
        frame = normalize_feature_frame(pd.read_csv(PERSONAL_FEATURES_PATH))
    else:
        frame = pd.DataFrame(columns=FEATURE_COLUMNS)
    frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
    write_csv(frame, PERSONAL_FEATURES_PATH)


def update_personal_tracks(metadata: dict[str, str]) -> None:
    columns = [
        "filename",
        "title",
        "artist",
        "album",
        "genre",
        "year",
        "source_method",
        "confidence",
    ]
    if PERSONAL_TRACKS_PATH.exists():
        frame = pd.read_csv(PERSONAL_TRACKS_PATH)
    else:
        frame = pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""

    row = {
        "filename": metadata.get("filename", ""),
        "title": metadata.get("title", ""),
        "artist": metadata.get("artist", "Unknown Artist"),
        "album": metadata.get("album", ""),
        "genre": metadata.get("genre", "Unknown"),
        "year": metadata.get("year", ""),
        "source_method": metadata.get("source_method", "filename"),
        "confidence": "metadata" if metadata.get("source_method") == "id3" else "filename",
    }
    frame = pd.concat([frame[columns], pd.DataFrame([row])], ignore_index=True)
    PERSONAL_TRACKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(PERSONAL_TRACKS_PATH, index=False, encoding="utf-8-sig")


def choose_sources() -> list[str]:
    if (PROCESSED_DIR / "gtzan_features.csv").exists():
        return ["gtzan", "personal"]
    if not (PROCESSED_DIR / "demo_features.csv").exists():
        write_csv(demo_module.generate_demo(), PROCESSED_DIR / "demo_features.csv")
    return ["demo", "personal"]


def graph_stats() -> dict[str, int]:
    if not GRAPH_PATH.exists():
        return {"nodes": 0, "links": 0, "personal_count": 0}
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    return {
        "nodes": len(nodes),
        "links": len(graph.get("links", [])),
        "personal_count": sum(1 for node in nodes if node.get("source") == "personal"),
    }


def rebuild_graph(sources: list[str] | None = None, top_k: int = 20) -> dict[str, int]:
    ensure_directories()
    selected_sources = sources or choose_sources()
    if not (PROCESSED_DIR / "personal_features.csv").exists():
        pd.DataFrame(columns=FEATURE_COLUMNS).to_csv(
            PROCESSED_DIR / "personal_features.csv",
            index=False,
            encoding="utf-8-sig",
        )
    merged = merge_module.merge_features(selected_sources)
    write_csv(merged, PROCESSED_DIR / "music_features_all.csv")
    graph = graph_module.build_graph(merged.fillna(""), top_k=top_k)
    output_path = PROCESSED_DIR / "music_graph.json"
    output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(output_path, GRAPH_PATH)
    return graph_stats()


def add_personal_song(metadata: dict[str, str], features: dict[str, float]) -> dict[str, int]:
    append_personal_feature(make_personal_feature_row(metadata, features))
    update_personal_tracks(metadata)
    return rebuild_graph(top_k=20)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/upload-personal")
async def upload_personal(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_directories()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported audio file type.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Audio file is larger than 50MB.")

    upload_path = unique_upload_path(PERSONAL_AUDIO_DIR, file.filename or f"uploaded{suffix}")
    upload_path.write_bytes(content)

    metadata = read_audio_metadata(upload_path)
    try:
        features = extract_audio_features(upload_path)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Audio feature extraction failed: {exc}") from exc

    metadata["filename"] = upload_path.name
    need_genre = not metadata.get("genre") or metadata["genre"] == "Unknown"
    preview = {
        "tempo": round(float(features.get("tempo", 0)), 2),
        "rms": round(float(features.get("rms", 0)), 4),
        "spectral_centroid": round(float(features.get("spectral_centroid", 0)), 2),
    }

    if need_genre:
        temp_id = f"pending_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        pending = load_pending_uploads()
        pending[temp_id] = {"metadata": metadata, "features": features}
        save_pending_uploads(pending)
        return {
            "ok": True,
            "need_genre": True,
            "temp_id": temp_id,
            "metadata": metadata,
            "features_preview": preview,
        }

    stats = add_personal_song(metadata, features)
    return {
        "ok": True,
        "need_genre": False,
        "message": "Personal song added to Music Galaxy.",
        "metadata": metadata,
        "stats": stats,
    }


@app.post("/api/confirm-personal-genre")
def confirm_personal_genre(payload: ConfirmGenreRequest) -> dict[str, Any]:
    pending = load_pending_uploads()
    record = pending.get(payload.temp_id)
    if not record:
        raise HTTPException(status_code=404, detail="Pending upload not found.")
    genre = payload.genre.strip() or "Unknown"
    metadata = record["metadata"]
    metadata["genre"] = genre
    stats = add_personal_song(metadata, record["features"])
    pending.pop(payload.temp_id, None)
    save_pending_uploads(pending)
    return {"ok": True, "message": "Personal song added to Music Galaxy.", "stats": stats}


@app.post("/api/rebuild-graph")
def rebuild_graph_api(payload: RebuildGraphRequest) -> dict[str, Any]:
    top_k = min(max(int(payload.top_k or 20), 1), 20)
    stats = rebuild_graph(sources=payload.sources, top_k=top_k)
    return {"ok": True, "stats": stats}


@app.get("/api/graph")
def get_graph() -> Any:
    if not GRAPH_PATH.exists():
        rebuild_graph(top_k=20)
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


@app.get("/api/audio")
def get_audio(path: str) -> FileResponse:
    audio_path = (PROJECT_ROOT / path).resolve()
    try:
        audio_path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid audio path.") from exc
    if not audio_path.exists() or audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(audio_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8001, reload=False)

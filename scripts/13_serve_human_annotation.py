from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from common import PROJECT_ROOT


LABEL_COLUMNS = ["pair_id", "annotator_id", "relevance", "confidence", "notes", "updated_at"]


class LabelRequest(BaseModel):
    pair_id: str
    relevance: Literal["0", "1", "NA"]
    confidence: int = Field(default=2, ge=1, le=3)
    notes: str = Field(default="", max_length=500)


def read_labels(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    try:
        frame = pd.read_csv(path, keep_default_na=False)
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame(columns=LABEL_COLUMNS)
    for column in LABEL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[LABEL_COLUMNS]


def write_labels(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    frame[LABEL_COLUMNS].to_csv(temp_path, index=False, encoding="utf-8")
    os.replace(temp_path, path)


def resolve_audio(relative_path: str) -> Path:
    audio_path = (PROJECT_ROOT / relative_path).resolve()
    try:
        audio_path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid audio path.") from exc
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return audio_path


def create_app(package_dir: Path, labels_path: Path, annotator_id: str = "annotator_1") -> FastAPI:
    pairs_path = package_dir / "pairs.csv"
    playback_path = package_dir / "playback_index.csv"
    if not pairs_path.exists() or not playback_path.exists():
        raise FileNotFoundError("Frozen evaluation package is incomplete.")

    pairs = pd.read_csv(pairs_path).sort_values("presentation_order", kind="stable")
    playback = pd.read_csv(playback_path)
    merged = pairs.merge(playback, on="pair_id", how="left", validate="one_to_one")
    if merged[["query_path", "candidate_path"]].isna().any().any():
        raise ValueError("Playback index is missing a frozen pair.")
    pair_records = {str(row["pair_id"]): row for _, row in merged.iterrows()}

    app = FastAPI(title="Music Galaxy Blind Similarity Review")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return ANNOTATION_HTML

    @app.get("/api/state")
    def state() -> dict[str, object]:
        labels = read_labels(labels_path)
        own_labels = labels[labels["annotator_id"].astype(str).eq(annotator_id)]
        by_pair = {str(row["pair_id"]): row for _, row in own_labels.iterrows()}
        items = []
        for pair_id, row in pair_records.items():
            label = by_pair.get(pair_id)
            items.append(
                {
                    "pair_id": pair_id,
                    "order": int(row["presentation_order"]),
                    "relevance": str(label["relevance"]) if label is not None else "",
                    "confidence": int(label["confidence"]) if label is not None and str(label["confidence"]) else 2,
                    "notes": str(label["notes"]) if label is not None else "",
                    "query_audio": f"/api/audio/{pair_id}/query",
                    "candidate_audio": f"/api/audio/{pair_id}/candidate",
                }
            )
        return {
            "annotator_id": annotator_id,
            "total": len(items),
            "completed": sum(bool(item["relevance"]) for item in items),
            "items": items,
        }

    @app.get("/api/audio/{pair_id}/{side}")
    def audio(pair_id: str, side: Literal["query", "candidate"]) -> FileResponse:
        row = pair_records.get(pair_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown pair.")
        return FileResponse(resolve_audio(str(row[f"{side}_path"])))

    @app.post("/api/label")
    def save_label(payload: LabelRequest) -> dict[str, object]:
        if payload.pair_id not in pair_records:
            raise HTTPException(status_code=404, detail="Unknown pair.")
        labels = read_labels(labels_path)
        keep = ~(
            labels["pair_id"].astype(str).eq(payload.pair_id)
            & labels["annotator_id"].astype(str).eq(annotator_id)
        )
        labels = labels.loc[keep].copy()
        row = {
            "pair_id": payload.pair_id,
            "annotator_id": annotator_id,
            "relevance": payload.relevance,
            "confidence": payload.confidence,
            "notes": payload.notes.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        labels = pd.concat([labels, pd.DataFrame([row])], ignore_index=True)
        labels = labels.sort_values(["pair_id", "annotator_id"], kind="stable")
        write_labels(labels_path, labels)
        return {"ok": True, "pair_id": payload.pair_id}

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {"ok": True, "pairs": len(pair_records), "labels": str(labels_path)}

    return app


ANNOTATION_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Music Galaxy 盲听评估</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, "Microsoft YaHei", sans-serif; }
    body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top, #172342, #080b17 62%); color: #eef4ff; }
    main { width: min(900px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }
    .panel { background: rgba(17, 24, 48, .92); border: 1px solid #33456f; border-radius: 18px; padding: 22px; box-shadow: 0 18px 70px #0008; }
    .top { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    h1 { margin: 0; font-size: 24px; } .muted { color: #9eacd0; }
    progress { width: 100%; height: 12px; margin: 16px 0 22px; }
    .audio-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    .clip { background: #0c1228; border-radius: 14px; padding: 16px; border: 1px solid #26365f; }
    audio { width: 100%; margin-top: 10px; }
    .labels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0 14px; }
    button { border: 1px solid #526a9d; border-radius: 12px; padding: 13px 10px; background: #19264a; color: #fff; cursor: pointer; font-weight: 650; }
    button:hover { background: #263967; } button.selected { outline: 3px solid #64d9ff; background: #27486b; }
    .nav { display: flex; justify-content: space-between; gap: 12px; margin-top: 18px; }
    .nav button { min-width: 120px; }
    textarea { box-sizing: border-box; width: 100%; min-height: 74px; background: #0b1022; color: #fff; border: 1px solid #34466f; border-radius: 10px; padding: 10px; }
    select { background: #0b1022; color: #fff; border: 1px solid #34466f; border-radius: 8px; padding: 7px; }
    .status { min-height: 24px; color: #78e5b4; }
    @media (max-width: 680px) { .audio-grid { grid-template-columns: 1fr; } .labels { grid-template-columns: 1fr; } }
  </style>
</head>
<body><main>
  <div class="panel">
    <div class="top"><div><h1>Music Galaxy 盲听评估</h1><div class="muted" id="pair"></div></div><strong id="count"></strong></div>
    <progress id="progress" value="0" max="1"></progress>
    <div class="audio-grid">
      <div class="clip"><strong>片段 A</strong><audio id="audio-a" controls preload="metadata"></audio></div>
      <div class="clip"><strong>片段 B</strong><audio id="audio-b" controls preload="metadata"></audio></div>
    </div>
    <p>忽略文件名、流派与方法，只根据听感判断两个片段是否适合作为相似音乐探索结果。</p>
    <div class="labels">
      <button data-label="1">相似（快捷键 1）</button>
      <button data-label="0">不相似（快捷键 0）</button>
      <button data-label="NA">无法判断（快捷键 N）</button>
    </div>
    <label>信心：<select id="confidence"><option value="1">低</option><option value="2" selected>中</option><option value="3">高</option></select></label>
    <p><textarea id="notes" maxlength="500" placeholder="可选备注；不要写个人信息"></textarea></p>
    <div class="status" id="status"></div>
    <div class="nav"><button id="prev">← 上一对</button><button id="next">下一对 →</button></div>
  </div>
</main>
<script>
let state, index = 0, selected = "";
const $ = (id) => document.getElementById(id);
async function load() {
  state = await (await fetch('/api/state')).json();
  const firstOpen = state.items.findIndex(item => !item.relevance);
  index = firstOpen >= 0 ? firstOpen : 0;
  render();
}
function render() {
  const item = state.items[index]; selected = item.relevance || "";
  $('pair').textContent = `匿名样本 ${item.order}`;
  $('count').textContent = `${state.completed} / ${state.total}`;
  $('progress').max = state.total; $('progress').value = state.completed;
  $('audio-a').src = item.query_audio; $('audio-b').src = item.candidate_audio;
  $('confidence').value = String(item.confidence || 2); $('notes').value = item.notes || "";
  document.querySelectorAll('[data-label]').forEach(btn => btn.classList.toggle('selected', btn.dataset.label === selected));
  $('prev').disabled = index === 0; $('next').disabled = index === state.items.length - 1;
  $('status').textContent = selected ? `已保存：${selected}` : '尚未标注';
}
async function save(label) {
  const item = state.items[index];
  const response = await fetch('/api/label', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pair_id:item.pair_id,relevance:label,confidence:Number($('confidence').value),notes:$('notes').value})});
  if (!response.ok) { $('status').textContent = '保存失败'; return; }
  if (!item.relevance) state.completed += 1;
  item.relevance = label; item.confidence = Number($('confidence').value); item.notes = $('notes').value;
  selected = label; render();
  if (index < state.items.length - 1) { index += 1; render(); }
}
document.querySelectorAll('[data-label]').forEach(btn => btn.addEventListener('click', () => save(btn.dataset.label)));
$('prev').addEventListener('click', () => { if(index > 0){ index -= 1; render(); }});
$('next').addEventListener('click', () => { if(index < state.items.length - 1){ index += 1; render(); }});
document.addEventListener('keydown', e => { if(e.target.tagName === 'TEXTAREA') return; if(e.key==='1') save('1'); if(e.key==='0') save('0'); if(e.key.toLowerCase()==='n') save('NA'); if(e.key==='ArrowLeft') $('prev').click(); if(e.key==='ArrowRight') $('next').click(); });
load().catch(error => { $('status').textContent = error.message; });
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local blinded listening preview.")
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "frozen" / "gtzan_human_v2",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "local_annotations" / "annotator_1.csv",
    )
    parser.add_argument("--annotator-id", default="annotator_1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    app = create_app(args.package_dir, args.labels, args.annotator_id)
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Listening preview: {url}")
    print(f"Private labels: {args.labels}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

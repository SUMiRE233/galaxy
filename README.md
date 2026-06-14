# Music Galaxy

Music Galaxy 是一个面向“多媒体数据可视化”课程的初步可运行项目。它将每首歌曲表示为一个节点，将音频特征相似度表示为边，再通过 ECharts 力导向布局形成可交互的“音乐星系”。

项目重点是音乐相似关系可视化，而不是训练音乐分类模型。即使 FMA small 尚未下载，也可以仅使用内置 demo 数据完整运行。

## 项目目标

- 建立 demo、个人音乐、FMA small 三类数据的统一特征管线。
- 使用 librosa 提取前 30 秒音频的节奏、能量、频谱与 MFCC 特征。
- 标准化特征并使用余弦相似度连接每首歌的 Top-K 邻居。
- 生成可供前端直接读取的 `music_graph.json`。
- 使用 ECharts 展示可缩放、可拖拽、可筛选的动态力导向图。

## 目录结构

```text
music-galaxy/
├─ README.md
├─ requirements.txt
├─ data/
│  ├─ raw/
│  │  ├─ personal/
│  │  │  ├─ audios/
│  │  │  └─ personal_tracks.csv
│  │  └─ fma_small/
│  └─ processed/
│     ├─ demo_features.csv
│     ├─ personal_features.csv
│     ├─ fma_features.csv
│     ├─ music_features_all.csv
│     ├─ music_graph.json
│     └─ personal_recommendations.csv
├─ scripts/
│  ├─ common.py
│  ├─ 00_generate_demo_data.py
│  ├─ 01_extract_personal_features.py
│  ├─ 02_extract_fma_features.py
│  ├─ 03_merge_features.py
│  ├─ 04_build_graph.py
│  └─ 05_run_pipeline.py
└─ web/
   ├─ index.html
   ├─ app.js
   ├─ style.css
   └─ music_graph.json
```

## 环境安装

建议使用 Python 3.10 或更高版本。在项目根目录执行：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

主要依赖包括 `numpy`、`pandas`、`scikit-learn`、`librosa` 和 `soundfile`。部分 MP3 文件可能还需要系统安装 FFmpeg。

## 运行 Demo

在项目根目录执行：

```bash
python scripts/05_run_pipeline.py --mode demo
```

该命令默认生成 120 首模拟歌曲，并生成：

- `data/processed/demo_features.csv`
- `data/processed/music_features_all.csv`
- `data/processed/music_graph.json`
- `web/music_graph.json`

可以调整 demo 数量和邻居数：

```bash
python scripts/05_run_pipeline.py --mode demo --demo-count 150 --top-k 3
```

然后启动前端：

```bash
cd web
python -m http.server 8000
```

浏览器访问 <http://localhost:8000>。

不要直接双击打开 `index.html`。页面使用 `fetch` 读取 JSON，浏览器在 `file://` 模式下通常会因为 CORS 安全策略阻止读取。

前端 ECharts 默认从 jsDelivr CDN 加载，因此首次打开页面需要网络连接。如需完全离线运行，可下载 `echarts.min.js` 到 `web/`，并修改 `index.html` 中对应的 `<script>` 地址。

## 加入个人音乐

1. 将 MP3、WAV、FLAC、OGG、M4A 或 AAC 文件放入：

   ```text
   data/raw/personal/audios/
   ```

2. 编辑 `data/raw/personal/personal_tracks.csv`：

   ```csv
   filename,title,artist,genre
   my_song.mp3,My Song,My Artist,Pop
   another.wav,Another Song,Someone,Jazz
   ```

3. 运行：

   ```bash
   python scripts/05_run_pipeline.py --mode personal
   ```

程序只读取每个音频的前 30 秒。若 CSV、音频或某个文件缺失，会显示友好提示；当没有任何有效个人歌曲时，管线会自动回退到 demo 数据。

个人音乐节点在图中具有更大的尺寸、白色描边和青色阴影。若存在个人歌曲，系统还会生成 `data/processed/personal_recommendations.csv`。

## 混合模式

```bash
python scripts/05_run_pipeline.py --mode all
```

混合模式总会生成 demo 数据，并尽可能加入 personal 和 FMA 数据。缺失的数据源会被跳过，不会导致整个流程失败。

处理大量音频前可先限制数量：

```bash
python scripts/05_run_pipeline.py --mode all --limit 50
```

## 接入 FMA Small

将 FMA small 的音频目录或音频文件复制到：

```text
data/raw/fma_small/
```

然后运行：

```bash
python scripts/05_run_pipeline.py --mode all
```

当前预留实现会递归扫描音频文件、使用统一的 librosa 流程提取特征，并用文件名作为 `track_id`。由于课程项目当前不依赖完整 FMA 元数据，标题、艺人和流派使用占位值。后续可在 `02_extract_fma_features.py` 中读取 FMA 官方 `tracks.csv`，按 `track_id` 合并真实元数据。

也可以单独执行：

```bash
python scripts/02_extract_fma_features.py --limit 100
python scripts/03_merge_features.py --sources demo fma
python scripts/04_build_graph.py --top-k 5
```

## 特征与技术路线

每首歌统一包含：

- 元数据：`id`、`track_id`、`title`、`artist`、`genre`、`source`、`filename`、`path`
- 音频特征：`tempo`、`rms`、`zcr`、`spectral_centroid`、`spectral_rolloff`
- MFCC：`mfcc_1` 到 `mfcc_13`

处理流程：

1. demo 生成或 librosa 音频特征提取。
2. 合并不同数据源为统一特征表。
3. 使用 `StandardScaler` 标准化数值特征。
4. 使用 `cosine_similarity` 计算歌曲两两相似度。
5. 为每首歌选择 Top-K 最相似节点并去除重复边。
6. 输出节点、边、流派分类和推荐列表到 JSON。
7. ECharts 使用力导向布局渲染图结构。

## 可视化含义

- 节点：歌曲。
- 节点颜色：歌曲流派。
- 节点大小：RMS 能量，能量越高节点越大。
- 白色描边与青色光晕：个人歌曲。
- 边：歌曲特征相似关系。
- 边的 `value`：标准化音频特征的余弦相似度。
- 点击节点：查看 BPM、能量、频谱质心和 Top 相似歌曲。
- 顶部筛选器：按流派或数据来源过滤星图。

## 注意事项

- 首次使用个人音频时，librosa 可能触发底层解码依赖加载，速度会比 demo 慢。
- 音频特征只取前 30 秒，是速度与代表性之间的课程项目级折中。
- demo 特征按流派分布生成，仅用于演示交互，不代表真实音乐统计规律。
- FMA small 文件较多，建议先使用 `--limit` 验证环境。
- 相似度为特征空间中的数学距离，不等同于主观音乐品味。
- 所有脚本都应从项目根目录运行；脚本内部使用 `pathlib.Path` 解析路径，不依赖固定操作系统路径。


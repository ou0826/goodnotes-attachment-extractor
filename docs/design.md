# 架构与实现说明

本文说明 GoodNotes 附件提取器的模块划分、文件格式处理方式和关键算法，
面向想阅读源码或参与贡献的开发者。普通使用请看 [README](../README.md) 或
[使用说明](usage.md)。

## 1. 设计目标

1. **零运行时依赖**：只使用 Python 标准库，用户不需要安装任何第三方包。
2. **直接解析二进制**：不依赖 GoodNotes 的内部代码，只按公开的容器格式读取数据。
3. **只读安全**：不修改源文件，不执行容器中的任何内容，不联网。
4. **双入口**：CLI 便于自动化和批处理，GUI 便于普通用户操作。
5. **可复现发布**：源码、测试和构建脚本都在仓库中。

## 2. 整体架构

```text
                    ┌──────────────────────┐
                    │  cli.py / gui.py     │  表示层
                    │  参数解析、文件选择   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  batch.py            │  流程编排
                    │  目录扫描、批量处理   │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌─────────▼────────┐   ┌─────────▼────────┐
│ classifier.py  │   │ metadata.py      │   │ parser.py        │
│ 魔术字节分类    │   │ Protobuf 索引解码 │   │ MP4/JPEG/PNG/PDF │
└────────────────┘   └──────────────────┘   └──────────────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
      ┌───────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
      │ config.py    │  │ logger.py   │  │ converter.py│
      │ 配置持久化    │  │ 日志与轮转   │  │ 可选格式转换 │
      └──────────────┘  └─────────────┘  └─────────────┘
```

`cli.py` 与 `gui.py` 各自实现了单文件提取流程，两者行为应保持一致；
公共的解析、分类、元数据能力都在下层模块中。

## 3. `.goodnotes` 容器结构

`.goodnotes` 是一个 ZIP 容器（`zipfile` 可直接打开）。典型结构：

```text
example.goodnotes
├── schema.pb                  数据模式版本（小端 uint16）
├── index.notes.pb             笔记页 UUID → 页面路径
├── index.attachments.pb       附件 UUID → 附件路径
├── index.events.pb            事件/操作记录
├── index.search.pb            搜索索引
├── notes/                     笔记页面数据
├── attachments/               附件（录音、图片、PDF）
└── ...
```

提取逻辑：

1. 打开 ZIP，枚举 `attachments/` 下的所有成员；
2. 同时把根目录下非 `.pb`、非目录的文件也作为候选；
3. 读取每个成员的前 12 字节做类型识别，再读取完整数据；
4. 按类型过滤，生成人类可读的文件名，写入输出目录。

> 不同 GoodNotes 版本导出的容器内容可能略有差异。本项目主要针对 GoodNotes 5
> 导出的格式开发和测试。

## 4. 模块设计

### 4.1 `classifier.py` — 文件类型识别

`FileCategory` 定义六个类别：`audio`、`video`、`image`、`pdf`、`protobuf`、
`unknown`。

`classify_file(data)` 的判定顺序：

1. 长度不足 12 字节 → `unknown`；
2. `data[4:8] == b"ftyp"` → MP4 容器：
   - 含视频编解码特征码（`avc1`、`hvc1`、`vp09`、`av01` 等）→ `video`；
   - 含音频特征码（`mp4a`、`aac ` 等）→ `audio`；
3. JPEG：`FF D8` 开头且带 APP0–APP15 段，或在前 4 KB 中找到 `FF DB` 与 `FF C0`；
4. PNG：8 字节固定签名；
5. PDF：`%PDF-`；
6. Protobuf 启发式检测 → `protobuf`；
7. 其余 → `unknown`。

`classify_file_detailed(data, filename)` 额外返回子类型、MIME、建议扩展名和置信度，
用于 `--info` 的详情输出。

### 4.2 `parser.py` — 二进制格式解析

| 函数 | 说明 |
| --- | --- |
| `parse_mp4_atom_tree` | 遍历 ISO BMFF 顶层原子，返回 offset/size/type |
| `parse_mp4_audio_metadata` | 解析 `moov → trak → mdia → mdhd` 得到时长与时间刻度，解析 `stsd → mp4a` 得到采样率与声道数 |
| `estimate_audio_duration_from_size` | 在缺少 `moov` 时按 AAC 压缩比估算时长 |
| `verify_mp4_integrity` | 检查 `ftyp`/`moov`/`mdat`/`mp4a` 是否存在及顺序 |
| `parse_jpeg_dimensions` | 按段标记状态机寻找 SOF0–SOF15，读取宽高 |
| `parse_jpeg_exif_orientation` | 读取 EXIF 方向标签 |
| `parse_png_dimensions` | 读取 IHDR 前 8 字节（大端宽高） |
| `parse_png_chunks` | 枚举 PNG 块（类型、长度） |
| `parse_png_color_info` | 读取位深、颜色类型等 |
| `is_pdf_document` / `parse_pdf_version` / `parse_pdf_page_count` | PDF 签名、版本头、页数估算 |

MP4 时长计算：

```text
duration(秒) = mvhd.duration / mvhd.timescale
```

`mvhd` 有版本 0（32 位）与版本 1（64 位）两种布局，解析时按版本号选择字段偏移。

### 4.3 `metadata.py` — Protobuf 索引解码

GoodNotes 的索引文件使用 Protocol Buffers wire format，但没有随附 `.proto` 定义。
本项目实现了一个最小 wire-format 解码器：

- `_read_varint`：读取 base-128 变长整数；
- `_read_length_delimited`：读取长度前缀的字符串/字节/嵌套消息；
- `_decode_tag`：拆出字段号与 wire type。

在此基础上：

- `_parse_string_map_protobuf` 从 length-delimited 字段中提取 UUID → 路径的映射；
- `_parse_events_protobuf` 统计事件记录；
- `_looks_like_uuid_at` 识别 36 字符的标准 UUID 文本；
- `parse_goodnotes_index` 汇总 schema 版本、笔记数、附件数、事件数、附件总大小、
  修改时间，返回 `GoodNotesMetadata`；
- `format_metadata_summary` 生成 `--info` 的文本摘要。

> 由于没有 schema，索引解析采取启发式策略：只提取能确定的结构，无法识别的字段
> 会被跳过，不影响附件提取。

### 4.4 `batch.py` — 批量处理

- `find_goodnotes_files(directory, recursive=True)`：`Path.rglob` / `glob` 查找；
- `BatchProcessor.process_multiple(input_files, output_base_dir, merge_output, extract_func)`：
  逐个调用提取函数，汇总成功/失败数量与耗时，支持进度回调；
- `merge_directories(source_dirs, output_dir)`：按 SHA-256 去重后合并目录；
- `organize_output_by_date`：按修改日期整理输出。

### 4.5 `converter.py` — 可选格式转换

提供 M4A→WAV/MP3、图片格式转换与缩放。音频转换优先调用系统 `ffmpeg`，
找不到时回退到纯 Python 的 WAV 写入；图片转换需要可选的 Pillow。

> 该模块目前作为库 API 提供，尚未接入 CLI/GUI 界面。

### 4.6 `config.py` — 配置管理

- 配置文件：`~/.goodnotes-extractor/config.json`；
- 分层优先级：内置默认值 < 用户配置 < 环境变量；
- 环境变量：`GNOTES_OUTPUT_DIR`、`GNOTES_LANG`、`GNOTES_LOG_LEVEL`、
  `GNOTES_FFMPEG_PATH`；
- 点号路径访问：`get("extraction.audio_enabled")`。

### 4.7 `logger.py` — 日志

- 控制台彩色输出 + 文件输出 + 可选 GUI 回调；
- 日志目录：`~/.goodnotes-extractor/logs/`；
- 文件名：`extract_YYYYmmdd_HHMMSS.log`；
- 自动清理，只保留最近 10 个日志文件。

### 4.8 `cli.py` — 命令行

`main()` 的分派顺序：

```text
无参数        → 在当前目录查找 .goodnotes 并提取；找不到则打印帮助
--gui         → 启动 GUI
-h/--help     → 帮助
-v/--version  → 版本号
--info FILE   → 打印元数据
--batch DIR   → 批量提取
其他          → 视为单文件提取，第二个参数为输出目录
```

`extract_single()` 是核心提取函数，返回
`{"audio": n, "image": n, "pdf": n, "total": n, "errors": [...]}`。

### 4.9 `gui.py` — 图形界面

基于 Tkinter，布局为：

- 顶部：标题、文件/目录选择、输出目录；
- 左侧：类型筛选、是否分类、完成后打开目录、待处理文件列表；
- 右侧：结果表格（类型/文件名/大小/详情）、处理日志；
- 底部：状态文本与进度条。

提取在 `threading.Thread` 中执行，通过 `root.after()` 回到主线程更新 UI，
避免界面卡死。

## 5. 输出与命名

| 类型 | 文件名模板 | 元数据来源 |
| --- | --- | --- |
| 音频 | `录音_<分>m<秒>s.m4a` | `mvhd` 时长，缺失时用 UUID 前 8 位 |
| 图片 | `图片_<宽>x<高>.<png/jpg>` | PNG IHDR / JPEG SOF |
| PDF | `文档_<UUID 前 8 位>.pdf` | 容器成员名 |

同名文件会追加 `_1`、`_2`，不会覆盖。

## 6. 测试

- 框架：标准库 `unittest`，同时兼容 `pytest`；
- 数量：74 个用例，覆盖解析器、分类器、元数据解码；
- 测试数据全部在代码中构造，不依赖真实笔记文件；
- CI：GitHub Actions 在 Ubuntu / Windows / macOS 上运行。

```bash
pytest
python -m unittest discover -s tests -v
```

## 7. 构建与发布

```bash
python -m pip install -e ".[dev]"
python scripts/build_exe.py
```

构建脚本使用 PyInstaller 的单文件模式，入口为 `scripts/launcher.py`。
推送 `v*` 标签时，`.github/workflows/release.yml` 会自动在 Windows 上构建并把
exe 上传到 GitHub Release。

## 8. 已知限制

- 主要测试环境是 Windows 10/11；GUI 使用了 Windows 常见字体，其他平台会回退；
- 批量模式的跨文件去重需要库调用，CLI 暂未提供开关；
- Protobuf 索引没有 schema，解析结果可能随 GoodNotes 版本变化；
- 不支持加密或损坏的容器；
- 尚无针对超大容器（>2 GB）的流式处理。

## 9. 版本

当前版本 1.0.1，许可证 MIT。变更记录见 [CHANGELOG](../CHANGELOG.md)。

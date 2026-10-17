# 使用说明

本文是 GoodNotes 附件提取器的完整使用手册。想先快速上手，请回到
[README](../README.md)。

## 1. 安装

### 1.1 使用发布版 exe（Windows）

1. 从 [Releases](https://github.com/ou0826/goodnotes-attachment-extractor/releases)
   下载 `GoodNotes-Attachment-Extractor-vX.Y.Z-win64.exe`；
2. 放到任意目录，双击运行；
3. 无参数运行时会显示帮助并等待回车；加 `--gui` 启动图形界面。

exe 为单文件绿色版，无需安装、无需 Python。卸载时直接删除 exe 即可。

> exe 未做代码签名，Windows SmartScreen 可能拦截。可选择"更多信息 → 仍要运行"，
> 或从源码运行/自行构建。

### 1.2 从源码安装

```bash
git clone https://github.com/ou0826/goodnotes-attachment-extractor.git
cd goodnotes-attachment-extractor
python -m pip install -e .
```

要求 Python 3.9 及以上。安装后可使用 `gn-extract` 和 `gn-extract-gui`。

不安装也可以运行：

```bash
# Windows PowerShell
$env:PYTHONPATH="src"; python -m goodnotes_extractor --help

# macOS / Linux
PYTHONPATH=src python -m goodnotes_extractor --help
```

## 2. 图形界面

<p align="center">
  <img src="images/gui.png" alt="图形界面截图" width="820">
</p>


启动方式：

```bash
gn-extract-gui
# 或
gn-extract --gui
```

### 2.1 界面布局

```text
┌─────────────────────────────────────────────────────────────┐
│ GoodNotes 附件提取器 v1.0.0                                 │
│ [选择文件] [选择目录（批量）] [输出目录…]                     │
├───────────────┬─────────────────────────────────────────────┤
│ 提取选项       │ 提取结果                                    │
│ ☑ 音频文件     │ 类型 | 文件名 | 大小 | 详情                  │
│ ☑ 图片文件     │ ...                                        │
│ ☑ PDF 文档     │                                            │
│ ☑ 按类型分文件夹│                                            │
│ ☑ 完成后打开目录│                                            │
│ [开始提取]     ├─────────────────────────────────────────────┤
│               │ 处理日志                                    │
│ 待处理文件     │ ...                                        │
│ ...           │                                            │
├───────────────┴─────────────────────────────────────────────┤
│ 就绪                                    [进度条]            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 操作步骤

1. 点击「选择文件」，可一次选中多个 `.goodnotes`；或点击「选择目录（批量）」，
   程序会递归扫描该目录及子目录；
2. 在左侧勾选要提取的类型；
3. 可选：点击「输出目录…」指定输出位置。未指定时，输出到源文件同级的
   `<笔记名>_提取`；
4. 点击「开始提取」；
5. 在右侧查看结果和日志。提取过程中可点击菜单「操作 → 停止」中断；
6. 菜单「操作 → 清除结果」清空表格，不会删除已导出的文件。

### 2.3 输出位置

- **指定了输出目录**：`<输出目录>/<笔记名>/音频|图片|文档/`
- **未指定输出目录**：`<源文件所在目录>/<笔记名>_提取/音频|图片|文档/`

## 3. 命令行

### 3.1 语法

```text
gn-extract <文件.goodnotes> [输出目录] [选项]
gn-extract --gui
gn-extract --batch <目录> [输出目录]
gn-extract --info <文件.goodnotes>
```

### 3.2 参数

| 参数 | 说明 |
| --- | --- |
| `<文件.goodnotes>` | 输入文件 |
| `[输出目录]` | 输出位置，默认是源文件同级的 `<笔记名>_提取` |
| `--gui` | 启动图形界面 |
| `--batch <目录>` | 批量处理目录下所有 `.goodnotes` |
| `--info <文件>` | 只显示元数据，不导出 |
| `--no-audio` | 不导出音频 |
| `--no-image` | 不导出图片 |
| `--no-pdf` | 不导出 PDF |
| `--no-organize` | 所有附件放在同一目录，不分类 |
| `-v, --version` | 显示版本 |
| `-h, --help` | 显示帮助 |

### 3.3 示例

```bash
# 提取单个文件
gn-extract 汽车工艺学复习.goodnotes

# 指定输出目录
gn-extract 笔记.goodnotes D:\导出结果

# 只要音频
gn-extract 笔记.goodnotes --no-image --no-pdf

# 不分类，全部平铺
gn-extract 笔记.goodnotes D:\导出 --no-organize

# 批量处理整个目录
gn-extract --batch D:\GoodNotes备份 D:\导出结果

# 查看元数据
gn-extract --info 笔记.goodnotes
```

`--info` 输出包含：数据模式版本、笔记页数量、附件文件数量、事件记录数量、
附件总大小、最后修改时间，以及每个附件的类型、文件名、大小和子类型。

### 3.4 无参数运行

在资源管理器中双击 exe（或直接运行 `gn-extract`）时：

- 如果当前目录有 `.goodnotes` 文件，自动提取第一个；
- 否则打印帮助并等待回车，方便查看输出。

### 3.5 退出码

当前版本所有成功/失败路径都返回 0。脚本中判断是否成功，请检查输出目录是否生成
目标文件。后续版本可能改为标准退出码。

## 4. 输出文件

### 4.1 目录结构

```text
笔记名_提取/
├── 音频/
│   ├── 录音_11m26s.m4a
│   └── 录音_0m31s.m4a
├── 图片/
│   ├── 图片_2048x1536.jpg
│   └── 图片_1855x998.png
└── 文档/
    └── 文档_A08519D7.pdf
```

使用 `--no-organize` 或取消勾选「按类型分文件夹」后，所有文件直接放在输出根目录。

### 4.2 命名规则

| 类型 | 规则 | 说明 |
| --- | --- | --- |
| 音频 | `录音_<分>m<秒>s.m4a` | 无法解析时长时用 `录音_<UUID前8位>.m4a` |
| 图片 | `图片_<宽>x<高>.<ext>` | 无法解析尺寸时用 `图片_<UUID前8位>.<ext>` |
| PDF | `文档_<原附件名前8位>.pdf` | 原附件名通常是 UUID |

同名文件自动追加 `_1`、`_2`，不会覆盖。

## 5. 配置与日志

### 5.1 配置文件

位置：`~/.goodnotes-extractor/config.json`（Windows 为
`C:\Users\<用户名>\.goodnotes-extractor\config.json`）。

首次运行时自动生成，包含输出目录、类型开关、界面尺寸、日志级别等默认值。
修改后重启程序生效。删除该文件可恢复默认配置。

### 5.2 环境变量

| 变量 | 作用 |
| --- | --- |
| `GNOTES_OUTPUT_DIR` | 默认输出目录 |
| `GNOTES_LANG` | 界面语言（预留） |
| `GNOTES_LOG_LEVEL` | 日志级别：DEBUG/INFO/WARNING/ERROR |
| `GNOTES_FFMPEG_PATH` | ffmpeg 可执行文件路径 |

### 5.3 日志

位置：`~/.goodnotes-extractor/logs/`，文件名形如 `extract_20261017_113000.log`。
最多保留最近 10 个，超出自动删除。

提交 Issue 前，请先删除日志中的个人路径和文件名。

## 6. 格式转换（可选）

`converter.py` 提供以下库 API，当前**未接入** CLI 和 GUI：

- `convert_m4a_to_wav` / `convert_m4a_to_mp3`：优先调用 ffmpeg，找不到时回退到
  纯 Python 的 WAV 写入；
- `convert_image_format` / `resize_image`：需要安装 Pillow
  （`pip install -e ".[images]"`）。

如果你需要界面化的转换功能，欢迎提交 Feature Request。

## 7. 常见问题

### 7.1 提示"不是有效的 .goodnotes 文件"

- 确认文件确实由 GoodNotes 导出，且扩展名为 `.goodnotes`；
- 确认文件没有在传输中损坏（可尝试用压缩软件打开，正常应能看到
  `schema.pb`、`index.*.pb`、`attachments/`）；
- 如果是加密或经过第三方云盘"在线预览"处理过的文件，可能已损坏。

### 7.2 提取数量为 0

- 导出时可能没有包含附件。请在 GoodNotes 中重新导出并勾选包含录音/音频；
- 检查是否取消了对应类型的勾选；
- 用 `--info` 查看容器中是否真的存在附件。

### 7.3 音频无法播放

- 用 VLC 或 ffmpeg 检查文件是否完整；
- 部分录音的 `moov` 在文件尾部，个别播放器兼容性差，可转成 WAV：

  ```bash
  ffmpeg -i 录音_11m26s.m4a 录音.wav
  ```

### 7.4 批量处理很慢

- 附件越多、文件越大，耗时越长；
- 把输入和输出放在不同磁盘可减少 I/O 竞争；
- 先用 `--info` 确认容器大小，避免处理不需要的大文件。

### 7.5 Windows 提示病毒/风险

PyInstaller 打包的未签名 exe 偶尔会被杀毒软件误报。可以：

- 从源码运行；
- 按 README 的步骤自行构建；
- 把 exe 上传到 VirusTotal 查看多引擎结果。

## 8. 隐私与数据

- 程序不联网、不上传、不收集任何信息；
- 只读取你指定的 `.goodnotes` 文件；
- 输出只写入你指定的目录；
- 配置和日志保存在用户主目录，卸载时手动删除即可。

## 9. 卸载

- exe 版：删除 exe；
- 源码版：`pip uninstall goodnotes-attachment-extractor`，并删除克隆的目录；
- 可选：删除 `~/.goodnotes-extractor/` 以清除配置与日志。

## 10. 声明

本项目是独立的第三方、非官方工具，与 GoodNotes 的开发者
Time Base Technology Limited 无任何关联。GoodNotes 是其注册商标。
请只处理你本人拥有或已获授权的文件。

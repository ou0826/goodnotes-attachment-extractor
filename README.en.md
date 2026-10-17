<p align="center">
  <img src="docs/images/banner.png" alt="GoodNotes Attachment Extractor" width="100%">
</p>

<p align="center">
  <b>Extract audio recordings, images, and PDF documents from .goodnotes files</b><br/>
  <sub>Formerly: Protobuf-based Note Attachment Parsing and Restoration System</sub>
</p>

<p align="center">
  <a href="https://github.com/ou0826/goodnotes-attachment-extractor/actions/workflows/ci.yml"><img src="https://github.com/ou0826/goodnotes-attachment-extractor/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/ou0826/goodnotes-attachment-extractor/releases"><img src="https://img.shields.io/github/v/release/ou0826/goodnotes-attachment-extractor?include_prereleases" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&amp;logoColor=white" alt="Python"></a>
</p>

> **Unofficial tool**: This is an independent third-party project. It is not
> affiliated with, endorsed by, or sponsored by Time Base Technology Limited,
> the developer of GoodNotes. GoodNotes is a registered trademark of its owner.
> Only process files that you own or are authorized to access.

<p align="center">
  <img src="docs/images/gui.png" alt="GUI screenshot" width="860">
  <br>
  <sub>GUI: file list, type filters, extraction results, and logs</sub>
</p>

## Features

<table>
  <tr>
    <td align="center" width="33%">🎧<br/><b>Audio</b><br/><sub>M4A / AAC<br/>duration-aware filenames</sub></td>
    <td align="center" width="33%">🖼️<br/><b>Images</b><br/><sub>JPEG / PNG<br/>resolution-aware filenames</sub></td>
    <td align="center" width="33%">📄<br/><b>PDF</b><br/><sub>Original documents<br/>UUID-prefixed names</sub></td>
  </tr>
  <tr>
    <td align="center">📦<br/><b>Batch mode</b><br/><sub>Recursive folder scan<br/>multiple notes at once</sub></td>
    <td align="center">🖥️<br/><b>GUI + CLI</b><br/><sub>Desktop interface<br/>scriptable command line</sub></td>
    <td align="center">🔒<br/><b>Offline</b><br/><sub>No network requests<br/>No runtime dependencies</sub></td>
  </tr>
</table>

## Why

A <code>.goodnotes</code> file is a ZIP container. Attachments live under
<code>attachments/</code> with UUID filenames and no extensions, which makes them
hard to identify after unzipping. This tool detects the real type from magic
bytes, parses container metadata, and writes readable filenames.

| Raw ZIP contents | After extraction |
| --- | --- |
| <code>attachments/4F2A9C...</code> | <code>音频/录音_11m26s.m4a</code> |
| <code>attachments/A08519...</code> | <code>图片/图片_2048x1536.png</code> |
| <code>attachments/D34B78...</code> | <code>文档/文档_D34B7852.pdf</code> |

## Quick start

### Download (Windows, no Python required)

1. Open [Releases](https://github.com/ou0826/goodnotes-attachment-extractor/releases);
2. Download one of:

| File | Purpose |
| --- | --- |
| <code>...-win64-GUI.exe</code> | GUI build; double-click to open (recommended) |
| <code>...-win64.exe</code> | CLI build for scripts and batch jobs |

3. For the CLI build, run <code>... --gui</code> to open the GUI.

### Install from source

~~~bash
git clone https://github.com/ou0826/goodnotes-attachment-extractor.git
cd goodnotes-attachment-extractor
python -m pip install -e .
gn-extract --gui
~~~

Requires Python 3.9+.

## Usage

~~~text
gn-extract <file.goodnotes> [output_dir]
gn-extract --gui
gn-extract --batch <directory> [output_dir]
gn-extract --info <file.goodnotes>
~~~

Run <code>gn-extract --help</code> for all options.

Output layout:

~~~text
笔记名_提取/
├── 音频/录音_11m26s.m4a
├── 图片/图片_2048x1536.png
└── 文档/文档_D34B7852.pdf
~~~

## How it works

~~~mermaid
flowchart LR
    A[".goodnotes ZIP"] --> B["Read attachments/"]
    B --> C{"Magic-byte type detection"}
    C -->|M4A / AAC| D["音频/录音_11m26s.m4a"]
    C -->|JPEG / PNG| E["图片/图片_2048x1536.png"]
    C -->|PDF| F["文档/文档_D34B7852.pdf"]
~~~

See [docs/design.md](docs/design.md) for module details.

## Development

~~~bash
python -m pip install -e ".[dev]"
pytest
python scripts/build_exe.py
~~~

## Contributing

Issues and pull requests are welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) and follow
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE). See [NOTICE](NOTICE) for trademark and third-party notices.

This project has applied for software copyright registration.

## Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. The authors are
not responsible for data loss or damage. Back up your notes before use.

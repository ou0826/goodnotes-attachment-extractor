# 贡献指南

感谢你愿意帮助改进 GoodNotes 附件提取器！本文面向第一次参与开源项目的贡献者，
按顺序做完即可提交一个合格的 Issue 或 Pull Request（PR）。

## 目录

- [行为准则](#行为准则)
- [报告问题](#报告问题)
- [开发环境](#开发环境)
- [代码结构](#代码结构)
- [测试](#测试)
- [代码风格](#代码风格)
- [提交信息](#提交信息)
- [提交 Pull Request](#提交-pull-request)
- [不要提交的内容](#不要提交的内容)

## 行为准则

参与本项目即表示你同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
请保持友善、就事论事，尊重不同经验和背景的贡献者。

## 报告问题

- **Bug**：使用 [Bug Report 模板](.github/ISSUE_TEMPLATE/bug_report.yml)，
  写清楚系统版本、Python 版本、复现步骤、期望结果和实际结果。
- **功能建议**：使用 [Feature Request 模板](.github/ISSUE_TEMPLATE/feature_request.yml)，
  说明使用场景，而不只是"希望加一个功能"。
- **安全问题**：不要公开提交 Issue，请按 [SECURITY.md](SECURITY.md) 私下报告。

> 提交前请先搜索现有 Issue，避免重复。

## 开发环境

```bash
git clone https://github.com/ou0826/goodnotes-attachment-extractor.git
cd goodnotes-attachment-extractor

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python -m pip install -e ".[dev]"
```

运行程序：

```bash
python -m goodnotes_extractor --help
python -m goodnotes_extractor --gui
```

## 代码结构

| 路径 | 职责 |
| --- | --- |
| `src/goodnotes_extractor/cli.py` | 命令行入口、单文件提取、批量提取 |
| `src/goodnotes_extractor/gui.py` | Tkinter 图形界面 |
| `src/goodnotes_extractor/parser.py` | MP4/JPEG/PNG/PDF 二进制解析 |
| `src/goodnotes_extractor/classifier.py` | 魔术字节类型识别 |
| `src/goodnotes_extractor/metadata.py` | Protobuf 索引解码 |
| `src/goodnotes_extractor/batch.py` | 批量处理与去重 |
| `src/goodnotes_extractor/converter.py` | 可选的格式转换（库 API） |
| `src/goodnotes_extractor/config.py` | 配置管理 |
| `src/goodnotes_extractor/logger.py` | 日志管理 |
| `tests/` | 单元测试 |

修改导出逻辑时，注意 CLI 与 GUI 各有一份提取实现，尽量让两边的行为保持一致。

## 测试

项目同时支持 `pytest` 和标准库 `unittest`：

```bash
pytest
# 或
python -m unittest discover -s tests -v
```

- 新功能请补充对应测试；
- 修复 Bug 时，最好先写一个能复现问题的测试；
- 提交 PR 前请确保全部测试通过。

## 代码风格

- 遵循 PEP 8，4 空格缩进；
- 函数与类使用中文 docstring（与现有代码保持一致）；
- 不做与当前任务无关的大规模重构；
- 不引入新的运行时依赖。确有必要时，请在 Issue 中先讨论；
- 面向用户的文案使用简体中文，代码标识符使用英文。

## 提交信息

推荐使用简短的 Conventional Commits 风格：

```text
feat: 支持解析 .goodnotes 中的 HEIC 图片
fix: 修复批量模式下同名文件被覆盖的问题
docs: 补充 macOS 安装说明
test: 增加 JPEG 尺寸解析边界用例
chore: 更新 CI 的 Python 版本
```

第一行控制在 72 个字符以内，需要时在空行后补充详细说明。

## 提交 Pull Request

1. Fork 本仓库，从 `main` 创建一个语义化的分支：

   ```bash
   git checkout -b feat/heic-support
   ```

2. 完成修改并补充测试；
3. 本地运行测试，确保全部通过；
4. 提交并推送到你的 Fork：

   ```bash
   git add .
   git commit -m "feat: 支持 HEIC 图片"
   git push origin feat/heic-support
   ```

5. 在 GitHub 上发起 Pull Request，按模板填写：
   - 这个 PR 解决了什么问题；
   - 做了哪些修改；
   - 如何验证（测试命令、手动步骤）；
   - 是否影响现有行为。

PR 合并前需要至少一次维护者审查，CI 必须通过。

## 不要提交的内容

以下内容**绝对不要**出现在 Issue、PR、提交历史或仓库中：

- 任何真实的 `.goodnotes` 文件或从其中提取的笔记内容；
- 身份证、学生证、证书、签章页等个人证件扫描件；
- 日志中包含的个人路径、文件名、用户名；
- 打包生成的 `.exe`（请通过 Releases 分发）；
- 其他项目的申请材料、代码文档或商业软件安装包。

如果需要提供复现材料，请自行构造一个**不含个人内容**的最小 `.goodnotes` 文件，
或只描述 ZIP 内部结构。

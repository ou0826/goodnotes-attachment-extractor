# Agent Skills

本仓库附带一个 Agent Skill，让 Claude Code、Codex、Cursor 等代理直接处理
GoodNotes 导出的 <code>.goodnotes</code> 文件。

## goodnotes-attachment-extractor

- 提取 M4A 录音、JPEG/PNG 图片、PDF 文档
- 支持 <code>--info</code> 元数据查看、<code>--json</code> 机器可读输出、目录批量、按类型分文件夹
- 纯 Python 标准库，本地运行，不上传任何内容

### 用 skills CLI 安装（推荐）

~~~bash
npx skills add ou0826/goodnotes-attachment-extractor
~~~

安装后可以直接对代理说：

> 把这个 .goodnotes 里的录音和图片导出来

### 手动安装

~~~bash
# Claude Code
cp -r skills/goodnotes-attachment-extractor ~/.claude/skills/

# DSH
cp -r skills/goodnotes-attachment-extractor ~/.dsh/skills/
~~~

### 直接运行

~~~bash
python skills/goodnotes-attachment-extractor/scripts/gn_extract.py --info "笔记.goodnotes"
python skills/goodnotes-attachment-extractor/scripts/gn_extract.py "笔记.goodnotes" -o "导出目录"
~~~

### 搜索

- GitHub：https://github.com/ou0826/goodnotes-attachment-extractor/tree/main/skills/goodnotes-attachment-extractor
- skills.sh：被收录后可在 https://skills.sh/ 搜索 goodnotes attachment extractor

技能的结构遵循 Agent Skills 约定：一个目录 + <code>SKILL.md</code> + 可选
<code>scripts/</code>、<code>references/</code>、<code>assets/</code>。

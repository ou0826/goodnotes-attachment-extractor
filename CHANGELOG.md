# Changelog

本项目的重要变更都会记录在此文件中。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [1.0.0] - 2026-10-17

### 首个开源版本

- 将原「基于协议缓冲区的笔记附件解析与还原系统 V1.0」重构为标准 Python 包
  `goodnotes_extractor`，提供 `gn-extract` 与 `gn-extract-gui` 两个命令。
- 支持从 `.goodnotes` 容器提取 M4A 音频、JPEG/PNG 图片和 PDF 文档。
- 支持按类型分文件夹、批量递归扫描、同名文件自动编号。
- 提供 Tkinter 图形界面和命令行接口。
- 提供 `--info` 元数据查看、`--version` 版本查询。
- 提供 74 个单元测试、GitHub Actions CI 和自动构建发布工作流。
- 采用 MIT 许可证开源，新增商标与第三方组件声明。

### 变更

- 产品名由「基于协议缓冲区的笔记附件解析与还原系统」简化为
  「GoodNotes 附件提取器」，原名称保留为项目副标题。
- 图形界面「关于」对话框改为中性的兼容性描述，并加入非官方声明。
- 模块路径由 `core/*.py` 调整为 `src/goodnotes_extractor/*.py`。

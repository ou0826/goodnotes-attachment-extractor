"""
批量处理模块
支持一次处理多个 .goodnotes 文件、合并输出、递归扫描目录等
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable


# ============================================================
#  批量扫描
# ============================================================

def find_goodnotes_files(
    search_dir: str,
    recursive: bool = True,
) -> list:
    """在指定目录中递归查找所有 .goodnotes 文件。

    Args:
        search_dir: 搜索起始目录
        recursive: 是否递归搜索子目录

    Returns:
        Path 对象列表
    """
    search_path = Path(search_dir)
    if not search_path.exists():
        return []

    if recursive:
        return sorted(search_path.rglob("*.goodnotes"))
    else:
        return sorted(search_path.glob("*.goodnotes"))


def scan_directory_for_archives(directory: str) -> dict:
    """扫描目录并按照 .goodnotes 文件分组。

    返回每个文件的基本信息字典。

    Args:
        directory: 目录路径

    Returns:
        {文件路径: {size, modified, stem}} 字典
    """
    results = {}
    for gn_path in find_goodnotes_files(directory):
        stat = gn_path.stat()
        results[str(gn_path)] = {
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "stem": gn_path.stem,
        }
    return results


# ============================================================
#  批量处理引擎
# ============================================================

class BatchProcessor:
    """批量处理控制器。

    管理多个 .goodnotes 文件的提取流程，支持进度回调和
    结果聚合。处理过程包括：打开 ZIP → 分类文件 →
    解析元数据 → 写出文件 → 汇总统计。
    """

    def __init__(self):
        self.total_inputs: int = 0
        self.processed_inputs: int = 0
        self.total_extracted: int = 0
        self.errors: list = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数。

        callback(processed: int, total: int, current_file: str, stage: str)
        """
        self._progress_callback = callback

    def _report_progress(self, current_file: str, stage: str):
        """向回调函数报告当前进度。"""
        if self._progress_callback:
            self._progress_callback(
                self.processed_inputs,
                self.total_inputs,
                current_file,
                stage,
            )

    def process_multiple(
        self,
        input_files: list,
        output_base_dir: str,
        merge_output: bool = False,
        extract_func: Callable = None,
    ) -> dict:
        """批量处理多个 .goodnotes 文件。

        Args:
            input_files: .goodnotes 文件路径列表
            output_base_dir: 输出基础目录
            merge_output: 是否将输出合并到同一目录
            extract_func: 单文件提取函数，签名为 f(path, output_dir) -> list

        Returns:
            {
                "total_inputs": 输入文件总数,
                "processed": 成功处理数,
                "failed": 失败数,
                "total_extracted": 总提取文件数,
                "extracted_per_input": {文件: 数量},
                "errors": [(文件, 错误信息)],
                "elapsed_seconds": 耗时秒数,
            }
        """
        self.start_time = datetime.now()
        self.total_inputs = len(input_files)
        self.processed_inputs = 0
        self.total_extracted = 0
        self.errors = []

        summary = {
            "total_inputs": self.total_inputs,
            "processed": 0,
            "failed": 0,
            "total_extracted": 0,
            "extracted_per_input": {},
            "errors": [],
            "elapsed_seconds": 0,
        }

        output_base = Path(output_base_dir)

        for gn_path in input_files:
            gn_path = Path(gn_path)
            self._report_progress(gn_path.name, "开始处理")

            try:
                if merge_output:
                    out_dir = output_base / "合并输出"
                else:
                    out_dir = output_base / gn_path.stem

                if extract_func:
                    extracted = extract_func(str(gn_path), str(out_dir))
                else:
                    from core.parser import parse_mp4_audio_metadata, classify_file
                    extracted = []
                    # 如果没有传入提取函数，只做扫描不做提取
                    pass

                self.processed_inputs += 1
                self.total_extracted += len(extracted) if extracted else 0
                summary["processed"] += 1
                summary["total_extracted"] += len(extracted) if extracted else 0
                summary["extracted_per_input"][gn_path.name] = (
                    len(extracted) if extracted else 0
                )

            except Exception as e:
                self.errors.append((gn_path.name, str(e)))
                summary["failed"] += 1
                summary["errors"].append((gn_path.name, str(e)))

            self._report_progress(gn_path.name, "完成")

        self.end_time = datetime.now()
        summary["elapsed_seconds"] = (
            self.end_time - self.start_time
        ).total_seconds()

        return summary

    def get_statistics(self) -> dict:
        """获取处理统计信息。"""
        if self.start_time and self.end_time:
            elapsed = (self.end_time - self.start_time).total_seconds()
        else:
            elapsed = 0

        return {
            "processed": self.processed_inputs,
            "total": self.total_inputs,
            "extracted_files": self.total_extracted,
            "error_count": len(self.errors),
            "elapsed_seconds": elapsed,
            "files_per_second": (
                self.processed_inputs / elapsed if elapsed > 0 else 0
            ),
        }


# ============================================================
#  输出组织
# ============================================================

def organize_output_by_date(
    output_dir: str,
    date: datetime = None,
) -> Path:
    """根据日期创建分层的输出目录。

    格式：output_dir/YYYY-MM/DD/

    Args:
        output_dir: 基础输出目录
        date: 日期（默认今天）

    Returns:
        创建的目录路径
    """
    if date is None:
        date = datetime.now()

    subdir = Path(output_dir) / date.strftime("%Y-%m") / date.strftime("%d")
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir


def merge_directories(
    source_dirs: list,
    target_dir: str,
    overwrite: bool = False,
) -> dict:
    """将多个目录的内容合并到目标目录。

    按文件哈希进行去重处理。

    Args:
        source_dirs: 源目录列表
        target_dir: 目标目录
        overwrite: 是否覆盖同名文件

    Returns:
        {"copied": n, "skipped": n, "duplicates": n}
    """
    import hashlib

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    result = {"copied": 0, "skipped": 0, "duplicates": 0}
    seen_hashes = {}

    # 先扫描目标目录的哈希
    for f in target.rglob("*"):
        if f.is_file():
            h = _file_sha256(f)
            seen_hashes[h] = f.name

    for src_dir in source_dirs:
        src = Path(src_dir)
        if not src.exists():
            continue

        for f in src.rglob("*"):
            if not f.is_file():
                continue

            h = _file_sha256(f)
            if h in seen_hashes:
                result["duplicates"] += 1
                if not overwrite:
                    result["skipped"] += 1
                    continue

            dest = target / f.name
            counter = 1
            while dest.exists() and not overwrite:
                dest = target / f"{f.stem}_{counter}{f.suffix}"
                counter += 1

            import shutil
            shutil.copy2(f, dest)
            seen_hashes[h] = dest.name
            result["copied"] += 1

    return result


def _file_sha256(filepath: Path) -> str:
    """计算文件的 SHA-256 哈希值。"""
    import hashlib
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

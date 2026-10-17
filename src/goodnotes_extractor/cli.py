"""
GoodNotes 附件提取器 - 命令行入口

用法:
  gn-extract <文件.goodnotes> [输出目录]    # 提取单个文件
  gn-extract --gui                          # 启动图形界面
  gn-extract --batch <目录> [输出目录]      # 批量提取
  gn-extract --info <文件.goodnotes>        # 查看元数据
"""

import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime

from .classifier import classify_file, FileCategory, classify_file_detailed
from .parser import (
    parse_mp4_audio_metadata,
    parse_jpeg_dimensions,
    parse_png_dimensions,
    parse_pdf_page_count,
    parse_pdf_version,
    verify_mp4_integrity,
)
from .metadata import (
    parse_goodnotes_index,
    format_metadata_summary,
    get_note_page_count,
)
from .batch import find_goodnotes_files, BatchProcessor
from .config import get_config
from .logger import setup_logging, get_logger
from . import __version__


def extract_single(
    goodnotes_path: str,
    output_dir: str = None,
    audio: bool = True,
    image: bool = True,
    pdf: bool = True,
    organize: bool = True,
) -> dict:
    """从单个 .goodnotes 文件提取所有附件。

    Args:
        goodnotes_path: .goodnotes 文件路径
        output_dir: 输出目录，默认在同目录下创建「笔记名_提取」文件夹
        audio: 是否提取音频
        image: 是否提取图片
        pdf: 是否提取PDF
        organize: 是否按类型分文件夹

    Returns:
        {"audio": n, "image": n, "pdf": n, "total": n, "errors": [...]}
    """
    logger = get_logger("extractor")
    gn_path = Path(goodnotes_path)

    if not gn_path.exists():
        raise FileNotFoundError(f"找不到文件: {goodnotes_path}")

    if output_dir is None:
        output_dir = gn_path.parent / f"{gn_path.stem}_提取"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    counts = {"audio": 0, "image": 0, "pdf": 0, "total": 0, "errors": []}
    out_subdirs = {}
    if organize:
        for cat, name in [("audio", "音频"), ("image", "图片"), ("pdf", "文档")]:
            d = output_dir / name
            d.mkdir(parents=True, exist_ok=True)
            out_subdirs[cat] = d

    logger.info(f"开始提取: {gn_path.name}")

    try:
        with zipfile.ZipFile(goodnotes_path, "r") as zf:
            # 收集附件成员
            members = [
                m for m in zf.namelist()
                if m.startswith("attachments/") and not m.endswith("/")
            ]
            members += [
                m for m in zf.namelist()
                if not m.startswith("attachments/") and not m.endswith("/")
                and not m.endswith(".pb") and m != "schema.pb"
            ]

            logger.info(f"找到 {len(members)} 个候选附件")

            for member in members:
                try:
                    with zf.open(member) as f:
                        header = f.read(12)
                        full_data = header + f.read()
                except Exception as e:
                    counts["errors"].append((member, str(e)))
                    continue

                ftype = classify_file(full_data)

                # 类型过滤
                if ftype == FileCategory.AUDIO and not audio:
                    continue
                if ftype == FileCategory.IMAGE and not image:
                    continue
                if ftype == FileCategory.PDF and not pdf:
                    continue
                if ftype in (FileCategory.VIDEO, FileCategory.UNKNOWN,
                             FileCategory.PROTOBUF):
                    continue

                # 构建文件名
                if ftype == FileCategory.AUDIO:
                    meta = parse_mp4_audio_metadata(full_data)
                    dur = meta.get("duration", 0)
                    if dur > 0:
                        mins, secs = int(dur // 60), int(dur % 60)
                        name = f"录音_{mins}m{secs:02d}s.m4a"
                    else:
                        name = f"录音_{Path(member).stem[:8]}.m4a"
                    dest_dir = out_subdirs.get("audio", output_dir)
                    counts["audio"] += 1
                elif ftype == FileCategory.IMAGE:
                    if full_data[:8] == b"\x89PNG\r\n\x1a\n":
                        w, h = parse_png_dimensions(full_data)
                        ext = ".png"
                    else:
                        w, h = parse_jpeg_dimensions(full_data)
                        ext = ".jpg"
                    name = f"图片_{w}x{h}{ext}" if w > 0 else f"图片_{Path(member).stem[:8]}{ext}"
                    dest_dir = out_subdirs.get("image", output_dir)
                    counts["image"] += 1
                elif ftype == FileCategory.PDF:
                    name = f"文档_{Path(member).stem[:8]}.pdf"
                    dest_dir = out_subdirs.get("pdf", output_dir)
                    counts["pdf"] += 1
                else:
                    continue

                # 写出
                out_path = dest_dir / name
                counter = 1
                while out_path.exists():
                    stem, ext = os.path.splitext(name)
                    out_path = dest_dir / f"{stem}_{counter}{ext}"
                    counter += 1

                out_path.write_bytes(full_data)
                size_kb = len(full_data) / 1024
                logger.info(f"  [{ftype}] {out_path.name} ({size_kb:.0f} KB)")
                counts["total"] += 1

    except zipfile.BadZipFile:
        raise ValueError(f"'{goodnotes_path}' 不是有效的 .goodnotes 文件")

    return counts


def show_metadata(goodnotes_path: str):
    """显示 .goodnotes 文件的元数据信息。"""
    logger = get_logger("metadata")

    try:
        with zipfile.ZipFile(goodnotes_path, "r") as zf:
            meta = parse_goodnotes_index(zf)

            # 获取每个附件的详细信息
            attachment_details = []
            for member in zf.namelist():
                if member.startswith("attachments/") and not member.endswith("/"):
                    try:
                        with zf.open(member) as f:
                            data = f.read()
                        detail = classify_file_detailed(data, member)
                        size = len(data)
                        attachment_details.append({
                            "path": member,
                            "size": size,
                            "category": detail["category"],
                            "subtype": detail["subtype"],
                            "mime": detail["mime"],
                        })
                    except Exception:
                        pass

            # 打印摘要
            print(format_metadata_summary(meta))
            print()
            print("附件详情:")
            for ad in attachment_details:
                print(f"  [{FileCategory.label(ad['category']):6s}] "
                      f"{Path(ad['path']).name}  "
                      f"{ad['size']/1024:>7.1f} KB  "
                      f"{ad.get('subtype', '')}")

    except zipfile.BadZipFile:
        raise ValueError(f"'{goodnotes_path}' 不是有效的 .goodnotes 文件")


def batch_extract(directory: str, output_dir: str = None) -> dict:
    """批量处理目录中的所有 .goodnotes 文件。

    Args:
        directory: 包含 .goodnotes 文件的目录
        output_dir: 输出根目录

    Returns:
        批量处理汇总
    """
    files = find_goodnotes_files(directory, recursive=True)
    if not files:
        print(f"在 '{directory}' 中未找到 .goodnotes 文件")
        return {}

    print(f"找到 {len(files)} 个 .goodnotes 文件\n")

    processor = BatchProcessor()
    results = processor.process_multiple(
        input_files=[str(f) for f in files],
        output_base_dir=output_dir or directory,
        merge_output=False,
        extract_func=extract_single,
    )

    # 打印汇总
    print()
    print("=" * 60)
    print("  批量提取完成")
    print(f"  处理: {results['processed']}/{results['total_inputs']} 个文件")
    print(f"  总提取: {results['total_extracted']} 个附件")
    if results["errors"]:
        print(f"  失败: {len(results['errors'])} 个")
        for name, err in results["errors"]:
            print(f"    - {name}: {err}")
    if results["elapsed_seconds"] > 0:
        print(f"  耗时: {results['elapsed_seconds']:.1f} 秒")
    print("=" * 60)

    return results


# ============================================================
#  命令行解析
# ============================================================

def print_usage():
    """打印使用说明。"""
    print(f"GoodNotes 附件提取器 v{__version__}")
    print()
    print("用法:")
    print("  gn-extract <文件.goodnotes> [输出目录]")
    print("  gn-extract --gui")
    print("  gn-extract --batch <目录> [输出目录]")
    print("  gn-extract --info <文件.goodnotes>")
    print()
    print("选项:")
    print("  --gui          启动图形用户界面")
    print("  --batch        批量处理目录中的所有 .goodnotes 文件")
    print("  --info         查看 .goodnotes 文件的元数据信息")
    print("  --no-audio     不提取音频文件")
    print("  --no-image     不提取图片文件")
    print("  --no-pdf       不提取PDF文档")
    print("  --no-organize  不按类型分文件夹")
    print("  -v, --version  显示版本号")
    print("  -h, --help     显示本帮助")


def main():
    setup_logging()

    if len(sys.argv) == 1:
        # 无参数：尝试自动发现 .goodnotes 文件
        cwd = Path.cwd()
        candidates = list(cwd.glob("*.goodnotes"))
        if candidates:
            print("自动检测到 .goodnotes 文件，开始提取...")
            result = extract_single(str(candidates[0]))
            print(f"\n提取完成: 音频{result['audio']}个, 图片{result['image']}个, "
                  f"PDF{result['pdf']}个, 合计{result['total']}个")
        else:
            print_usage()
            print()
            print("提示: 将 .goodnotes 文件拖放到本程序图标上即可提取")
            try:
                input("按 Enter 退出...")
            except (EOFError, OSError):
                pass
        return

    if sys.argv[1] == "--gui":
        from .gui import main as gui_main
        gui_main()
        return

    if sys.argv[1] == "--help" or sys.argv[1] == "-h":
        print_usage()
        return

    if sys.argv[1] in ("--version", "-v"):
        print(f"GoodNotes 附件提取器 v{__version__}")
        return

    if sys.argv[1] == "--info":
        if len(sys.argv) < 3:
            print("请指定 .goodnotes 文件: --info <文件.goodnotes>")
            return
        try:
            show_metadata(sys.argv[2])
        except Exception as e:
            print(f"错误: {e}")
        return

    if sys.argv[1] == "--batch":
        if len(sys.argv) < 3:
            print("请指定目录: --batch <目录> [输出目录]")
            return
        output = sys.argv[3] if len(sys.argv) >= 4 else None
        try:
            batch_extract(sys.argv[2], output)
        except Exception as e:
            print(f"错误: {e}")
        return

    # 单个文件提取
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else None

    # 解析选项
    audio = "--no-audio" not in sys.argv
    image = "--no-image" not in sys.argv
    pdf = "--no-pdf" not in sys.argv
    organize = "--no-organize" not in sys.argv

    try:
        print("=" * 60)
        print(f"  GoodNotes 附件提取器 v{__version__}")
        print("=" * 60)
        print()

        result = extract_single(input_path, output_dir, audio, image, pdf, organize)

        print()
        print(f"提取完成!")
        print(f"  音频: {result['audio']} 个")
        print(f"  图片: {result['image']} 个")
        print(f"  文档: {result['pdf']} 个")
        print(f"  合计: {result['total']} 个文件")

        if result["errors"]:
            print(f"  失败: {len(result['errors'])} 个")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

    # 双击运行时暂停
    if not sys.stdout.isatty():
        try:
            print()
            input("按 Enter 退出...")
        except (EOFError, OSError):
            pass


if __name__ == "__main__":
    main()

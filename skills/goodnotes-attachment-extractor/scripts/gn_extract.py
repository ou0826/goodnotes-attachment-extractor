#!/usr/bin/env python3
"""Extract audio, images and PDFs from GoodNotes .goodnotes exports.

Standard library only. Read-only: never modifies the source file.

Usage:
  python gn_extract.py --info FILE.goodnotes
  python gn_extract.py FILE.goodnotes -o OUTDIR
  python gn_extract.py DIRECTORY -o OUTDIR --json
"""

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path

VIDEO_SIGS = (
    b"avc1", b"avc3", b"hvc1", b"hev1", b"mp4v",
    b"encv", b"mjp2", b"s263", b"vp09", b"av01",
)
AUDIO_SIGS = (b"mp4a", b"ac-3", b"opus", b"alac", b"aac ")
SOF_MARKERS = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
PNG_SIG = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
JPEG_SOI = bytes([0xFF, 0xD8])


def classify(data):
    """Return audio / video / image / pdf / unknown from magic bytes."""
    if len(data) < 12:
        return "unknown"
    if data[4:8] == b"ftyp":
        if any(sig in data for sig in VIDEO_SIGS):
            return "video"
        if any(sig in data for sig in AUDIO_SIGS):
            return "audio"
        return "unknown"
    if data[:8] == PNG_SIG:
        return "image"
    if data[:2] == JPEG_SOI:
        return "image"
    if data[:5] == b"%PDF-":
        return "pdf"
    return "unknown"


def mp4_duration(data):
    """Read duration in seconds from moov/mvhd."""
    pos = 0
    while pos + 8 <= len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        atom = data[pos + 4:pos + 8]
        if size < 8:
            break
        if atom == b"moov":
            body = pos + 8
            end = min(pos + size, len(data))
            p = body
            while p + 8 <= end:
                child = struct.unpack(">I", data[p:p + 4])[0]
                kind = data[p + 4:p + 8]
                if child < 8:
                    break
                if kind == b"mvhd":
                    b = p + 8
                    ver = data[b]
                    if ver == 0:
                        ts = struct.unpack(">I", data[b + 12:b + 16])[0]
                        dur = struct.unpack(">I", data[b + 16:b + 20])[0]
                    elif ver == 1:
                        ts = struct.unpack(">I", data[b + 20:b + 24])[0]
                        dur = struct.unpack(">Q", data[b + 24:b + 32])[0]
                    else:
                        return 0.0
                    return dur / ts if ts else 0.0
                p += child
        pos += size
    return 0.0


def jpeg_size(data):
    """Return (width, height) from a JPEG SOF segment."""
    pos = 2
    while pos + 9 <= len(data):
        if data[pos] != 0xFF:
            return (0, 0)
        marker = data[pos + 1]
        if marker == 0xD9:
            break
        if marker in SOF_MARKERS:
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return (width, height)
        if pos + 4 > len(data):
            break
        seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if seg_len < 2:
            break
        pos += 2 + seg_len
    return (0, 0)


def png_size(data):
    if len(data) < 24:
        return (0, 0)
    return struct.unpack(">II", data[16:24])


def pdf_info(data):
    version = "?"
    newline = bytes([10])
    end = data.find(newline)
    header = data[:end if end > 0 else 16].decode("ascii", "replace").strip()
    if header.startswith("%PDF-"):
        version = header[5:]
    return version


def attachment_members(zf):
    names = zf.namelist()
    members = [n for n in names if n.startswith("attachments/") and not n.endswith("/")]
    members += [
        n for n in names
        if not n.startswith("attachments/") and not n.endswith("/")
        and not n.endswith(".pb") and n != "schema.pb"
    ]
    return members


def describe(data):
    kind = classify(data)
    item = {"category": kind, "size": len(data)}
    if kind == "audio":
        item["duration"] = round(mp4_duration(data), 2)
    elif kind == "image":
        w, h = png_size(data) if data[:8] == PNG_SIG else jpeg_size(data)
        item["width"], item["height"] = w, h
    elif kind == "pdf":
        item["pdf_version"] = pdf_info(data)
    return item


def safe_destination(directory, name):
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def info_one(path):
    result = {
        "input": str(path),
        "schema_version": None,
        "members": 0,
        "counts": {"audio": 0, "image": 0, "pdf": 0, "other": 0},
        "total_size": 0,
        "items": [],
    }
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "schema.pb" in names:
            raw = zf.read("schema.pb")[:2]
            if len(raw) == 2:
                result["schema_version"] = struct.unpack("<H", raw)[0]
        members = attachment_members(zf)
        result["members"] = len(members)
        for member in members:
            data = zf.read(member)
            detail = describe(data)
            kind = detail["category"]
            if kind not in ("audio", "image", "pdf"):
                result["counts"]["other"] += 1
                continue
            detail["member"] = member
            result["items"].append(detail)
            result["counts"][kind] += 1
            result["total_size"] += detail["size"]
    return result


def extract_one(path, output, organize=True, audio=True, image=True, pdf=True):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "input": str(path),
        "output": str(output),
        "counts": {"audio": 0, "image": 0, "pdf": 0, "total": 0},
        "files": [],
        "errors": [],
    }
    subdirs = {"audio": "音频", "image": "图片", "pdf": "文档"}
    with zipfile.ZipFile(path) as zf:
        for member in attachment_members(zf):
            try:
                data = zf.read(member)
            except Exception as exc:
                result["errors"].append(f"{member}: {exc}")
                continue
            kind = classify(data)
            if kind == "audio":
                if not audio:
                    continue
                duration = mp4_duration(data)
                if duration > 0:
                    minutes, seconds = int(duration // 60), int(duration % 60)
                    name = f"录音_{minutes}m{seconds:02d}s.m4a"
                else:
                    name = f"录音_{Path(member).stem[:8]}.m4a"
            elif kind == "image":
                if not image:
                    continue
                if data[:8] == PNG_SIG:
                    width, height = png_size(data)
                    ext = ".png"
                else:
                    width, height = jpeg_size(data)
                    ext = ".jpg"
                if width > 0:
                    name = f"图片_{width}x{height}{ext}"
                else:
                    name = f"图片_{Path(member).stem[:8]}{ext}"
            elif kind == "pdf":
                if not pdf:
                    continue
                name = f"文档_{Path(member).stem[:8]}.pdf"
            else:
                continue

            destination_dir = output / subdirs[kind] if organize else output
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = safe_destination(destination_dir, name)
            try:
                destination.write_bytes(data)
            except OSError as exc:
                result["errors"].append(f"{member}: {exc}")
                continue
            result["counts"][kind] += 1
            result["counts"]["total"] += 1
            result["files"].append(str(destination.relative_to(output)))
    return result


def print_info(result):
    print(f"File: {result['input']}")
    print(f"Schema: {result['schema_version']}  Members: {result['members']}")
    counts = result["counts"]
    print(f"audio={counts['audio']} image={counts['image']} pdf={counts['pdf']} other={counts['other']}")
    for item in result["items"]:
        if item["category"] == "audio":
            extra = f"{item.get('duration', 0)}s"
        elif item["category"] == "image":
            extra = f"{item.get('width', 0)}x{item.get('height', 0)}"
        else:
            extra = f"PDF {item.get('pdf_version', '?')}"
        print(f"  [{item['category']}] {Path(item['member']).name}  {item['size'] / 1024:.1f} KB  {extra}")


def print_extract(result):
    if "error" in result:
        print(f"FAILED: {result['input']} - {result['error']}", file=sys.stderr)
        return
    counts = result["counts"]
    print(f"Extracted: {result['input']}")
    print(f"  output: {result['output']}")
    print(f"  audio={counts['audio']} image={counts['image']} pdf={counts['pdf']} total={counts['total']}")
    if result["errors"]:
        print(f"  errors: {len(result['errors'])}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract audio, images and PDFs from .goodnotes files."
    )
    parser.add_argument("input", help=".goodnotes file or directory to scan")
    parser.add_argument("-o", "--output", help="output directory")
    parser.add_argument("--info", action="store_true", help="inspect only, do not extract")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--no-organize", action="store_true", help="do not split by type")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--no-image", action="store_true")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--version", action="version", version="1.0.0")
    args = parser.parse_args(argv)

    source = Path(args.input).expanduser()
    if not source.exists():
        print(f"Input not found: {source}", file=sys.stderr)
        return 1
    inputs = sorted(source.rglob("*.goodnotes")) if source.is_dir() else [source]
    if not inputs:
        print(f"No .goodnotes files found in: {source}", file=sys.stderr)
        return 1

    results = []
    for path in inputs:
        try:
            if args.info:
                results.append(info_one(path))
            else:
                if args.output:
                    base = Path(args.output).expanduser()
                    out = base / f"{path.stem}_提取" if len(inputs) > 1 else base
                else:
                    out = path.parent / f"{path.stem}_提取"
                results.append(
                    extract_one(
                        path,
                        out,
                        organize=not args.no_organize,
                        audio=not args.no_audio,
                        image=not args.no_image,
                        pdf=not args.no_pdf,
                    )
                )
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            results.append({"input": str(path), "error": str(exc)})

    if args.json:
        print(json.dumps(results, ensure_ascii=True, indent=2))
    elif args.info:
        for index, result in enumerate(results):
            if index:
                print()
            print_info(result)
    else:
        for result in results:
            print_extract(result)

    return 0 if any("error" not in item for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

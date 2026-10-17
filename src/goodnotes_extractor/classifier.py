"""
文件类型识别与分类模块
通过二进制魔术字节（magic bytes）识别文件格式，
区分音频/视频/图片/文档等类别
"""

from typing import Optional, Tuple


# ============================================================
#  文件类型枚举
# ============================================================

class FileCategory:
    """文件类别常量定义。"""
    AUDIO = "audio"        # M4A/MP4 纯音频
    VIDEO = "video"        # MP4 带视频轨道
    IMAGE = "image"        # JPEG/PNG 图片
    PDF = "pdf"            # PDF 文档
    PROTOBUF = "protobuf"  # Protocol Buffer 数据
    UNKNOWN = "unknown"    # 无法识别

    _LABELS = {
        "audio": "音频文件",
        "video": "视频文件",
        "image": "图片文件",
        "pdf": "PDF文档",
        "protobuf": "数据文件",
        "unknown": "未知格式",
    }

    @classmethod
    def label(cls, category: str) -> str:
        """返回类别的中文标签。"""
        return cls._LABELS.get(category, "未知格式")


# ============================================================
#  视频编解码器特征码
# ============================================================

_VIDEO_CODEC_SIGNATURES = [
    b"avc1",   # H.264/AVC
    b"avc3",   # H.264/AVC (parameter sets in-band)
    b"hvc1",   # H.265/HEVC
    b"hev1",   # H.265/HEVC (alternative)
    b"mp4v",   # MPEG-4 Part 2 Visual
    b"encv",   # Encrypted video
    b"mjp2",   # Motion JPEG 2000
    b"s263",   # H.263
    b"vp09",   # VP9
    b"av01",   # AV1
]


def _has_video_codec(data: bytes) -> bool:
    """检查 MP4 容器是否包含视频编解码器特征码。"""
    return any(sig in data for sig in _VIDEO_CODEC_SIGNATURES)


def _has_audio_codec(data: bytes) -> bool:
    """检查 MP4 容器是否包含音频编解码器特征码。"""
    return b"mp4a" in data or b"ac-3" in data or b"opus" in data or b"alac" in data


# ============================================================
#  主分类函数
# ============================================================

def classify_file(data: bytes) -> str:
    """根据二进制魔术字节识别文件类型。

    检测顺序：
      1. MP4 容器 (ftyp) → 区分视频/纯音频
      2. JPEG (0xFF 0xD8 0xFF 0xE0-EF)
      3. PNG (8字节固定签名)
      4. PDF (%PDF-)
      5. Protocol Buffer (启发式检测)

    Args:
        data: 文件的完整二进制数据

    Returns:
        FileCategory 常量之一 (audio/video/image/pdf/protobuf/unknown)
    """
    if len(data) < 12:
        return FileCategory.UNKNOWN

    # MP4/M4A/MOV 容器格式
    if data[4:8] == b"ftyp":
        if _has_video_codec(data):
            return FileCategory.VIDEO
        if _has_audio_codec(data):
            return FileCategory.AUDIO
        # 有 ftyp 但无视频也无音频编解码器 → 可能是非标准容器
        return FileCategory.UNKNOWN

    # JPEG 图像 (SOI + APP0/APP1)
    if data[:2] == b"\xff\xd8":
        if len(data) >= 4 and data[2] == 0xFF and 0xE0 <= data[3] <= 0xEF:
            return FileCategory.IMAGE
        # 也可能是 JPEG（无 EXIF/JFIF APP段），进一步检查
        if b"\xff\xdb" in data[:4096] and b"\xff\xc0" in data[:4096]:
            return FileCategory.IMAGE
        return FileCategory.UNKNOWN

    # PNG 图像
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return FileCategory.IMAGE

    # PDF 文档
    if data[:5] == b"%PDF-":
        return FileCategory.PDF

    # Protocol Buffer (启发式：检查 .pb 扩展名对应的数据模式)
    if _looks_like_protobuf(data):
        return FileCategory.PROTOBUF

    return FileCategory.UNKNOWN


def classify_file_detailed(data: bytes, filename: str = "") -> dict:
    """详细分类，返回类别、子类型和置信度。

    Args:
        data: 文件的完整二进制数据
        filename: 文件名（可选，用于辅助判断）

    Returns:
        包含 category/subtype/confidence/mime 的字典
    """
    result = {
        "category": FileCategory.UNKNOWN,
        "subtype": "",
        "confidence": 0.0,
        "mime": "application/octet-stream",
    }

    category = classify_file(data)

    if category == FileCategory.AUDIO:
        result["category"] = FileCategory.AUDIO
        result["subtype"] = "AAC" if b"mp4a" in data else "Audio"
        result["confidence"] = 0.95
        result["mime"] = "audio/mp4"

    elif category == FileCategory.VIDEO:
        result["category"] = FileCategory.VIDEO
        if b"avc1" in data or b"avc3" in data:
            result["subtype"] = "H.264"
        elif b"hvc1" in data or b"hev1" in data:
            result["subtype"] = "H.265/HEVC"
        elif b"vp09" in data:
            result["subtype"] = "VP9"
        elif b"av01" in data:
            result["subtype"] = "AV1"
        else:
            result["subtype"] = "Video"
        result["confidence"] = 0.95
        result["mime"] = "video/mp4"

    elif category == FileCategory.IMAGE:
        result["category"] = FileCategory.IMAGE
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            result["subtype"] = "PNG"
            result["mime"] = "image/png"
        else:
            result["subtype"] = "JPEG"
            result["mime"] = "image/jpeg"
        result["confidence"] = 0.99

    elif category == FileCategory.PDF:
        result["category"] = FileCategory.PDF
        result["subtype"] = "PDF"
        result["confidence"] = 0.99
        result["mime"] = "application/pdf"

    elif category == FileCategory.PROTOBUF:
        result["category"] = FileCategory.PROTOBUF
        result["subtype"] = "ProtocolBuffer"
        result["confidence"] = 0.70
        result["mime"] = "application/x-protobuf"

    return result


# ============================================================
#  Protocol Buffer 启发式检测
# ============================================================

def _looks_like_protobuf(data: bytes) -> bool:
    """启发式判断数据是否可能是 Protocol Buffer 编码。

    由于 protobuf 没有标准文件头，使用以下经验规则：
      - 较小的文件（< 1MB，因为索引文件通常不大）
      - 包含大量高位字节（protobuf varint 特征）
      - 数据不是纯文本（不可打印字符比例较高）

    Args:
        data: 二进制数据

    Returns:
        是否可能为 protobuf 数据
    """
    size = len(data)
    # protobuf 索引文件通常不超过 500KB
    if size > 500 * 1024:
        return False

    # 采样检查不可打印字符比例
    sample_size = min(size, 4096)
    sample = data[:sample_size]

    non_printable = sum(1 for b in sample if b < 0x20 and b not in (0x09, 0x0A, 0x0D))
    ratio = non_printable / sample_size

    # 如果超过 20% 的字节不可打印，可能是二进制格式
    return ratio > 0.20


# ============================================================
#  文件扩展名建议
# ============================================================

_EXTENSION_MAP = {
    FileCategory.AUDIO: ".m4a",
    FileCategory.IMAGE: "",   # 需要进一步区分 JPEG/PNG
    FileCategory.PDF: ".pdf",
    FileCategory.VIDEO: ".mp4",
}


def suggest_extension(category: str, data: bytes = None) -> str:
    """根据文件类别和二进制内容建议文件扩展名。

    Args:
        category: FileCategory 类别
        data: 文件数据（用于区分 JPEG/PNG），可选

    Returns:
        建议的扩展名字符串（含点号）
    """
    if category == FileCategory.IMAGE and data is not None:
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        return ".jpg"

    return _EXTENSION_MAP.get(category, "")


# ============================================================
#  批量分类
# ============================================================

def classify_files_batch(file_data_map: dict) -> dict:
    """对多个文件进行批量分类。

    Args:
        file_data_map: {文件名: 二进制数据} 映射

    Returns:
        {文件名: 分类结果字典} 映射
    """
    results = {}
    for filename, data in file_data_map.items():
        results[filename] = classify_file_detailed(data, filename)
    return results


def get_category_statistics(classification_results: dict) -> dict:
    """统计批量分类结果中各类别的文件数量和总大小。

    Args:
        classification_results: classify_files_batch 的输出

    Returns:
        {类别: {"count": n, "total_size": bytes}} 统计字典
    """
    stats = {}
    for filename, info in classification_results.items():
        cat = info["category"]
        if cat not in stats:
            stats[cat] = {"count": 0, "total_size": 0}
        stats[cat]["count"] += 1
    return stats

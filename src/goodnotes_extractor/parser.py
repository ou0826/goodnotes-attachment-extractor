"""
二进制格式解析引擎
解析 MP4/M4A、JPEG、PNG 等容器格式的元数据

支持格式：
  - ISO Base Media File Format (MP4/M4A/MOV)
  - JPEG (JFIF/EXIF)
  - PNG (IHDR块)
  - PDF 文档头识别
"""

import struct
from typing import Optional, Tuple, Dict


# ============================================================
#  MP4 / M4A 容器格式解析
# ============================================================

def parse_mp4_atom_tree(data: bytes) -> list:
    """将 MP4 文件解析为原子树的顶层节点列表。

    遍历 ISO BMFF 字节流，按照每个原子的 4 字节大端长度 + 4 字节类型标记
    逐级拆分顶层原子。返回包含偏移、长度、类型名和子原子的字典列表。

    Args:
        data: MP4 容器文件的完整二进制数据

    Returns:
        顶层原子列表，每个原子为 dict，包含 offset/size/type/children 字段
    """
    atoms = []
    pos = 0
    data_len = len(data)

    while pos + 8 <= data_len:
        if pos + 4 > data_len:
            break
        atom_size = struct.unpack(">I", data[pos:pos + 4])[0]
        if atom_size == 0:
            atom_size = data_len - pos
        if atom_size < 8 or pos + atom_size > data_len:
            break
        atom_type = data[pos + 4:pos + 8].decode("ascii", errors="replace")
        atoms.append({
            "offset": pos,
            "size": atom_size,
            "type": atom_type,
        })
        pos += atom_size

    return atoms


def parse_mp4_audio_metadata(data: bytes) -> Dict[str, int]:
    """从 MP4/M4A 文件的 moov 原子中提取音频元数据。

    解析 moov → trak → mdia → mdhd（时长/时间刻度）以及
    moov → trak → mdia → minf → stbl → stsd → mp4a（采样率/声道数）。
    支持 mvhd 版本 0（32 位字段）和版本 1（64 位字段）。

    Args:
        data: MP4/M4A 文件的完整二进制数据

    Returns:
        字典，键为 duration(秒)、sample_rate(Hz)、channels、timescale、duration_raw
    """
    result = {
        "duration": 0,
        "sample_rate": 0,
        "channels": 0,
        "timescale": 0,
        "duration_raw": 0,
    }

    pos = 0
    while pos + 8 <= len(data):
        atom_size = struct.unpack(">I", data[pos:pos + 4])[0]
        if atom_size <= 0 or pos + atom_size > len(data):
            break
        atom_type = data[pos + 4:pos + 8]

        if atom_type == b"moov":
            _parse_moov_children(data, pos + 8, pos + atom_size, result)

        pos += atom_size

    return result


def _parse_moov_children(data: bytes, start: int, end: int, result: dict):
    """解析 moov 容器内的子原子。"""
    pos = start
    while pos + 8 <= end:
        child_size = struct.unpack(">I", data[pos:pos + 4])[0]
        child_type = data[pos + 4:pos + 8]
        if child_size <= 0 or pos + child_size > end:
            break

        if child_type == b"mvhd":
            _parse_mvhd(data, pos + 8, result)

        elif child_type == b"trak":
            _parse_trak(data, pos + 8, pos + child_size, result)

        pos += child_size


def _parse_mvhd(data: bytes, body_start: int, result: dict):
    """解析 mvhd（movie header）原子中的时长和时间刻度。

    mvhd 结构（body_start 指向 version 字节）:
      version(1) + flags(3) + creation_time(4或8) + modification_time(4或8)
      + timescale(4) + duration(4或8)
    """
    ver = data[body_start]
    if ver == 0:
        ts = struct.unpack(">I", data[body_start + 12:body_start + 16])[0]
        dur = struct.unpack(">I", data[body_start + 16:body_start + 20])[0]
    elif ver == 1:
        ts = struct.unpack(">I", data[body_start + 20:body_start + 24])[0]
        dur = struct.unpack(">Q", data[body_start + 24:body_start + 32])[0]
    else:
        return

    if ts > 0:
        result["timescale"] = ts
        result["duration_raw"] = dur
        result["duration"] = int(dur / ts * 1000) / 1000.0


def _parse_trak(data: bytes, start: int, end: int, result: dict):
    """解析单个 trak 原子，查找音频轨道配置。"""
    pos = start
    has_mp4a = False

    while pos + 8 <= end:
        child_size = struct.unpack(">I", data[pos:pos + 4])[0]
        child_type = data[pos + 4:pos + 8]
        if child_size <= 0 or pos + child_size > end:
            break

        if child_type == b"mdia":
            # 在 mdia 内部递归查找 minf → stbl → stsd → mp4a
            _parse_mdia_for_audio(data, pos + 8, pos + child_size, result)

        pos += child_size


def _parse_mdia_for_audio(data: bytes, start: int, end: int, result: dict):
    """在 mdia 容器内查找音频采样信息。"""
    pos = start
    while pos + 8 <= end:
        child_size = struct.unpack(">I", data[pos:pos + 4])[0]
        child_type = data[pos + 4:pos + 8]
        if child_size <= 0 or pos + child_size > end:
            break

        if child_type == b"minf":
            _parse_minf_for_audio(data, pos + 8, pos + child_size, result)

        pos += child_size


def _parse_minf_for_audio(data: bytes, start: int, end: int, result: dict):
    """在 minf 容器内查找 stbl → stsd → mp4a。"""
    pos = start
    while pos + 8 <= end:
        child_size = struct.unpack(">I", data[pos:pos + 4])[0]
        child_type = data[pos + 4:pos + 8]
        if child_size <= 0 or pos + child_size > end:
            break

        if child_type == b"stbl":
            _parse_stbl_for_mp4a(data, pos + 8, pos + child_size, result)

        pos += child_size


def _parse_stbl_for_mp4a(data: bytes, start: int, end: int, result: dict):
    """在 stbl 容器内查找 stsd → mp4a。"""
    pos = start
    while pos + 8 <= end:
        child_size = struct.unpack(">I", data[pos:pos + 4])[0]
        child_type = data[pos + 4:pos + 8]
        if child_size <= 0 or pos + child_size > end:
            break

        if child_type == b"stsd":
            # stsd body: version(1) + flags(3) + entry_count(4) + entries...
            # 每个 entry: size(4) + type(4) + data
            body = pos + 8
            if body + 8 <= end:
                entry_count = struct.unpack(">I", data[body + 4:body + 8])[0]
                entry_pos = body + 8
                for _ in range(entry_count):
                    if entry_pos + 8 > end:
                        break
                    entry_size = struct.unpack(">I", data[entry_pos:entry_pos + 4])[0]
                    entry_type = data[entry_pos + 4:entry_pos + 8]
                    if entry_type == b"mp4a" and not result.get("sample_rate"):
                        _parse_mp4a_entry(data, entry_pos + 8, result)
                    entry_pos += entry_size

        pos += child_size


def _parse_mp4a_entry(data: bytes, body_start: int, result: dict):
    """解析 mp4a（MPEG-4 Audio）条目中的采样率和声道数。

    mp4a 条目结构:
      reserved(6) + data_reference_index(2) + version(2) + revision(2)
      + vendor(4) + channels(2) + sample_size(2) + compression_id(2)
      + packet_size(2) + sample_rate(4, 16.16定点数)
    """
    if body_start + 28 > len(data):
        return

    channels = struct.unpack(">H", data[body_start + 16:body_start + 18])[0]
    sr_raw = struct.unpack(">I", data[body_start + 24:body_start + 28])[0]
    sample_rate = sr_raw >> 16  # 16.16 定点数转整数

    if channels > 0:
        result["channels"] = channels
    if sample_rate > 0:
        result["sample_rate"] = sample_rate


def estimate_audio_duration_from_size(
    file_size: int,
    sample_rate: int = 22050,
    channels: int = 2,
    bits_per_sample: int = 16,
    compression_ratio: float = 8.0,
) -> float:
    """根据文件大小和编码参数估算音频时长。

    使用 AAC 典型压缩比（~8:1）从原始 PCM 比特率反推时长。
    原始比特率 = 采样率 × 位深 × 声道数
    编码后比特率 ≈ 原始比特率 / 压缩比
    时长 = 文件大小 × 8 / 编码后比特率

    Args:
        file_size: 文件大小（字节）
        sample_rate: 采样频率（Hz），默认 22050
        channels: 声道数，默认 2
        bits_per_sample: 采样位深，默认 16
        compression_ratio: 压缩比，默认 8.0

    Returns:
        估算的时长（秒）
    """
    raw_bitrate = sample_rate * bits_per_sample * channels
    encoded_bitrate = raw_bitrate / compression_ratio
    return file_size * 8 / encoded_bitrate


def verify_mp4_integrity(data: bytes) -> Tuple[bool, str]:
    """校验 MP4/M4A 文件结构完整性。

    检查项：ftyp 标记、moov 原子存在性、mdat 原子存在性、
    音频轨道可用性。

    Args:
        data: MP4 文件的完整二进制数据

    Returns:
        (是否通过, 状态描述)
    """
    if len(data) < 24:
        return False, "文件长度不足 24 字节，不是有效的 MP4 容器"

    if data[4:8] != b"ftyp":
        return False, "缺少 ftyp 标记"

    has_moov = b"moov" in data
    has_mdat = b"mdat" in data
    has_mp4a = b"mp4a" in data

    if not has_moov:
        return False, "缺少 moov 原子（元数据容器）"
    if not has_mdat:
        return False, "缺少 mdat 原子（媒体数据容器）"
    if not has_mp4a:
        return False, "缺少 mp4a 条目（音频轨道描述）"

    # 检查 moov 原子是否在文件末尾（需要修复的典型问题）
    moov_pos = data.rfind(b"moov")
    mdat_pos = data.rfind(b"mdat")
    if moov_pos > mdat_pos:
        return True, "结构正常（moov 位于文件末尾）"
    elif moov_pos < mdat_pos:
        return True, "结构正常（moov 位于文件开头，支持流式播放）"

    return True, "校验通过"


def read_mp4_sample_data(data: bytes, max_samples: int = 10) -> list:
    """从 stsz/stz2 原子中读取采样大小信息。

    采样大小表用于定位每个 AAC 帧的边界，是精确计算时长的关键。

    Args:
        data: MP4 文件的完整二进制数据
        max_samples: 最多返回的采样数

    Returns:
        采样大小列表（字节）
    """
    # 查找 stsz 或 stz2 原子
    for atom_name in [b"stsz", b"stz2"]:
        pos = data.find(atom_name)
        if pos < 8:
            continue

        atom_size = struct.unpack(">I", data[pos - 4:pos])[0]
        body_start = pos + 4
        body_end = pos - 4 + atom_size

        if body_start + 12 > body_end:
            continue

        ver = data[body_start]
        sample_size = struct.unpack(">I", data[body_start + 4:body_start + 8])[0]
        sample_count = struct.unpack(">I", data[body_start + 8:body_start + 12])[0]

        if sample_size == 0 and sample_count > 0:
            # 每个采样大小单独存储
            sizes = []
            table_start = body_start + 12
            actual_count = min(sample_count, max_samples)
            for i in range(actual_count):
                offset = table_start + i * 4
                if offset + 4 <= body_end:
                    size = struct.unpack(">I", data[offset:offset + 4])[0]
                    sizes.append(size)
            return sizes
        elif sample_size > 0:
            return [sample_size] * min(sample_count, max_samples)

    return []


# ============================================================
#  JPEG 图像格式解析
# ============================================================

# JPEG 标记码定义
JPEG_MARKER_SOI = 0xD8    # Start of Image
JPEG_MARKER_SOF0 = 0xC0   # Baseline DCT
JPEG_MARKER_SOF1 = 0xC1   # Extended sequential DCT
JPEG_MARKER_SOF2 = 0xC2   # Progressive DCT
JPEG_MARKER_APP0 = 0xE0   # JFIF
JPEG_MARKER_APP1 = 0xE1   # EXIF
JPEG_MARKER_DQT = 0xDB    # Quantization Table
JPEG_MARKER_DHT = 0xC4    # Huffman Table
JPEG_MARKER_SOS = 0xDA    # Start of Scan
JPEG_MARKER_EOI = 0xD9    # End of Image

SOF_MARKERS = {JPEG_MARKER_SOF0, JPEG_MARKER_SOF1, JPEG_MARKER_SOF2}


def parse_jpeg_dimensions(data: bytes) -> Tuple[int, int]:
    """从 JPEG 二进制数据中解析图像宽度和高度。

    扫描 JPEG 段标记（每段格式：0xFF + 标记码 + 2字节段长度 + 段数据），
    定位到 SOF（Start of Frame）标记后读取尺寸字段。

    Args:
        data: JPEG 文件的二进制数据

    Returns:
        (宽度, 高度) 元组；解析失败返回 (0, 0)
    """
    if len(data) < 4:
        return (0, 0)

    pos = 2  # 跳过 SOI 标记 (0xFF, 0xD8)

    while pos < len(data) - 9:
        if data[pos] != 0xFF:
            break

        marker = data[pos + 1]
        if marker == JPEG_MARKER_EOI:
            break

        if marker in SOF_MARKERS:
            # SOF 段格式：[长度(2)][精度(1)][高度(2)][宽度(2)][分量数(1)]...
            if pos + 9 <= len(data):
                height = struct.unpack(">H", data[pos + 5:pos + 7])[0]
                width = struct.unpack(">H", data[pos + 7:pos + 9])[0]
                return (width, height)
            break

        # 跳过非 SOF 段
        seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        pos += 2 + seg_len

    return (0, 0)


def parse_jpeg_exif_orientation(data: bytes) -> int:
    """从 JPEG EXIF 数据中读取照片旋转方向。

    EXIF Orientation 标签（0x0112）的值：
      1 = 正常, 3 = 旋转180°, 6 = 旋转90°顺时针, 8 = 旋转90°逆时针

    Args:
        data: JPEG 文件的二进制数据

    Returns:
        方向值，默认为 1（正常）
    """
    # 查找 APP1 标记（EXIF）
    app1_pos = data.find(b"\xff\xe1")
    if app1_pos < 0:
        return 1

    # 跳过 APP1 段头（标记2+长度2+EXIF标识6=10字节）
    tiff_start = app1_pos + 10
    if tiff_start + 8 > len(data):
        return 1

    # 读取 TIFF 字节序
    byte_order = data[tiff_start:tiff_start + 2]
    if byte_order == b"II":
        endian = "<"  # Intel (little-endian)
    elif byte_order == b"MM":
        endian = ">"  # Motorola (big-endian)
    else:
        return 1

    # 验证 TIFF 标识 (0x002A)
    tiff_magic = struct.unpack(endian + "H", data[tiff_start + 2:tiff_start + 4])[0]
    if tiff_magic != 0x002A:
        return 1

    # IFD0 偏移
    ifd_offset = struct.unpack(endian + "I", data[tiff_start + 4:tiff_start + 8])[0]
    ifd_pos = tiff_start + ifd_offset

    # 遍历 IFD 条目
    if ifd_pos + 2 > len(data):
        return 1
    entry_count = struct.unpack(endian + "H", data[ifd_pos:ifd_pos + 2])[0]
    entry_base = ifd_pos + 2

    for i in range(entry_count):
        entry_pos = entry_base + i * 12
        if entry_pos + 12 > len(data):
            break
        tag_id = struct.unpack(endian + "H", data[entry_pos:entry_pos + 2])[0]
        if tag_id == 0x0112:  # Orientation 标签
            orientation = struct.unpack(
                endian + "H", data[entry_pos + 8:entry_pos + 10]
            )[0]
            return orientation

    return 1


def parse_jpeg_quality_estimate(data: bytes) -> int:
    """根据 JPEG 量化表估算压缩质量因子。

    通过分析 DQT 段中的量化表系数推算编码质量（1-100）。
    基于广泛使用的 ImageMagick 算法：系数均值映射到质量范围。

    Args:
        data: JPEG 文件的二进制数据

    Returns:
        估算的质量因子 (1-100)，未知时返回 -1
    """
    # 查找 DQT 段
    dqt_positions = []
    search_pos = 0
    while True:
        pos = data.find(b"\xff\xdb", search_pos)
        if pos < 0:
            break
        dqt_positions.append(pos)
        search_pos = pos + 2

    if not dqt_positions:
        return -1

    # 读取第一个量化表
    first_dqt = dqt_positions[0]
    seg_len = struct.unpack(">H", data[first_dqt + 2:first_dqt + 4])[0]
    table_data_start = first_dqt + 4
    table_data_end = table_data_start + seg_len - 2

    if table_data_end > len(data):
        return -1

    table_data = data[table_data_start:table_data_end]
    if len(table_data) < 64:
        return -1

    # 计算量化系数的调和平均值
    sum_q = 0
    count = 0
    for i in range(min(64, len(table_data))):
        val = table_data[i]
        if val > 0:
            sum_q += val
            count += 1

    if count == 0:
        return -1

    avg_q = sum_q / count

    # 将量化均值映射到质量因子（经验公式）
    if avg_q < 5:
        quality = 100
    elif avg_q < 10:
        quality = 90
    elif avg_q < 15:
        quality = 80
    elif avg_q < 25:
        quality = 70
    elif avg_q < 35:
        quality = 60
    elif avg_q < 50:
        quality = 50
    elif avg_q < 70:
        quality = 40
    else:
        quality = 30

    return quality


# ============================================================
#  PNG 图像格式解析
# ============================================================

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_png_dimensions(data: bytes) -> Tuple[int, int]:
    """从 PNG 二进制数据中解析图像宽度和高度。

    PNG 结构：8 字节签名 + IHDR 块（长度4 + "IHDR"4 + 宽度4 + 高度4 + ...）

    Args:
        data: PNG 文件的二进制数据

    Returns:
        (宽度, 高度) 元组；解析失败返回 (0, 0)
    """
    if len(data) < 24 or data[:8] != PNG_SIGNATURE:
        return (0, 0)

    width = struct.unpack(">I", data[16:20])[0]
    height = struct.unpack(">I", data[20:24])[0]
    return (width, height)


def parse_png_color_info(data: bytes) -> Dict[str, int]:
    """从 PNG IHDR 块中提取颜色信息。

    返回色深、颜色类型、压缩方法等元数据。

    Args:
        data: PNG 文件的二进制数据

    Returns:
        颜色信息字典
    """
    result = {"bit_depth": 0, "color_type": 0, "compression": 0, "filter": 0, "interlace": 0}

    if len(data) < 29 or data[:8] != PNG_SIGNATURE:
        return result

    result["bit_depth"] = data[24]
    result["color_type"] = data[25]
    result["compression"] = data[26]
    result["filter"] = data[27]
    result["interlace"] = data[28]

    return result


# PNG 颜色类型常量
PNG_COLOR_GRAYSCALE = 0
PNG_COLOR_RGB = 2
PNG_COLOR_INDEXED = 3
PNG_COLOR_GRAYSCALE_ALPHA = 4
PNG_COLOR_RGBA = 6

_PNG_COLOR_TYPE_NAMES = {
    0: "灰度",
    2: "RGB",
    3: "索引色",
    4: "灰度+Alpha",
    6: "RGBA",
}


def png_color_type_name(color_type: int) -> str:
    """返回 PNG 颜色类型的中文名称。"""
    return _PNG_COLOR_TYPE_NAMES.get(color_type, f"未知({color_type})")


def parse_png_chunks(data: bytes) -> list:
    """提取 PNG 文件中所有块（chunk）的类型和长度列表。

    Args:
        data: PNG 文件的二进制数据

    Returns:
        块列表，每个元素为 (类型名, 数据长度)
    """
    chunks = []
    if len(data) < 8 or data[:8] != PNG_SIGNATURE:
        return chunks

    pos = 8
    while pos < len(data) - 12:
        chunk_len = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8].decode("ascii", errors="replace")
        chunks.append((chunk_type, chunk_len))
        pos += 12 + chunk_len
        if chunk_type == "IEND":
            break

    return chunks


# ============================================================
#  PDF 文档检测
# ============================================================

def is_pdf_document(data: bytes) -> bool:
    """检测数据是否为 PDF 文档。

    简单的签名匹配：前 5 字节是否为 '%PDF-'

    Args:
        data: 二进制数据（至少 5 字节）

    Returns:
        是否为 PDF 文档
    """
    return len(data) >= 5 and data[:5] == b"%PDF-"


def parse_pdf_version(data: bytes) -> str:
    """从 PDF 文件头中提取版本号。

    PDF 文件以 '%PDF-X.Y' 开头，如 '%PDF-1.7'

    Args:
        data: PDF 文件的二进制数据

    Returns:
        版本字符串，如 "1.7"
    """
    if len(data) < 8:
        return "未知"
    header_end = data.find(b"\n")
    if header_end < 0:
        header_end = min(16, len(data))
    header = data[:header_end].decode("ascii", errors="replace").strip()
    if header.startswith("%PDF-"):
        return header[5:]
    return "未知"


def parse_pdf_page_count(data: bytes) -> int:
    """通过扫描 PDF 二进制数据估算页数。

    搜索 '/Type /Page' 模式来统计页面对象数量。
    这是一阶近似，对于复杂 PDF 可能不准确。

    Args:
        data: PDF 文件的二进制数据

    Returns:
        估算的页数
    """
    # 搜索 "/Type/Page" 或 "/Type /Page" 模式
    count = 0
    search_pos = 0
    while True:
        pos = data.find(b"/Type", search_pos)
        if pos < 0:
            break
        remaining = data[pos:pos + 20]
        if b"/Page" in remaining[:15] or b" /Page" in remaining[:15]:
            count += 1
        search_pos = pos + 5
        if search_pos >= len(data):
            break
    return count

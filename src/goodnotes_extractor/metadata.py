"""
GoodNotes 元数据解析模块
解析 .goodnotes 容器中的 Protocol Buffer 索引文件，
提取笔记结构、附件映射、时间戳等信息

索引文件说明：
  - index.notes.pb    : 笔记页 UUID 到文件路径的映射
  - index.attachments.pb : 附件 UUID 到文件路径的映射
  - index.events.pb   : 笔记事件/操作日志
  - index.search.pb   : 搜索索引映射
  - schema.pb         : 数据模式版本标识
"""

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ============================================================
#  Protobuf 简单解码器
# ============================================================

class ProtobufWireType:
    """Protocol Buffer 线类型常量。"""
    VARINT = 0
    FIXED64 = 1
    LENGTH_DELIMITED = 2
    FIXED32 = 5


def _read_varint(data: bytes, offset: int) -> tuple:
    """读取 Protobuf varint 编码的整数。

    Args:
        data: 二进制数据
        offset: 起始偏移

    Returns:
        (整数值, 消耗的字节数)
    """
    result = 0
    shift = 0
    consumed = 0
    while offset + consumed < len(data):
        byte = data[offset + consumed]
        result |= (byte & 0x7F) << shift
        consumed += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift > 63:
            break
    return result, consumed


def _read_length_delimited(data: bytes, offset: int) -> tuple:
    """读取 Protobuf 长度分隔字段（字符串、嵌套消息、字节数组）。

    Args:
        data: 二进制数据
        offset: 起始偏移

    Returns:
        (字节内容, 消耗的总字节数)
    """
    length, varint_bytes = _read_varint(data, offset)
    content_start = offset + varint_bytes
    content_end = content_start + length
    if content_end > len(data):
        content_end = len(data)
    content = data[content_start:content_end]
    return content, varint_bytes + length


def _decode_tag(data: bytes, offset: int) -> tuple:
    """解码 Protobuf 字段标签（field_number + wire_type）。

    Args:
        data: 二进制数据
        offset: 起始偏移

    Returns:
        (field_number, wire_type, 消耗字节数)
    """
    tag, consumed = _read_varint(data, offset)
    field_number = tag >> 3
    wire_type = tag & 0x07
    return field_number, wire_type, consumed


# ============================================================
#  GoodNotes 专用元数据结构
# ============================================================

class GoodNotesMetadata:
    """GoodNotes 笔记文件的元数据容器。

    存储从索引文件中解析出的笔记结构信息，包括：
      - 笔记页列表和对应的文件路径
      - 附件列表（类型、大小、路径）
      - 事件记录（操作类型、时间戳）
      - 搜索索引条目
    """

    def __init__(self):
        self.notebook_title: str = ""
        self.note_count: int = 0
        self.attachment_count: int = 0
        self.event_count: int = 0
        self.notes: list = []          # [(uuid, rel_path), ...]
        self.attachments: list = []    # [(uuid, rel_path), ...]
        self.events: list = []         # [(timestamp, event_type, uuid), ...]
        self.schema_version: int = 0
        self.created_date: Optional[datetime] = None
        self.modified_date: Optional[datetime] = None
        self.total_size: int = 0


def parse_goodnotes_index(zipfile_obj) -> GoodNotesMetadata:
    """从 .goodnotes ZIP 中解析索引文件和元数据。

    读取 index.notes.pb、index.attachments.pb、index.events.pb、
    index.search.pb 和 schema.pb，提取笔记结构信息。

    Args:
        zipfile_obj: 已打开的 zipfile.ZipFile 对象

    Returns:
        GoodNotesMetadata 对象
    """
    meta = GoodNotesMetadata()

    # 解析 schema 版本
    if "schema.pb" in zipfile_obj.namelist():
        try:
            with zipfile_obj.open("schema.pb") as f:
                schema_data = f.read()
            if len(schema_data) >= 2:
                meta.schema_version = struct.unpack("<H", schema_data[:2])[0]
        except Exception:
            pass

    # 解析笔记索引
    if "index.notes.pb" in zipfile_obj.namelist():
        try:
            with zipfile_obj.open("index.notes.pb") as f:
                notes_data = f.read()
            meta.notes = _parse_string_map_protobuf(notes_data)
            meta.note_count = len(meta.notes)
        except Exception:
            pass

    # 解析附件索引
    if "index.attachments.pb" in zipfile_obj.namelist():
        try:
            with zipfile_obj.open("index.attachments.pb") as f:
                attach_data = f.read()
            meta.attachments = _parse_string_map_protobuf(attach_data)
            meta.attachment_count = len(meta.attachments)
        except Exception:
            pass

    # 解析事件索引
    if "index.events.pb" in zipfile_obj.namelist():
        try:
            with zipfile_obj.open("index.events.pb") as f:
                events_data = f.read()
            meta.events = _parse_events_protobuf(events_data)
            meta.event_count = len(meta.events)
        except Exception:
            pass

    # 从 ZIP 信息推断时间
    try:
        info = zipfile_obj.getinfo("index.notes.pb")
        if info.date_time:
            meta.modified_date = datetime(*info.date_time, tzinfo=timezone.utc)
    except Exception:
        pass

    # 统计附件总大小
    for name in zipfile_obj.namelist():
        if name.startswith("attachments/") and not name.endswith("/"):
            try:
                info = zipfile_obj.getinfo(name)
                meta.total_size += info.file_size
            except Exception:
                pass

    return meta


def _parse_string_map_protobuf(data: bytes) -> list:
    """解析 GoodNotes 中的字符串到字符串映射 protobuf 结构。

    GoodNotes 使用一种简化的序列化格式来存储 UUID → 文件路径 的映射：
      每条记录由 tag(1) + length + UUID + tag(2) + length + path 组成

    Args:
        data: protobuf 二进制数据

    Returns:
        [(uuid, rel_path), ...] 列表
    """
    entries = []
    offset = 0

    while offset < len(data) - 4:
        try:
            # 读取 UUID 字段 (field 1, string)
            fn1, wt1, consumed1 = _decode_tag(data, offset)
            if wt1 != ProtobufWireType.LENGTH_DELIMITED:
                break
            offset += consumed1
            uuid_bytes, consumed = _read_length_delimited(data, offset)
            offset += consumed
            uuid_str = uuid_bytes.decode("ascii", errors="replace")

            # 读取路径字段 (field 2, string)
            if offset >= len(data) - 2:
                break
            fn2, wt2, consumed2 = _decode_tag(data, offset)
            if wt2 != ProtobufWireType.LENGTH_DELIMITED:
                break
            offset += consumed2
            path_bytes, consumed = _read_length_delimited(data, offset)
            offset += consumed
            path_str = path_bytes.decode("ascii", errors="replace")

            entries.append((uuid_str, path_str))
        except Exception:
            offset += 1

    return entries


def _parse_events_protobuf(data: bytes) -> list:
    """解析 GoodNotes 事件索引。

    事件索引使用更复杂的 protobuf 结构，包含时间戳和事件类型。
    采用启发式方法提取 UUID 和时间相关字段。

    Args:
        data: 事件 protobuf 二进制数据

    Returns:
        [(timestamp_hint, event_type, uuid), ...] 列表
    """
    events = []
    seen_uuids = set()

    # 扫描所有 UUID 格式的字符串
    offset = 0
    while offset < len(data) - 8:
        # 查找 UUID 模式：8-4-4-4-12 的十六进制字符
        uuid_start = None
        for i in range(offset, min(offset + 200, len(data) - 36)):
            if _looks_like_uuid_at(data, i):
                uuid_start = i
                break

        if uuid_start is None:
            break

        uuid_str = data[uuid_start:uuid_start + 36].decode("ascii", errors="replace")
        if uuid_str not in seen_uuids:
            seen_uuids.add(uuid_str)
            events.append((0, "unknown", uuid_str))

        offset = uuid_start + 36

    return events


def _looks_like_uuid_at(data: bytes, pos: int) -> bool:
    """检查给定位置是否像一个 UUID 字符串。

    UUID 格式：xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (36字符)

    Args:
        data: 二进制数据
        pos: 位置索引

    Returns:
        True 如果该位置有有效的 UUID 字符串
    """
    if pos + 36 > len(data):
        return False

    # 检查分隔符位置
    if data[pos + 8] != 0x2D or data[pos + 13] != 0x2D:
        return False
    if data[pos + 18] != 0x2D or data[pos + 23] != 0x2D:
        return False

    # 检查所有字符是否为十六进制或分隔符
    for i in range(36):
        if i in (8, 13, 18, 23):
            if data[pos + i] != 0x2D:
                return False
        else:
            byte_val = data[pos + i]
            if not ((0x30 <= byte_val <= 0x39) or (0x41 <= byte_val <= 0x46) or
                    (0x61 <= byte_val <= 0x66)):
                return False

    return True


# ============================================================
#  元数据格式化输出
# ============================================================

def format_metadata_summary(meta: GoodNotesMetadata) -> str:
    """生成元数据的可读摘要字符串。

    Args:
        meta: GoodNotesMetadata 对象

    Returns:
        多行摘要文本
    """
    lines = []
    lines.append("=" * 50)
    lines.append("  GoodNotes 笔记元数据摘要")
    lines.append("=" * 50)
    lines.append(f"  数据模式版本 : {meta.schema_version}")
    lines.append(f"  笔记页面数量 : {meta.note_count}")
    lines.append(f"  附件文件数量 : {meta.attachment_count}")
    lines.append(f"  事件记录数量 : {meta.event_count}")
    lines.append(f"  附件总大小   : {meta.total_size / 1024 / 1024:.1f} MB")

    if meta.modified_date:
        lines.append(f"  最后修改时间 : {meta.modified_date.strftime('%Y-%m-%d %H:%M:%S')}")

    if meta.notes:
        lines.append("")
        lines.append("  笔记页面列表:")
        for uuid, path in meta.notes:
            lines.append(f"    [{uuid[:8]}...] → {path}")

    if meta.attachments:
        lines.append("")
        lines.append("  附件文件列表:")
        for uuid, path in meta.attachments:
            lines.append(f"    [{uuid[:8]}...] → {path}")

    lines.append("=" * 50)
    return "\n".join(lines)


def get_note_page_count(zipfile_obj) -> int:
    """快速获取笔记页面数量（不完整解析）。"""
    try:
        if "index.notes.pb" in zipfile_obj.namelist():
            with zipfile_obj.open("index.notes.pb") as f:
                data = f.read()
            return len(_parse_string_map_protobuf(data))
    except Exception:
        pass
    return 0


def get_attachment_uuids(zipfile_obj) -> list:
    """获取所有附件的 UUID 列表。"""
    uuids = []
    try:
        if "index.attachments.pb" in zipfile_obj.namelist():
            with zipfile_obj.open("index.attachments.pb") as f:
                data = f.read()
            entries = _parse_string_map_protobuf(data)
            uuids = [uuid for uuid, _ in entries]
    except Exception:
        pass
    return uuids

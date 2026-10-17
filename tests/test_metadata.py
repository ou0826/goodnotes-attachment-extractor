"""
GoodNotes 元数据解析模块 - 单元测试
"""

import sys
import io
import zipfile
import struct
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from goodnotes_extractor.metadata import (
    _read_varint,
    _read_length_delimited,
    _decode_tag,
    _looks_like_uuid_at,
    _parse_string_map_protobuf,
    parse_goodnotes_index,
    get_note_page_count,
    get_attachment_uuids,
    GoodNotesMetadata,
    ProtobufWireType,
)


class TestVarintDecoding(unittest.TestCase):
    """Protobuf varint 解码测试。"""

    def test_single_byte_varint(self):
        """单字节 varint (值 < 128)。"""
        value, consumed = _read_varint(b"\x01", 0)
        self.assertEqual(value, 1)
        self.assertEqual(consumed, 1)

    def test_two_byte_varint(self):
        """两字节 varint (值 128-16383)。"""
        value, consumed = _read_varint(b"\x96\x01", 0)
        self.assertEqual(value, 150)
        self.assertEqual(consumed, 2)

    def test_large_varint(self):
        """多字节 varint。"""
        value, consumed = _read_varint(b"\xff\xff\xff\xff\x0f", 0)
        self.assertEqual(value, 0xFFFFFFFF)
        self.assertEqual(consumed, 5)

    def test_zero_varint(self):
        """零值 varint。"""
        value, consumed = _read_varint(b"\x00", 0)
        self.assertEqual(value, 0)
        self.assertEqual(consumed, 1)

    def test_varint_at_offset(self):
        """从非零偏移读取。"""
        data = b"\x01\x02\xac\x02"
        value, consumed = _read_varint(data, 2)
        self.assertEqual(value, 300)
        self.assertEqual(consumed, 2)


class TestTagDecoding(unittest.TestCase):
    """Protobuf 标签解码测试。"""

    def test_decode_tag(self):
        """标签解码: field_number = tag >> 3, wire_type = tag & 7。"""
        # tag = (field_number << 3) | wire_type
        # field_number=1, wire_type=2 (LENGTH_DELIMITED) → tag=10
        fn, wt, consumed = _decode_tag(b"\x0a", 0)
        self.assertEqual(fn, 1)
        self.assertEqual(wt, ProtobufWireType.LENGTH_DELIMITED)
        self.assertEqual(consumed, 1)

    def test_decode_varint_tag(self):
        """varint wire type 标签。"""
        fn, wt, consumed = _decode_tag(b"\x08", 0)
        self.assertEqual(fn, 1)
        self.assertEqual(wt, ProtobufWireType.VARINT)


class TestLengthDelimited(unittest.TestCase):
    """Protobuf 长度分隔字段解码测试。"""

    def test_read_string(self):
        """读取字符串字段。"""
        data = b"\x05Hello"
        content, consumed = _read_length_delimited(data, 0)
        self.assertEqual(content, b"Hello")
        self.assertEqual(consumed, 6)

    def test_read_empty(self):
        """读取空字段。"""
        data = b"\x00"
        content, consumed = _read_length_delimited(data, 0)
        self.assertEqual(content, b"")
        self.assertEqual(consumed, 1)

    def test_truncated(self):
        """截断的数据不会崩溃。"""
        data = b"\x10ab"
        content, consumed = _read_length_delimited(data, 0)
        self.assertEqual(len(content), 2)


class TestUUIDDetection(unittest.TestCase):
    """UUID 检测测试。"""

    def test_valid_uuid(self):
        """有效 UUID 格式检测。"""
        data = b"693CAB31-4718-4A74-801B-2877708215A4"
        self.assertTrue(_looks_like_uuid_at(data, 0))

    def test_invalid_uuid(self):
        """无效格式检测。"""
        data = b"not-a-valid-uuid-string-at-all"
        self.assertFalse(_looks_like_uuid_at(data, 0))

    def test_short_data(self):
        """数据不足 36 字节。"""
        data = b"short"
        self.assertFalse(_looks_like_uuid_at(data, 0))

    def test_boundary(self):
        """起始位置靠后的有效 UUID。"""
        prefix = b"prefix_"
        data = prefix + b"693CAB31-4718-4A74-801B-2877708215A4"
        self.assertTrue(_looks_like_uuid_at(data, len(prefix)))


class TestStringMapParsing(unittest.TestCase):
    """GoodNotes 字符串映射解析测试。"""

    def test_simple_map(self):
        """简单的 UUID → 路径 映射。"""
        # 构造: tag(1)=0x0a, len=36, UUID; tag(2)=0x12, len=30, path
        uuid = b"693CAB31-4718-4A74-801B-2877708215A4"
        path = b"attachments/693CAB31-4718-4A74-801B-2877708215A4"

        data = b""
        data += b"\x0a"  # field 1, wire type 2
        data += bytes([len(uuid)])
        data += uuid
        data += b"\x12"  # field 2, wire type 2
        data += bytes([len(path)])
        data += path

        entries = _parse_string_map_protobuf(data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], uuid.decode("ascii"))
        self.assertEqual(entries[0][1], path.decode("ascii"))

    def test_multiple_entries(self):
        """多个映射条目的解析。"""
        data = b""
        for i in range(3):
            uuid = f"0000000{i}-0000-4000-8000-00000000000{i}".encode("ascii")
            path = f"attachments/file_{i}.m4a".encode("ascii")
            data += b"\x0a"
            data += bytes([len(uuid)])
            data += uuid
            data += b"\x12"
            data += bytes([len(path)])
            data += path

        entries = _parse_string_map_protobuf(data)
        self.assertEqual(len(entries), 3)

    def test_empty_data(self):
        """空数据应返回空列表。"""
        entries = _parse_string_map_protobuf(b"")
        self.assertEqual(len(entries), 0)


class TestGoodNotesMetadata(unittest.TestCase):
    """GoodNotesMetadata 类测试。"""

    def test_default_values(self):
        """默认值初始化。"""
        meta = GoodNotesMetadata()
        self.assertEqual(meta.note_count, 0)
        self.assertEqual(meta.attachment_count, 0)
        self.assertEqual(meta.event_count, 0)
        self.assertEqual(meta.schema_version, 0)

    def test_set_attributes(self):
        """属性设置。"""
        meta = GoodNotesMetadata()
        meta.note_count = 5
        meta.attachment_count = 10
        meta.total_size = 1024000
        self.assertEqual(meta.note_count, 5)
        self.assertEqual(meta.attachment_count, 10)
        self.assertEqual(meta.total_size, 1024000)


class TestIndexParsingWithZIP(unittest.TestCase):
    """使用内存 ZIP 测试索引解析。"""

    def _create_test_zip(self) -> bytes:
        """创建包含最小索引文件的 ZIP。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # schema.pb
            zf.writestr("schema.pb", struct.pack("<H", 1))
            # index.notes.pb - 一个笔记页
            uuid = b"1713D8DF-FD54-449D-BCC1-9786654869FF"
            path = b"notes/1713D8DF-FD54-449D-BCC1-9786654869FF"
            notes_data = b"\x0a" + bytes([len(uuid)]) + uuid
            notes_data += b"\x12" + bytes([len(path)]) + path
            zf.writestr("index.notes.pb", notes_data)
            # index.attachments.pb - 一个附件
            auuid = b"400172C4-65EF-4F46-9C5A-73E3FAD61F1A"
            apath = b"attachments/400172C4-65EF-4F46-9C5A-73E3FAD61F1A"
            attach_data = b"\x0a" + bytes([len(auuid)]) + auuid
            attach_data += b"\x12" + bytes([len(apath)]) + apath
            zf.writestr("index.attachments.pb", attach_data)
            # 添加一个实际附件
            zf.writestr("attachments/test.bin", b"\x00" * 100)
            zf.writestr("index.events.pb", b"\x00" * 10)
            zf.writestr("index.search.pb", b"\x00" * 5)
        return buf.getvalue()

    def test_parse_index(self):
        """测试从 ZIP 解析索引。"""
        zip_data = self._create_test_zip()
        buf = io.BytesIO(zip_data)
        with zipfile.ZipFile(buf, "r") as zf:
            meta = parse_goodnotes_index(zf)
            self.assertEqual(meta.note_count, 1)
            self.assertEqual(meta.attachment_count, 1)
            self.assertEqual(meta.schema_version, 1)
            self.assertGreater(meta.total_size, 0)

    def test_page_count(self):
        """测试快速获取页数。"""
        zip_data = self._create_test_zip()
        buf = io.BytesIO(zip_data)
        with zipfile.ZipFile(buf, "r") as zf:
            count = get_note_page_count(zf)
            self.assertEqual(count, 1)

    def test_attachment_uuids(self):
        """测试获取附件 UUID 列表。"""
        zip_data = self._create_test_zip()
        buf = io.BytesIO(zip_data)
        with zipfile.ZipFile(buf, "r") as zf:
            uuids = get_attachment_uuids(zf)
            self.assertEqual(len(uuids), 1)
            self.assertIn("400172C4", uuids[0])


if __name__ == "__main__":
    unittest.main()

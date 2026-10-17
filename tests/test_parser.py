"""
二进制格式解析引擎 - 单元测试
覆盖 MP4/M4A 原子树解析、JPEG/PNG 尺寸解析、PDF 检测
"""

import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from goodnotes_extractor.parser import (
    parse_mp4_audio_metadata,
    parse_mp4_atom_tree,
    parse_jpeg_dimensions,
    parse_png_dimensions,
    parse_png_color_info,
    parse_png_chunks,
    png_color_type_name,
    is_pdf_document,
    parse_pdf_version,
    parse_pdf_page_count,
    verify_mp4_integrity,
    estimate_audio_duration_from_size,
    parse_jpeg_exif_orientation,
    parse_jpeg_quality_estimate,
    read_mp4_sample_data,
    PNG_COLOR_GRAYSCALE,
    PNG_COLOR_RGB,
    PNG_COLOR_RGBA,
    PNG_SIGNATURE,
)


class TestM4AMetadataParsing(unittest.TestCase):
    """M4A/MP4 音频元数据解析测试。"""

    def _build_minimal_m4a(self, duration=100, timescale=1000,
                           sample_rate=44100, channels=2):
        """构造最小可解析的 M4A 文件用于测试。"""
        # mvhd atom
        mvhd_data = struct.pack(">I", 0)             # version + flags
        mvhd_data += struct.pack(">I", 0)             # creation_time
        mvhd_data += struct.pack(">I", 0)             # modification_time
        mvhd_data += struct.pack(">I", timescale)      # timescale
        mvhd_data += struct.pack(">I", duration)       # duration
        mvhd_data += b"\x00" * 80                      # padding
        mvhd_atom = struct.pack(">I", len(mvhd_data) + 8) + b"mvhd" + mvhd_data

        # mp4a atom inside stsd
        sr_fixed = sample_rate << 16
        mp4a_data = b"\x00" * 6                        # reserved
        mp4a_data += struct.pack(">H", 1)              # data_reference_index
        mp4a_data += struct.pack(">H", 0)              # version
        mp4a_data += struct.pack(">H", 0)              # revision
        mp4a_data += struct.pack(">I", 0)              # vendor
        mp4a_data += struct.pack(">H", channels)        # channels
        mp4a_data += struct.pack(">H", 16)              # sample_size
        mp4a_data += struct.pack(">H", 0)              # compression_id
        mp4a_data += struct.pack(">H", 0)              # packet_size
        mp4a_data += struct.pack(">I", sr_fixed)        # sample_rate
        mp4a_atom = struct.pack(">I", len(mp4a_data) + 8) + b"mp4a" + mp4a_data

        stsd_data = b"\x00\x00\x00\x00" + struct.pack(">I", 1) + mp4a_atom
        stsd_atom = struct.pack(">I", len(stsd_data) + 8) + b"stsd" + stsd_data
        stbl_atom = struct.pack(">I", len(stsd_atom) + 8) + b"stbl" + stsd_atom
        minf_atom = struct.pack(">I", len(stbl_atom) + 8) + b"minf" + stbl_atom
        mdia_atom = struct.pack(">I", len(minf_atom) + 8) + b"mdia" + minf_atom
        trak_atom = struct.pack(">I", len(mdia_atom) + 8) + b"trak" + mdia_atom

        moov_data = mvhd_atom + trak_atom
        moov_atom = struct.pack(">I", len(moov_data) + 8) + b"moov" + moov_data

        # ftyp + moov
        ftyp_data = b"mp42" + b"\x00\x00\x00\x00" + b"mp42" + b"isom"
        ftyp_atom = struct.pack(">I", len(ftyp_data) + 8) + b"ftyp" + ftyp_data

        return ftyp_atom + moov_atom + b"\x00" * 100  # 填充

    def test_parse_basic_metadata(self):
        """测试基本元数据解析：时长、采样率、声道数。"""
        data = self._build_minimal_m4a(duration=500, timescale=1000,
                                       sample_rate=44100, channels=2)
        result = parse_mp4_audio_metadata(data)
        self.assertAlmostEqual(result["duration"], 0.5, places=3)
        self.assertEqual(result["sample_rate"], 44100)
        self.assertEqual(result["channels"], 2)

    def test_parse_different_sample_rates(self):
        """测试不同采样率的解析。"""
        for sr in [8000, 16000, 22050, 44100, 48000]:
            with self.subTest(sample_rate=sr):
                data = self._build_minimal_m4a(sample_rate=sr, channels=1)
                result = parse_mp4_audio_metadata(data)
                self.assertEqual(result["sample_rate"], sr,
                                 f"采样率 {sr} 解析失败")

    def test_parse_mono_and_stereo(self):
        """测试单声道和双声道。"""
        for ch in [1, 2]:
            with self.subTest(channels=ch):
                data = self._build_minimal_m4a(channels=ch)
                result = parse_mp4_audio_metadata(data)
                self.assertEqual(result["channels"], ch)

    def test_empty_data_handling(self):
        """测试空数据不会崩溃。"""
        result = parse_mp4_audio_metadata(b"")
        self.assertEqual(result["duration"], 0)
        self.assertEqual(result["sample_rate"], 0)
        self.assertEqual(result["channels"], 0)

    def test_corrupted_data_handling(self):
        """测试损坏数据不会崩溃。"""
        data = b"\x00" * 1000
        result = parse_mp4_audio_metadata(data)
        self.assertIsInstance(result, dict)


class TestJPEGParsing(unittest.TestCase):
    """JPEG 图像解析测试。"""

    def _build_minimal_jpeg(self, width=640, height=480):
        """构造可解析的 JPEG 数据。"""
        data = b"\xff\xd8\xff\xe0"  # SOI + APP0
        data += struct.pack(">H", 16)  # APP0 段长度
        data += b"JFIF\x00"            # JFIF 标识
        data += b"\x01\x01"            # 版本
        data += b"\x00"                # 单位
        data += struct.pack(">H", 72)  # X密度
        data += struct.pack(">H", 72)  # Y密度
        data += b"\x00\x00"            # 缩略图

        # SOF0 段
        data += b"\xff\xc0"            # SOF0 标记
        data += struct.pack(">H", 8 + 3 * 3)  # 段长度
        data += b"\x08"                # 精度
        data += struct.pack(">H", height)
        data += struct.pack(">H", width)
        data += b"\x03"                # 分量数
        data += b"\x01\x11\x00"        # Y分量
        data += b"\x02\x11\x01"        # Cb分量
        data += b"\x03\x11\x01"        # Cr分量
        data += b"\xff\xd9"            # EOI
        return data

    def test_parse_dimensions(self):
        """测试 JPEG 尺寸解析。"""
        data = self._build_minimal_jpeg(800, 600)
        w, h = parse_jpeg_dimensions(data)
        self.assertEqual(w, 800)
        self.assertEqual(h, 600)

    def test_parse_small_image(self):
        """测试小尺寸 JPEG。"""
        data = self._build_minimal_jpeg(16, 16)
        w, h = parse_jpeg_dimensions(data)
        self.assertEqual(w, 16)
        self.assertEqual(h, 16)

    def test_invalid_data(self):
        """测试无效数据不会崩溃。"""
        w, h = parse_jpeg_dimensions(b"\x00" * 100)
        self.assertEqual(w, 0)
        self.assertEqual(h, 0)

    def test_truncated_data(self):
        """测试截断数据不会崩溃。"""
        data = b"\xff\xd8\xff\xe0\x00"
        w, h = parse_jpeg_dimensions(data)
        self.assertEqual(w, 0)


class TestPNGParsing(unittest.TestCase):
    """PNG 图像解析测试。"""

    def _build_minimal_png(self, width=100, height=100):
        """构造可解析的 PNG 数据（含 IHDR 块）。"""
        data = PNG_SIGNATURE
        # IHDR chunk
        ihdr_data = struct.pack(">I", width)
        ihdr_data += struct.pack(">I", height)
        ihdr_data += b"\x08"    # bit depth 8
        ihdr_data += b"\x02"    # color type RGB
        ihdr_data += b"\x00"    # compression
        ihdr_data += b"\x00"    # filter
        ihdr_data += b"\x00"    # interlace
        # IHDR chunk length + type + data + CRC
        chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data
        chunk += struct.pack(">I", 0)  # dummy CRC
        return data + chunk

    def test_parse_dimensions(self):
        """测试 PNG 尺寸解析。"""
        data = self._build_minimal_png(1920, 1080)
        w, h = parse_png_dimensions(data)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

    def test_color_info(self):
        """测试 PNG 颜色信息提取。"""
        data = self._build_minimal_png(100, 100)
        info = parse_png_color_info(data)
        self.assertEqual(info["bit_depth"], 8)
        self.assertEqual(info["color_type"], PNG_COLOR_RGB)

    def test_color_type_names(self):
        """测试颜色类型名称映射。"""
        self.assertEqual(png_color_type_name(PNG_COLOR_GRAYSCALE), "灰度")
        self.assertEqual(png_color_type_name(PNG_COLOR_RGB), "RGB")
        self.assertEqual(png_color_type_name(PNG_COLOR_RGBA), "RGBA")

    def test_chunk_listing(self):
        """测试块列表提取。"""
        data = self._build_minimal_png(100, 100)
        chunks = parse_png_chunks(data)
        self.assertTrue(len(chunks) >= 1)
        self.assertEqual(chunks[0][0], "IHDR")

    def test_invalid_signature(self):
        """测试非 PNG 数据返回 (0,0)。"""
        w, h = parse_png_dimensions(b"NOT A PNG FILE\x00")
        self.assertEqual(w, 0)
        self.assertEqual(h, 0)

    def test_incomplete_ihdr(self):
        """测试不完整的 IHDR 数据。"""
        data = PNG_SIGNATURE + b"\x00\x00\x00\x0dIHDR\x00\x00"
        w, h = parse_png_dimensions(data)
        self.assertEqual(w, 0)


class TestPDFDetection(unittest.TestCase):
    """PDF 文档检测测试。"""

    def test_valid_pdf(self):
        """测试有效 PDF 检测。"""
        self.assertTrue(is_pdf_document(b"%PDF-1.7\n%..."))

    def test_invalid_pdf(self):
        """测试无效数据。"""
        self.assertFalse(is_pdf_document(b"Hello World"))
        self.assertFalse(is_pdf_document(b""))

    def test_version_extraction(self):
        """测试版本号提取。"""
        self.assertEqual(parse_pdf_version(b"%PDF-1.4\n..."), "1.4")
        self.assertEqual(parse_pdf_version(b"%PDF-2.0\n..."), "2.0")

    def test_page_count_estimation(self):
        """测试页数估算。"""
        data = b"%PDF-1.7\n/Type /Page/Type/Page/Type /Page"
        count = parse_pdf_page_count(data)
        self.assertGreaterEqual(count, 3)


class TestAudioEstimation(unittest.TestCase):
    """音频时长估算测试。"""

    def test_estimate_formula(self):
        """验证时长估算公式的合理性。"""
        dur = estimate_audio_duration_from_size(
            1024 * 1024, sample_rate=44100, channels=2
        )
        self.assertGreater(dur, 0)
        self.assertLess(dur, 3600)

    def test_mono_shorter_than_stereo(self):
        """单声道文件应比同大小双声道文件时长更长。"""
        dur_mono = estimate_audio_duration_from_size(1024 * 1024, channels=1)
        dur_stereo = estimate_audio_duration_from_size(1024 * 1024, channels=2)
        self.assertGreater(dur_mono, dur_stereo)


class TestMP4Integrity(unittest.TestCase):
    """MP4 完整性校验测试。"""

    def test_invalid_small_file(self):
        """太小的文件不能通过校验。"""
        ok, msg = verify_mp4_integrity(b"small")
        self.assertFalse(ok)

    def test_missing_atoms(self):
        """缺少关键原子的文件。"""
        data = struct.pack(">I", 24)
        data += b"ftypmp42\x00\x00\x00\x00mp42isom"
        ok, msg = verify_mp4_integrity(data)
        self.assertFalse(ok)


class TestAtomTree(unittest.TestCase):
    """MP4 原子树解析测试。"""

    def test_atom_tree_parsing(self):
        """测试顶层原子树解析。"""
        # ftyp atom
        ftyp = struct.pack(">I", 20) + b"ftyp" + b"mp42\x00\x00\x00\x00mp42"
        # moov atom (empty)
        moov = struct.pack(">I", 8) + b"moov"
        data = ftyp + moov

        atoms = parse_mp4_atom_tree(data)
        self.assertEqual(len(atoms), 2)
        self.assertEqual(atoms[0]["type"], "ftyp")
        self.assertEqual(atoms[1]["type"], "moov")

    def test_empty_data(self):
        """空数据应返回空列表。"""
        atoms = parse_mp4_atom_tree(b"")
        self.assertEqual(len(atoms), 0)


class TestJPEGExif(unittest.TestCase):
    """JPEG EXIF 元数据解析测试。"""

    def test_no_exif(self):
        """无 EXIF 数据返回默认方向。"""
        data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        orientation = parse_jpeg_exif_orientation(data)
        self.assertEqual(orientation, 1)

    def test_quality_estimate(self):
        """质量估计测试。"""
        # 构造带量化表的简单数据
        data = b"\xff\xdb" + struct.pack(">H", 67) + b"\x00" + b"\x08" * 64
        data += b"\xff\xd9"
        q = parse_jpeg_quality_estimate(data)
        self.assertGreater(q, 0)


if __name__ == "__main__":
    unittest.main()

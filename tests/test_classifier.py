"""
文件类型识别与分类模块 - 单元测试
"""

import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from goodnotes_extractor.classifier import (
    classify_file,
    classify_file_detailed,
    classify_files_batch,
    get_category_statistics,
    suggest_extension,
    FileCategory,
)


def _make_ftyp_data():
    """构造 MP4 ftyp 头数据。"""
    return (struct.pack(">I", 24) + b"ftyp" +
            b"mp42\x00\x00\x00\x00" + b"mp42" + b"isom")


class TestFileClassifier(unittest.TestCase):
    """文件分类器测试。"""

    def test_classify_m4a_audio(self):
        """带有 mp4a 的 MP4 容器应被识别为音频。"""
        data = _make_ftyp_data() + b"moo" + b"mp4a" * 100
        result = classify_file(data)
        self.assertEqual(result, FileCategory.AUDIO)

    def test_classify_video(self):
        """带有 avc1 的 MP4 容器应被识别为视频。"""
        data = _make_ftyp_data() + b"moov" + b"avc1" * 100
        result = classify_file(data)
        self.assertEqual(result, FileCategory.VIDEO)

    def test_classify_video_h265(self):
        """带有 hvc1 的 HEVC 视频。"""
        data = _make_ftyp_data() + b"moov" + b"hvc1" * 100
        result = classify_file(data)
        self.assertEqual(result, FileCategory.VIDEO)

    def test_classify_jpeg(self):
        """JPEG 文件识别。"""
        # 构造一个简单的 JPEG 头
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = classify_file(data)
        self.assertEqual(result, FileCategory.IMAGE)

    def test_classify_png(self):
        """PNG 文件识别。"""
        data = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = classify_file(data)
        self.assertEqual(result, FileCategory.IMAGE)

    def test_classify_pdf(self):
        """PDF 文件识别。"""
        data = b"%PDF-1.7\n% some pdf content"
        result = classify_file(data)
        self.assertEqual(result, FileCategory.PDF)

    def test_classify_unknown(self):
        """无法识别的数据。"""
        data = b"Hello, this is not a recognized format!" * 10
        result = classify_file(data)
        self.assertEqual(result, FileCategory.UNKNOWN)

    def test_small_data(self):
        """太小的数据无法识别。"""
        result = classify_file(b"tiny")
        self.assertEqual(result, FileCategory.UNKNOWN)

    def test_empty_data(self):
        """空数据无法识别。"""
        result = classify_file(b"")
        self.assertEqual(result, FileCategory.UNKNOWN)


class TestDetailedClassification(unittest.TestCase):
    """详细分类测试。"""

    def test_audio_detail(self):
        """音频详细分类应包含 subtype 和 mime。"""
        data = _make_ftyp_data() + b"moov" + b"mp4a" * 200
        detail = classify_file_detailed(data)
        self.assertEqual(detail["category"], FileCategory.AUDIO)
        self.assertGreater(detail["confidence"], 0.9)
        self.assertEqual(detail["mime"], "audio/mp4")

    def test_png_detail(self):
        """PNG 详细分类。"""
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        detail = classify_file_detailed(data)
        self.assertEqual(detail["subtype"], "PNG")
        self.assertEqual(detail["mime"], "image/png")

    def test_jpeg_detail(self):
        """JPEG 详细分类。"""
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        detail = classify_file_detailed(data)
        self.assertEqual(detail["subtype"], "JPEG")
        self.assertEqual(detail["mime"], "image/jpeg")

    def test_video_codec_detection(self):
        """视频编解码器检测。"""
        data = _make_ftyp_data() + b"moov" + b"avc1" * 100
        detail = classify_file_detailed(data)
        self.assertEqual(detail["category"], FileCategory.VIDEO)
        self.assertEqual(detail["subtype"], "H.264")


class TestExtensionSuggestion(unittest.TestCase):
    """扩展名建议测试。"""

    def test_audio_extension(self):
        self.assertEqual(suggest_extension(FileCategory.AUDIO), ".m4a")

    def test_pdf_extension(self):
        self.assertEqual(suggest_extension(FileCategory.PDF), ".pdf")

    def test_jpeg_extension(self):
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        self.assertEqual(suggest_extension(FileCategory.IMAGE, data), ".jpg")

    def test_png_extension(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        self.assertEqual(suggest_extension(FileCategory.IMAGE, data), ".png")


class TestBatchClassification(unittest.TestCase):
    """批量分类测试。"""

    def test_batch_classify(self):
        """测试批量分类功能。"""
        file_map = {
            "audio.m4a": _make_ftyp_data() + b"moov" + b"mp4a" * 200,
            "image.jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            "doc.pdf": b"%PDF-1.7\n...",
        }
        results = classify_files_batch(file_map)
        self.assertEqual(len(results), 3)
        self.assertEqual(results["audio.m4a"]["category"], FileCategory.AUDIO)
        self.assertEqual(results["image.jpg"]["category"], FileCategory.IMAGE)
        self.assertEqual(results["doc.pdf"]["category"], FileCategory.PDF)

    def test_statistics(self):
        """测试分类统计。"""
        file_map = {
            "a.m4a": _make_ftyp_data() + b"moov" + b"mp4a" * 200,
            "b.m4a": _make_ftyp_data() + b"moov" + b"mp4a" * 200,
            "c.jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 100,
        }
        results = classify_files_batch(file_map)
        stats = get_category_statistics(results)
        self.assertEqual(stats[FileCategory.AUDIO]["count"], 2)
        self.assertEqual(stats[FileCategory.IMAGE]["count"], 1)


class TestFileCategoryLabels(unittest.TestCase):
    """文件类别标签测试。"""

    def test_known_labels(self):
        self.assertEqual(FileCategory.label(FileCategory.AUDIO), "音频文件")
        self.assertEqual(FileCategory.label(FileCategory.IMAGE), "图片文件")
        self.assertEqual(FileCategory.label(FileCategory.PDF), "PDF文档")

    def test_unknown_label(self):
        self.assertEqual(FileCategory.label("nonexistent"), "未知格式")


if __name__ == "__main__":
    unittest.main()

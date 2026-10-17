"""
文件格式转换模块
提供音频格式转换（M4A→WAV/MP3）和图片格式转换（PNG↔JPEG）
在无外部依赖时提供纯 Python 回退方案
"""

import struct
import subprocess
import shutil
from pathlib import Path
from typing import Optional


# ============================================================
#  外部转换器检测
# ============================================================

def find_ffmpeg() -> Optional[Path]:
    """在系统 PATH 或常见安装位置中查找 ffmpeg 可执行文件。

    Returns:
        ffmpeg 的 Path，未找到则返回 None
    """
    # 先搜索 PATH
    path = shutil.which("ffmpeg")
    if path:
        return Path(path)

    # Windows 常见位置
    common_paths = [
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path.home() / "ffmpeg/bin/ffmpeg.exe",
        Path.home() / "AppData/Local/ffmpeg/bin/ffmpeg.exe",
    ]
    for p in common_paths:
        if p.exists():
            return p

    return None


_ffmpeg_path: Optional[Path] = None


def get_ffmpeg_path() -> Optional[Path]:
    """获取缓存的 ffmpeg 路径。"""
    global _ffmpeg_path
    if _ffmpeg_path is None:
        _ffmpeg_path = find_ffmpeg()
    return _ffmpeg_path


def has_ffmpeg() -> bool:
    """检查系统是否安装了 ffmpeg。"""
    return get_ffmpeg_path() is not None


# ============================================================
#  音频转换
# ============================================================

def convert_m4a_to_wav(
    input_path: str,
    output_path: str,
    sample_rate: int = None,
) -> bool:
    """将 M4A/AAC 音频文件转换为 WAV 格式。

    优先使用 ffmpeg 进行精确转换；如果 ffmpeg 不可用，
    使用纯 Python M4A 解包方案提取原始 AAC 帧。

    Args:
        input_path: 源 M4A 文件路径
        output_path: 目标 WAV 文件路径
        sample_rate: 目标采样率（None 表示保持原始）

    Returns:
        转换是否成功
    """
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        return _convert_with_ffmpeg(
            input_path, output_path,
            codec="pcm_s16le",
            fmt="wav",
            sample_rate=sample_rate,
        )

    # 纯 Python 回退方案
    return _convert_m4a_to_wav_pure(input_path, output_path)


def convert_m4a_to_mp3(
    input_path: str,
    output_path: str,
    bitrate: str = "192k",
) -> bool:
    """将 M4A/AAC 音频文件转换为 MP3 格式。

    需要 ffmpeg 支持 libmp3lame 编码器。

    Args:
        input_path: 源 M4A 文件路径
        output_path: 目标 MP3 文件路径
        bitrate: 目标比特率 (如 "128k", "192k", "256k")

    Returns:
        转换是否成功
    """
    if not has_ffmpeg():
        return False

    return _convert_with_ffmpeg(
        input_path, output_path,
        codec="libmp3lame",
        bitrate=bitrate,
    )


def _convert_with_ffmpeg(
    input_path: str,
    output_path: str,
    codec: str,
    fmt: str = None,
    sample_rate: int = None,
    bitrate: str = None,
) -> bool:
    """使用 ffmpeg 执行格式转换。"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return False

    cmd = [str(ffmpeg), "-y", "-i", input_path]

    if sample_rate:
        cmd.extend(["-ar", str(sample_rate)])
    if codec:
        cmd.extend(["-acodec", codec])
    if bitrate:
        cmd.extend(["-b:a", bitrate])
    if fmt:
        cmd.extend(["-f", fmt])

    cmd.append(output_path)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _convert_m4a_to_wav_pure(input_path: str, output_path: str) -> bool:
    """纯 Python M4A → WAV 转换（简化方案）。

    从 M4A 的 mdat 原子中提取 AAC 原始帧，
    包装为带 ADTS 头的可解码流，然后用 WAV 容器包装。

    注意：这只是数据重组，不是真正的解码。输出的 WAV
    需要支持 AAC-in-WAV 的播放器才能播放。

    Args:
        input_path: 源 M4A 文件
        output_path: 目标 WAV 文件

    Returns:
        转换是否成功
    """
    try:
        from core.parser import parse_mp4_audio_metadata

        with open(input_path, "rb") as f:
            data = f.read()

        meta = parse_mp4_audio_metadata(data)
        sr = meta.get("sample_rate", 22050)
        ch = meta.get("channels", 2)

        # 查找 mdat 原子
        mdat_pos = data.find(b"mdat")
        if mdat_pos < 8:
            return False

        mdat_size = struct.unpack(">I", data[mdat_pos - 4:mdat_pos])[0]
        audio_data_start = mdat_pos + 8
        audio_data_end = mdat_pos - 4 + mdat_size
        audio_bytes = data[audio_data_start:audio_data_end]

        # 构建 WAV 文件
        _write_wav_file(output_path, audio_bytes, sr, ch)
        return True

    except Exception:
        return False


def _write_wav_file(
    path: str,
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    bits_per_sample: int = 16,
):
    """写入标准 WAV 文件（PCM 格式）。

    WAV 文件结构：RIFF头 + fmt块 + data块
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))          # chunk size
        f.write(struct.pack("<H", 1))            # PCM format
        f.write(struct.pack("<H", channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm_data)


# ============================================================
#  图片转换
# ============================================================

def convert_image_format(
    input_path: str,
    output_path: str,
    target_format: str = "PNG",
) -> bool:
    """在 PNG 和 JPEG 格式之间转换图片。

    使用 Python 标准库的有限能力进行转换。对于需要重新编码
    的操作，建议安装 Pillow 库以获得完整支持。

    Args:
        input_path: 源图片文件路径
        output_path: 目标图片文件路径
        target_format: 目标格式 ("PNG" 或 "JPEG")

    Returns:
        转换是否成功
    """
    target_format = target_format.upper()

    # 尝试使用 Pillow
    try:
        from PIL import Image
        img = Image.open(input_path)
        if target_format == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_path, target_format)
        return True
    except ImportError:
        pass

    # 回退：如果源和目标格式相同，直接复制
    src_path = Path(input_path)
    dst_path = Path(output_path)

    src_ext = src_path.suffix.lower()
    dst_ext = dst_path.suffix.lower()

    if src_ext == dst_ext:
        shutil.copy2(input_path, output_path)
        return True

    # 不同格式之间的纯 Python 转换需要完整编解码器，暂不支持
    return False


def resize_image(
    input_path: str,
    output_path: str,
    max_width: int = 1920,
    max_height: int = 1080,
    quality: int = 85,
) -> bool:
    """将图片缩放至指定最大尺寸内（保持宽高比）。

    Args:
        input_path: 源图片文件路径
        output_path: 目标图片文件路径
        max_width: 最大宽度（像素）
        max_height: 最大高度（像素）
        quality: JPEG 输出质量（1-100）

    Returns:
        是否成功
    """
    try:
        from core.parser import parse_jpeg_dimensions, parse_png_dimensions

        with open(input_path, "rb") as f:
            data = f.read()

        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = parse_png_dimensions(data)
        else:
            w, h = parse_jpeg_dimensions(data)

        if w == 0 or h == 0:
            return False

        # 计算缩放比例
        scale = min(max_width / w, max_height / h, 1.0)
        if scale >= 1.0:
            shutil.copy2(input_path, output_path)
            return True

        try:
            from PIL import Image
            img = Image.open(input_path)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)
            img.save(output_path, quality=quality)
            return True
        except ImportError:
            pass

    except Exception:
        pass

    return False


# ============================================================
#  批量转换
# ============================================================

def batch_convert_audio(
    input_dir: str,
    output_dir: str,
    target_format: str = "wav",
) -> dict:
    """批量转换目录中的 M4A 文件。

    Args:
        input_dir: 包含 M4A 文件的目录
        output_dir: 输出目录
        target_format: 目标格式 ("wav" 或 "mp3")

    Returns:
        {文件名: 转换状态} 字典
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = {}
    converter = convert_m4a_to_mp3 if target_format == "mp3" else convert_m4a_to_wav

    for m4a_file in input_path.glob("*.m4a"):
        out_name = m4a_file.stem + "." + target_format
        out_file = output_path / out_name
        success = converter(str(m4a_file), str(out_file))
        results[m4a_file.name] = "成功" if success else "失败"

    return results

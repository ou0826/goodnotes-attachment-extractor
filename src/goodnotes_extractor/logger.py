"""
结构化日志模块
提供分级日志记录、文件轮转、格式化输出等功能
支持同时输出到控制台和文件，适配命令行和 GUI 两种场景
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
#  日志级别定义
# ============================================================

LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ANSI 颜色码（Windows 10+ 支持）
_COLORS = {
    "DEBUG": "\033[36m",       # 青色
    "INFO": "\033[32m",        # 绿色
    "WARNING": "\033[33m",     # 黄色
    "ERROR": "\033[31m",       # 红色
    "CRITICAL": "\033[35m",    # 紫色
    "RESET": "\033[0m",
}

# 无颜色模式（写入文件时使用）
_PLAIN_FORMAT = (
    "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"
)
_COLOR_FORMAT = (
    "%(asctime)s %(color)s[%(levelname)-8s]%(reset)s %(name)s - %(message)s"
)


class ColoredFormatter(logging.Formatter):
    """带 ANSI 颜色的控制台日志格式化器。"""

    def format(self, record):
        if hasattr(record, "color"):
            record.color = _COLORS.get(record.levelname, "")
            record.reset = _COLORS["RESET"]
        else:
            record.color = ""
            record.reset = ""
        return super().format(record)


class LogManager:
    """日志管理器。

    统一管理应用日志的配置和输出目标。
    支持控制台输出、文件输出和 GUI 回调三种后端。

    用法:
        lm = LogManager()
        lm.setup(level="INFO", log_dir="./logs")
        logger = lm.get_logger(__name__)
        logger.info("消息内容")
    """

    def __init__(self):
        self._initialized = False
        self._log_dir: Optional[Path] = None
        self._console_handler: Optional[logging.Handler] = None
        self._file_handler: Optional[logging.Handler] = None
        self._gui_callback = None

        # 根 logger
        self._root_logger = logging.getLogger("goodnotes_extractor")
        self._root_logger.setLevel(logging.DEBUG)

    def setup(
        self,
        level: str = "INFO",
        log_dir: str = None,
        console_output: bool = True,
        file_output: bool = True,
        gui_callback=None,
    ):
        """配置日志系统。

        Args:
            level: 最低记录级别
            log_dir: 日志文件保存目录
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            gui_callback: GUI 消息回调函数
        """
        self._root_logger.handlers.clear()

        log_level = LEVELS.get(level.upper(), logging.INFO)
        self._root_logger.setLevel(log_level)

        # 控制台处理器
        if console_output and sys.stdout is not None:
            self._console_handler = logging.StreamHandler(sys.stdout)
            self._console_handler.setLevel(log_level)
            fmt = ColoredFormatter(
                _COLOR_FORMAT,
                datefmt="%H:%M:%S",
            )
            self._console_handler.setFormatter(fmt)
            self._root_logger.addHandler(self._console_handler)

        # 文件处理器
        if file_output:
            if log_dir:
                self._log_dir = Path(log_dir)
            else:
                self._log_dir = Path.home() / ".goodnotes-extractor" / "logs"
            self._log_dir.mkdir(parents=True, exist_ok=True)

            log_filename = datetime.now().strftime("extract_%Y%m%d_%H%M%S.log")
            log_path = self._log_dir / log_filename

            self._file_handler = logging.FileHandler(
                log_path, encoding="utf-8"
            )
            self._file_handler.setLevel(logging.DEBUG)
            file_fmt = logging.Formatter(
                _PLAIN_FORMAT,
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            self._file_handler.setFormatter(file_fmt)
            self._root_logger.addHandler(self._file_handler)

            # 清理旧日志文件
            self._cleanup_old_logs(keep=10)

        # GUI 回调
        if gui_callback:
            self._gui_callback = gui_callback

        self._initialized = True

    def get_logger(self, name: str) -> logging.Logger:
        """获取或创建子 logger。

        Args:
            name: logger 名称，通常使用 __name__

        Returns:
            logging.Logger 实例
        """
        if not self._initialized:
            self.setup()

        return logging.getLogger(f"goodnotes_extractor.{name}")

    def set_level(self, level: str):
        """动态修改日志级别。"""
        log_level = LEVELS.get(level.upper(), logging.INFO)
        self._root_logger.setLevel(log_level)
        for handler in self._root_logger.handlers:
            handler.setLevel(log_level)

    def get_log_files(self) -> list:
        """获取所有日志文件路径（按时间降序）。"""
        if not self._log_dir or not self._log_dir.exists():
            return []
        return sorted(
            self._log_dir.glob("extract_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _cleanup_old_logs(self, keep: int = 10):
        """删除旧的日志文件，只保留最近 N 个。"""
        log_files = self.get_log_files()
        for old_file in log_files[keep:]:
            try:
                old_file.unlink()
            except OSError:
                pass


# ============================================================
#  全局实例
# ============================================================

_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """获取全局日志管理器。"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
        _log_manager.setup()
    return _log_manager


def get_logger(name: str = "extractor") -> logging.Logger:
    """快捷获取 logger 实例。"""
    return get_log_manager().get_logger(name)


def setup_logging(
    level: str = "INFO",
    log_dir: str = None,
    gui_callback=None,
):
    """一次性配置全局日志。"""
    get_log_manager().setup(
        level=level,
        log_dir=log_dir,
        gui_callback=gui_callback,
    )

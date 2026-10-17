"""
配置管理系统
管理用户偏好、默认设置和应用状态的持久化存储
使用 JSON 格式保存配置，支持多配置文件和环境变量覆盖
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


# ============================================================
#  默认配置
# ============================================================

DEFAULT_CONFIG = {
    "version": "2.0.0",
    "general": {
        "language": "zh_CN",
        "output_base_dir": "",
        "auto_open_output": True,
        "preserve_original_filename": False,
        "max_filename_length": 120,
    },
    "extraction": {
        "audio_enabled": True,
        "image_enabled": True,
        "pdf_enabled": True,
        "skip_duplicates": True,
        "organize_by_type": True,
        "datetime_in_filename": False,
    },
    "conversion": {
        "audio_default_format": "m4a",
        "audio_available_formats": ["m4a", "wav", "mp3"],
        "image_default_format": "original",
        "image_available_formats": ["original", "png", "jpg"],
        "ffmpeg_path": "",
    },
    "batch": {
        "recursive_search": True,
        "max_concurrent": 1,
        "merge_output": False,
    },
    "ui": {
        "theme": "light",
        "font_size": 12,
        "window_width": 960,
        "window_height": 680,
        "show_progress_details": True,
        "confirm_overwrite": True,
    },
    "logging": {
        "level": "INFO",
        "save_to_file": True,
        "log_dir": "",
        "max_log_files": 10,
    },
}


class ConfigManager:
    """应用配置管理器。

    负责配置的加载、保存、查询和更新。采用分层优先级：
      默认值 < 用户配置文件 < 环境变量

    用法:
        cfg = ConfigManager()
        cfg.load()
        audio_enabled = cfg.get("extraction.audio_enabled")
        cfg.set("ui.theme", "dark")
        cfg.save()
    """

    def __init__(self, config_dir: str = None):
        """初始化配置管理器。

        Args:
            config_dir: 配置文件目录，默认为用户目录下的 .goodnotes-extractor
        """
        if config_dir is None:
            config_dir = Path.home() / ".goodnotes-extractor"
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._data: dict = {}
        self._loaded = False

    def load(self) -> dict:
        """加载配置文件。如果文件不存在则创建默认配置。

        Returns:
            完整的配置字典
        """
        self._config_dir.mkdir(parents=True, exist_ok=True)

        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                self._data = self._merge_config(DEFAULT_CONFIG.copy(), user_config)
            except (json.JSONDecodeError, OSError):
                self._data = DEFAULT_CONFIG.copy()
                self.save()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

        self._apply_env_overrides()
        self._loaded = True
        return self._data

    def save(self):
        """保存当前配置到文件。"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key_path: str, default: Any = None) -> Any:
        """通过点分隔的键路径获取配置值。

        Args:
            key_path: 配置键路径，如 "extraction.audio_enabled"
            default: 键不存在时的默认值

        Returns:
            配置值
        """
        if not self._loaded:
            self.load()

        keys = key_path.split(".")
        current = self._data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def set(self, key_path: str, value: Any):
        """设置配置值。

        Args:
            key_path: 配置键路径
            value: 新值
        """
        if not self._loaded:
            self.load()

        keys = key_path.split(".")
        current = self._data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def reset(self, key_path: str = None):
        """重置配置项为默认值。

        Args:
            key_path: 要重置的键路径，None 表示全部重置
        """
        if key_path is None:
            self._data = DEFAULT_CONFIG.copy()
        else:
            default_val = self._get_default(key_path)
            if default_val is not None:
                self.set(key_path, default_val)

    def export(self) -> str:
        """导出配置为 JSON 字符串。"""
        return json.dumps(self._data, ensure_ascii=False, indent=2)

    def import_from_string(self, json_str: str) -> bool:
        """从 JSON 字符串导入配置。

        Args:
            json_str: 配置 JSON 字符串

        Returns:
            导入是否成功
        """
        try:
            imported = json.loads(json_str)
            self._data = self._merge_config(self._data, imported)
            return True
        except json.JSONDecodeError:
            return False

    def _merge_config(self, base: dict, override: dict) -> dict:
        """递归合并配置字典。"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _get_default(self, key_path: str) -> Any:
        """从默认配置中获取值。"""
        keys = key_path.split(".")
        current = DEFAULT_CONFIG
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current

    def _apply_env_overrides(self):
        """应用环境变量覆盖配置。

        支持的环境变量：
          GNOTES_OUTPUT_DIR    - 输出目录
          GNOTES_LANG          - 界面语言
          GNOTES_LOG_LEVEL     - 日志级别
          GNOTES_FFMPEG_PATH   - ffmpeg 路径
        """
        env_map = {
            "GNOTES_OUTPUT_DIR": "general.output_base_dir",
            "GNOTES_LANG": "general.language",
            "GNOTES_LOG_LEVEL": "logging.level",
            "GNOTES_FFMPEG_PATH": "conversion.ffmpeg_path",
        }

        for env_var, config_key in env_map.items():
            value = os.environ.get(env_var)
            if value:
                self.set(config_key, value)


# ============================================================
#  全局配置实例
# ============================================================

_global_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """获取全局配置管理器单例。"""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
        _global_config.load()
    return _global_config


def reset_config():
    """重置全局配置（用于测试）。"""
    global _global_config
    _global_config = None

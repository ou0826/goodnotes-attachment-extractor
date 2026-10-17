"""使用 PyInstaller 构建单文件可执行程序。

同时生成命令行版和图形界面版：
  dist/GoodNotes-Attachment-Extractor.exe       命令行
  dist/GoodNotes-Attachment-Extractor-GUI.exe   图形界面（无控制台）
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "icon.ico"

TARGETS = [
    {
        "name": "GoodNotes-Attachment-Extractor",
        "script": "launcher.py",
        "windowed": False,
    },
    {
        "name": "GoodNotes-Attachment-Extractor-GUI",
        "script": "launcher_gui.py",
        "windowed": True,
    },
]


def build(target: dict) -> Path:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        target["name"],
        "--paths",
        str(ROOT / "src"),
        "--hidden-import",
        "goodnotes_extractor.gui",
        "--console" if not target["windowed"] else "--windowed",
    ]
    if ICON.exists():
        cmd += ["--icon", str(ICON), "--add-data", f"{ICON}{os.pathsep}assets"]
    cmd.append(str(ROOT / "scripts" / target["script"]))

    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    exe = ROOT / "dist" / f"{target['name']}.exe"
    if not exe.exists():
        raise FileNotFoundError(f"Build failed: {exe} not found")

    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"Build complete: {exe} ({size_mb:.1f} MB)")
    return exe


def main() -> int:
    for target in TARGETS:
        build(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

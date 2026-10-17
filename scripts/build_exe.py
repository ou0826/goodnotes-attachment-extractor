"""使用 PyInstaller 构建单文件可执行程序。

用法:
    python scripts/build_exe.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "GoodNotes-Attachment-Extractor"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        NAME,
        "--paths",
        str(ROOT / "src"),
        "--hidden-import",
        "goodnotes_extractor.gui",
        str(ROOT / "scripts" / "launcher.py"),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    exe = ROOT / "dist" / f"{NAME}.exe"
    if not exe.exists():
        print("Build failed: output file not found", file=sys.stderr)
        return 1

    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"Build complete: {exe} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

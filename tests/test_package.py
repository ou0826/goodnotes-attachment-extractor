"""包级冒烟测试：版本号与模块可导入。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import goodnotes_extractor


class TestPackage(unittest.TestCase):
    def test_version_format(self):
        self.assertRegex(goodnotes_extractor.__version__, r"^\d+\.\d+\.\d+$")

    def test_license_declared(self):
        self.assertEqual(goodnotes_extractor.__license__, "MIT")

    def test_core_modules_importable(self):
        from goodnotes_extractor import (  # noqa: F401
            batch,
            classifier,
            config,
            converter,
            logger,
            metadata,
            parser,
        )

    def test_cli_entrypoint_exists(self):
        from goodnotes_extractor.cli import main

        self.assertTrue(callable(main))


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supercover.gui import bundled_resource  # noqa: E402
from supercover.release import main as release_main, run_self_test  # noqa: E402
from supercover.version import __version__  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PortableReleaseTest(unittest.TestCase):
    def test_release_version_is_consistent_across_metadata(self):
        project = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        version_resource = (
            PROJECT_ROOT / "packaging" / "windows-version.txt"
        ).read_text(encoding="utf-8")

        self.assertEqual(__version__, "0.5.0")
        self.assertEqual(project["project"]["version"], __version__)
        self.assertIn("ProductVersion', u'0.5.0.0'", version_resource)
        self.assertIn("filevers=(0, 5, 0, 0)", version_resource)

    def test_source_self_test_validates_tk_and_cover_conversion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "self-test.json"

            report = run_self_test(report_path)
            saved = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(report["status"], "ok")
            self.assertFalse(report["frozen"])
            self.assertEqual(saved["version"], __version__)
            self.assertEqual((saved["cover_width"], saved["cover_height"]), (72, 72))
            self.assertGreater(saved["cover_bytes"], 5_000)

    def test_release_entry_supports_self_test_and_rejects_unknown_arguments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "entry-self-test.json"

            self.assertEqual(release_main(["--self-test", str(report_path)]), 0)
            self.assertTrue(report_path.is_file())
            self.assertEqual(release_main(["--unknown"]), 2)
            self.assertEqual(release_main(["--self-test"]), 2)

    def test_windows_icon_contains_required_sizes_and_transparency(self):
        png_path = PROJECT_ROOT / "assets" / "supercover-icon.png"
        ico_path = PROJECT_ROOT / "assets" / "supercover.ico"

        with Image.open(png_path) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertIsNotNone(image.getchannel("A").getbbox())
        with Image.open(ico_path) as icon:
            self.assertEqual(icon.format, "ICO")
            sizes = icon.ico.sizes()
            self.assertIn((16, 16), sizes)
            self.assertIn((32, 32), sizes)
            self.assertIn((256, 256), sizes)

    def test_spec_is_one_file_windowed_without_upx(self):
        spec = (PROJECT_ROOT / "packaging" / "supercover.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn('name="SuperCover"', spec)
        self.assertIn("console=False", spec)
        self.assertIn("upx=False", spec)
        self.assertIn('"assets" / "supercover.ico"', spec)
        self.assertEqual(
            bundled_resource("assets", "supercover.ico"),
            PROJECT_ROOT / "assets" / "supercover.ico",
        )


if __name__ == "__main__":
    unittest.main()

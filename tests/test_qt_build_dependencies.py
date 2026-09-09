"""Regression: an unrelated tool's same-named ICU DLL must never ship."""
from pathlib import Path
import tempfile
import unittest

from tools.verify_qt_build import audit_sources


class QtBuildDependencyTests(unittest.TestCase):
    def test_user_guide_is_included_in_the_release(self):
        root=Path(__file__).resolve().parents[1]
        guide=root/'USER_GUIDE.md';script=(root/'build-qt.ps1').read_text(encoding='utf8')
        self.assertTrue(guide.is_file())
        self.assertIn('USER_GUIDE.md',script)
        self.assertIn("dist\\MediaAnvilQt\\USER_GUIDE.md",script)
        self.assertIn('# MediaAnvil 使用说明',guide.read_text(encoding='utf8'))

    def test_mit_license_is_included_in_the_release(self):
        root = Path(__file__).resolve().parents[1]
        license_file = root / 'LICENSE'
        script = (root / 'build-qt.ps1').read_text(encoding='utf8')
        self.assertTrue(license_file.is_file())
        self.assertIn('MIT License', license_file.read_text(encoding='utf8'))
        self.assertIn("'LICENSE');.", script)
        self.assertIn("dist\\MediaAnvilQt\\LICENSE", script)

    def test_rejects_foreign_icu_but_accepts_system_and_python_libraries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            python = root / 'python'
            windows = root / 'windows'
            toc = root / 'Analysis-00.toc'
            trusted = [
                ('PySide6/Qt6Core.dll', str(python / 'site-packages/PySide6/Qt6Core.dll'), 'BINARY'),
                ('icuuc.dll', str(windows / 'System32/icuuc.dll'), 'BINARY'),
            ]
            toc.write_text(repr(('metadata', [trusted])), encoding='utf8')
            audit_sources(toc, [python, windows])
            trusted.append(('icuuc.dll', str(root / 'python-other/poppler/icuuc.dll'), 'BINARY'))
            toc.write_text(repr(('metadata', [trusted])), encoding='utf8')
            with self.assertRaisesRegex(RuntimeError, 'poppler'):
                audit_sources(toc, [python, windows])


if __name__ == '__main__':
    unittest.main()

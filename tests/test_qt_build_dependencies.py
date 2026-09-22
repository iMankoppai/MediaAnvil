"""Regression: an unrelated tool's same-named ICU DLL must never ship."""
from pathlib import Path
import re
import tempfile
import unittest

from tools.verify_qt_build import audit_sources, verify_release_documents


class QtBuildDependencyTests(unittest.TestCase):
    def test_build_uses_windows_icu_and_requires_a_completed_smoke_report(self):
        root = Path(__file__).resolve().parents[1]
        build_script = (root / 'build-qt.ps1').read_text(encoding='utf8')
        verifier = (root / 'tools/verify_qt_build.py').read_text(encoding='utf8')
        self.assertNotIn('download_icu', build_script)
        self.assertNotIn("vendor\\icu", build_script)
        self.assertNotIn("'icuuc.dll');PySide6", build_script)
        self.assertIn("directory.rglob('icu*.dll')", verifier)
        self.assertIn("'--smoke-test'", verifier)
        self.assertIn("report.json", verifier)

    def test_user_guide_is_included_in_the_release(self):
        root=Path(__file__).resolve().parents[1]
        guide=root/'USER_GUIDE.md';script=(root/'build-qt.ps1').read_text(encoding='utf8')
        self.assertTrue(guide.is_file())
        self.assertIn('USER_GUIDE.md',script)
        self.assertIn("dist\\MediaAnvilQt\\USER_GUIDE.md",script)
        self.assertIn('# MediaAnvil 使用说明',guide.read_text(encoding='utf8'))
        english_guide=root/'USER_GUIDE.en.md';english_build=root/'README-Qt.en.md'
        self.assertTrue(english_guide.is_file());self.assertTrue(english_build.is_file())
        self.assertIn("dist\\MediaAnvilQt\\USER_GUIDE.en.md",script)
        self.assertIn("dist\\MediaAnvilQt\\README-Qt.md",script)
        self.assertIn("dist\\MediaAnvilQt\\README-Qt.en.md",script)
        self.assertIn('# MediaAnvil User Guide',english_guide.read_text(encoding='utf8'))

    def test_mit_license_is_included_in_the_release(self):
        root = Path(__file__).resolve().parents[1]
        license_file = root / 'LICENSE'
        script = (root / 'build-qt.ps1').read_text(encoding='utf8')
        self.assertTrue(license_file.is_file())
        self.assertIn('MIT License', license_file.read_text(encoding='utf8'))
        self.assertIn("'LICENSE');.", script)
        self.assertIn("dist\\MediaAnvilQt\\LICENSE", script)

    def test_third_party_notices_and_licenses_are_in_the_release_root(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / 'build-qt.ps1').read_text(encoding='utf8')
        notices = root / 'THIRD_PARTY_NOTICES.md'
        self.assertTrue(notices.is_file())
        self.assertIn("dist\\MediaAnvilQt\\THIRD_PARTY_NOTICES.md", script)
        self.assertIn("dist\\MediaAnvilQt\\licenses\\qt", script)
        self.assertIn('FFmpeg', notices.read_text(encoding='utf8'))
        self.assertTrue((root / 'licenses/qt/GPL-3.0.txt').is_file())

    def test_release_document_check_rejects_incomplete_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, 'THIRD_PARTY_NOTICES.md'):
                verify_release_documents(directory)
            for name in ('USER_GUIDE.md', 'USER_GUIDE.en.md', 'README-Qt.md',
                         'README-Qt.en.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
                (directory / name).write_text('x', encoding='utf8')
            with self.assertRaisesRegex(RuntimeError, 'licenses/qt'):
                verify_release_documents(directory)
            (directory / 'licenses/qt').mkdir(parents=True)
            (directory / 'licenses/qt/GPL-3.0.txt').write_text('x', encoding='utf8')
            verify_release_documents(directory)

    def test_release_notes_come_from_the_changelog(self):
        from tools.release_notes import notes_for, section_for
        root = Path(__file__).resolve().parents[1]
        changelog = root / 'CHANGELOG.md'
        current = (root / 'mediaanvil_qt/__init__.py').read_text(encoding='utf8')
        version = re.search(r"__version__\s*=\s*'([^']+)'", current).group(1)
        # the shipped version must have a real entry, or the release would be empty
        notes = notes_for(version, changelog)
        self.assertIsNotNone(notes, f'CHANGELOG.md has no section for {version}')
        self.assertIn(version, notes)
        self.assertGreater(len(notes.splitlines()), 3, notes)
        self.assertIsNotNone(notes_for(f'v{version}', changelog))
        self.assertIsNone(notes_for('v99.99.99', changelog))
        self.assertIsNone(section_for('v99.99.99', changelog))

    def test_release_workflow_uses_changelog_notes(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / '.github/workflows/release.yml').read_text(encoding='utf8')
        self.assertIn('tools/release_notes.py', workflow)
        self.assertIn('--notes-file', workflow)
        self.assertNotIn('--generate-notes', workflow)
        # an existing release must also pick up corrected notes
        self.assertIn('gh release edit', workflow)

    def test_release_notes_script_fails_without_an_entry(self):
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / 'tools/release_notes.py'), 'v99.99.99'],
            capture_output=True, text=True, cwd=root)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('no section', completed.stderr)

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

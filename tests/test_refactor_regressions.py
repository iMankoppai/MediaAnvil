"""Behavioral regressions found while separating Qt responsibilities."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QApplication

from mediaanvil_qt.file_widgets import FileList
from mediaanvil_qt.i18n import current_language, set_current_language, tr
from mediaanvil_qt.preview_lyrics import PreviewLyricsMixin
from mediaanvil_qt.table_widgets import StatusDelegate


class RefactorRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_reordering_multiple_files_preserves_selection_and_check_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / f'{i}.wav' for i in range(4)]
            for path in paths:
                path.touch()
            files = FileList({'.wav'}, reorderable=True)
            files.add_paths(paths)
            files.item(1).setCheckState(Qt.CheckState.Unchecked)
            self.assertTrue(files.move_rows([0, 1], 4))
            self.assertEqual(files.paths(), tuple(paths[2:] + paths[:2]))
            self.assertEqual({item.text() for item in files.selectedItems()}, {str(p) for p in paths[:2]})
            self.assertEqual(files.item(3).checkState(), Qt.CheckState.Unchecked)
            # The next move should carry both rows, as a user expects.
            self.assertTrue(files.move_rows([files.row(item) for item in files.selectedItems()], 0))
            self.assertEqual(files.paths(), tuple(paths))
            files.close()

    def test_success_badge_color_does_not_depend_on_interface_language(self):
        previous = current_language()
        try:
            delegate = StatusDelegate()
            for language in ('zh_CN', 'en_US'):
                set_current_language(language)
                for state, expected in (('已完成', '#e1f6e9'), ('可重命名', '#e1f6e9'), ('可重命名（自动避让）', '#e1f6e9'), ('失败', '#fff0e5')):
                    with self.subTest(language=language, state=state):
                        index = MagicMock()
                        index.data.return_value = tr(state, language)
                        painter = MagicMock()
                        delegate.paint(painter, SimpleNamespace(rect=QRect(0, 0, 150, 40)), index)
                        self.assertEqual(painter.setBrush.call_args.args[0].name(), expected)
        finally:
            set_current_language(previous)

    def test_saving_shifted_lyrics_captures_text_before_background_work(self):
        class Preview(PreviewLyricsMixin):
            pass

        preview = Preview()
        preview.path = Path('track.mp3')
        preview.base_timeline = (object(),)
        preview.applied_shift = 1.0
        preview.lyric_source = '[00:01.00]Original'
        jobs = []
        preview.app = SimpleNamespace(run_task=lambda work, done: jobs.append(work), t=lambda text: text)
        preview.save_shifted_lyrics()
        preview.applied_shift = 5.0
        preview.lyric_source = '[00:10.00]Changed'
        written = []

        def write(path, changes, target):
            written.append(changes.lyrics_path.read_text(encoding='utf-8'))
            return target

        with patch('mediaanvil_qt.preview_lyrics.write_metadata', side_effect=write):
            jobs[0](None)
        self.assertEqual(written, ['[00:02.00]Original'])

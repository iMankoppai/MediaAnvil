import time,tempfile,unittest,threading,wave,re
from pathlib import Path
from unittest.mock import MagicMock,patch
from PIL import Image
try:
    from PySide6.QtCore import QTimer,Qt,QPoint,QPointF,QMimeData,QUrl,QSize
    from PySide6.QtWidgets import (QApplication,QPushButton,QSizePolicy,QLabel,QAbstractButton,
        QComboBox,QDialog,QLineEdit,QPlainTextEdit,QTableWidget,QListWidget,QWidget)
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QDragEnterEvent,QDropEvent,QFontInfo
except ImportError:
    raise unittest.SkipTest('Install requirements-qt.txt to run Qt interface tests')
from mediaanvil_qt.app import MainWindow,default_window_size
from mediaanvil_qt.common import dialog_initial_directory
from mediaanvil_qt.documents import DocumentViewer
from mediaanvil_qt.i18n import localize_dialog_buttons
from mediaanvil_qt import __version__ as qt_version
from mediaanvil_qt.design import STYLE
from mediaanvil_qt.services import collect_paths,convert_files,write_matches
from mediaanvil_qt.metadata import CropDialog
from core.settings import save_settings
from sub2lrc.audio_converter import AudioConversionSettings
from sub2lrc.image_converter import ImageConversionSettings
from sub2lrc.audio_metadata import read_metadata
from sub2lrc.audio_preview import PlaybackState


class QtRewriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.window=MainWindow(self.base/'settings.json');self.messages=[]
        self.window.inform=lambda message:self.messages.append(str(message))
        self.window.show_text=lambda title,text:self.messages.append(str(text))
        self.window.present_document=lambda title,text:self.messages.append(str(text))
        self.window.show();self.qt.processEvents()
    def tearDown(self):
        self.wait();self.window.close();self.qt.processEvents();self.temp.cleanup()
    def wait(self):
        deadline=time.monotonic()+20
        while self.window._worker and time.monotonic()<deadline:
            self.qt.processEvents();time.sleep(.005)
        self.assertIsNone(self.window._worker,'worker did not complete');self.qt.processEvents()
    def test_pages_preserve_native_window_and_data(self):
        self.assertEqual(qt_version,'1.1.0')
        self.assertIn('v1.1.0',[label.text() for label in self.window.findChildren(QLabel)])
        self.assertEqual(len(self.window.pages),8)
        actual_size=(self.window.width(),self.window.height());expected_size=default_window_size()
        for actual,expected in zip(actual_size,expected_size):self.assertAlmostEqual(actual,expected,delta=1)
        self.assertFalse(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertIn('QPushButton#navItem { background:transparent; border:0; border-left:2px solid transparent; border-radius:8px; text-align:left; padding:12px 14px; min-height:22px; font-size:15px; font-weight:600; }',STYLE)
        self.assertIn('QSlider:horizontal { padding:0 8px; }',STYLE)
        self.assertIn('QSlider::handle:horizontal { background:white; border:2px solid #397bf3; width:12px; height:12px;',STYLE)
        self.assertFalse(hasattr(self.window.pages['preview'],'open_folder'))
        self.assertIn('使用说明',[button.text() for button in self.window.pages['about'].findChildren(QPushButton)])
        self.window.pages['editor'].title.setText('未保存的草稿')
        for i in range(8):self.window.navigation.setCurrentRow(i);self.qt.processEvents()
        self.assertEqual(self.window.pages['editor'].title.text(),'未保存的草稿')

    def test_about_documents_open_in_read_only_app_dialog_with_matching_language(self):
        about=self.window.pages['about']
        buttons={control.text():control for control in about.findChildren(QPushButton)}
        QTest.mouseClick(buttons['使用说明'],Qt.MouseButton.LeftButton)
        self.assertIn('# MediaAnvil 使用说明',self.messages[-1])
        self.window.set_language('en_US');self.qt.processEvents()
        buttons={control.text():control for control in about.findChildren(QPushButton)}
        QTest.mouseClick(buttons['User Guide'],Qt.MouseButton.LeftButton)
        self.assertIn('# MediaAnvil User Guide',self.messages[-1])
        QTest.mouseClick(buttons['Third-party Notices'],Qt.MouseButton.LeftButton)
        self.assertIn('FFmpeg',self.messages[-1])

    def test_file_dialog_uses_and_remembers_media_directories(self):
        first=self.base/'first-audio';first.mkdir()
        second=self.base/'second-audio';second.mkdir();selected=second/'track.wav';selected.touch()
        page=self.window.pages['preview'];self.window.settings['last_audio_directory']=str(first)
        with patch.object(page,'receive') as receive,patch('mediaanvil_qt.preview.QFileDialog.getOpenFileNames',return_value=([str(selected)],'')) as choose:
            page.choose()
        self.assertEqual(choose.call_args.args[2],str(first))
        receive.assert_called_once_with([selected])
        self.assertEqual(self.window.settings['last_audio_directory'],str(second.resolve()))

        pictures=self.base/'pictures';pictures.mkdir();self.window.settings['last_image_directory']=str(pictures)
        image_page=self.window.pages['image'];add=image_page.toolbar.findChildren(QPushButton)[0]
        with patch('mediaanvil_qt.common.QFileDialog.getOpenFileNames',return_value=([],'')) as choose:
            QTest.mouseClick(add,Qt.MouseButton.LeftButton)
        self.assertEqual(choose.call_args.args[2],str(pictures))

    def test_file_dialog_fallback_uses_windows_user_location_not_process_directory(self):
        music=self.base/'Music';music.mkdir();self.window.settings['last_audio_directory']=''
        with patch('mediaanvil_qt.common.QStandardPaths.writableLocation',return_value=str(music)):
            self.assertEqual(dialog_initial_directory(self.window,'audio'),str(music))

    def test_document_viewer_renders_markdown_with_outline_and_search(self):
        markdown='# 标题一\n\n正文 **加粗** 与 `code`。\n\n## 章节二\n\n- 项目 A\n- 项目 B\n\n```text\ncode block\n```\n'
        viewer=DocumentViewer('使用说明',markdown,'zh_CN')
        self.assertEqual([row[1] for row in viewer.outline_rows],['标题一','章节二'])
        self.assertEqual([row[0] for row in viewer.outline_rows],[1,2])
        self.assertIn('加粗',viewer.browser.toPlainText())
        viewer.outline.setCurrentRow(1)
        self.assertIn('章节二',viewer.browser.textCursor().block().text())
        viewer.search.setText('项目 B');viewer.find_next()
        self.assertTrue(viewer.browser.textCursor().hasSelection())
        viewer.search.setText('不存在的文字');viewer.find_next()
        self.assertIn('未找到',viewer.status.text())
        viewer.close()

    def test_document_viewer_never_opens_network_links(self):
        viewer=DocumentViewer('使用说明','# 标题\n\n[外链](https://example.com/page)\n','zh_CN')
        clicked=[]
        viewer.resolver=lambda url:clicked.append(url.toString())
        with patch('mediaanvil_qt.documents.QApplication.clipboard') as clipboard:
            from PySide6.QtCore import QUrl
            viewer._link_clicked(QUrl('https://example.com/page'))
        clipboard.return_value.setText.assert_called_once_with('https://example.com/page')
        self.assertEqual(clicked,[])
        self.assertIn('未打开网络地址',viewer.status.text())
        viewer.close()

    def test_document_viewer_follows_bundled_relative_links_only(self):
        resolver_calls=[]
        def resolver(url):
            resolver_calls.append(url.toString())
            return ('使用说明','# 新文档\n')
        viewer=DocumentViewer('使用说明','# 标题\n','zh_CN',resolver)
        from PySide6.QtCore import QUrl
        viewer._link_clicked(QUrl('USER_GUIDE.en.md'))
        self.assertEqual(resolver_calls,['USER_GUIDE.en.md'])
        self.assertEqual([row[1] for row in viewer.outline_rows],['新文档'])
        viewer.close()

    def test_standard_dialog_buttons_follow_interface_language(self):
        from PySide6.QtWidgets import QDialogButtonBox
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Close|QDialogButtonBox.StandardButton.Cancel)
        holder=QWidget();box.setParent(holder)
        localize_dialog_buttons(holder,'zh_CN')
        self.assertEqual(box.button(QDialogButtonBox.StandardButton.Close).text(),'关闭')
        self.assertEqual(box.button(QDialogButtonBox.StandardButton.Cancel).text(),'取消')
        localize_dialog_buttons(holder,'en_US')
        self.assertEqual(box.button(QDialogButtonBox.StandardButton.Close).text(),'Close')
        self.assertEqual(box.button(QDialogButtonBox.StandardButton.Cancel).text(),'Cancel')
        holder.close()

    def test_document_viewer_reports_missing_and_unreadable_documents(self):
        with patch('mediaanvil_qt.app.resource',return_value=self.base/'missing.md'):
            self.window.show_document('使用说明','USER_GUIDE.md')
        self.assertIn('文档无法打开',self.messages[-1])
        broken=self.base/'broken.md';broken.write_bytes(b'\xff\xfe\x00\x00bad')
        with patch('mediaanvil_qt.app.resource',return_value=broken):
            self.window.show_document('使用说明','USER_GUIDE.md')
        self.assertIn('文档无法打开',self.messages[-1])

    def test_every_import_export_dialog_uses_its_remembered_directory(self):
        settings=self.window.settings
        directories={key:self.base/folder for key,folder in (
            ('last_audio_directory','audio'),('last_image_directory','image'),
            ('last_subtitle_directory','subtitle'),('last_output_directory','output'))}
        for folder in directories.values():folder.mkdir()
        settings.update({key:str(folder) for key,folder in directories.items()})
        editor=self.window.pages['editor']
        source=directories['last_audio_directory']/'track.mp3';source.touch()
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=(str(source),'')) as choose:
            editor.choose()
        self.assertEqual(choose.call_args.args[2],str(directories['last_audio_directory']))
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=('','')) as choose:
            editor.import_lyrics()
        self.assertEqual(choose.call_args.args[2],str(directories['last_subtitle_directory']))
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=('','')) as choose:
            editor.import_cover()
        self.assertEqual(choose.call_args.args[2],str(directories['last_image_directory']))
        with patch('mediaanvil_qt.metadata.QFileDialog.getExistingDirectory',return_value='') as choose:
            editor.scan_folder()
        self.assertEqual(choose.call_args.args[2],str(directories['last_audio_directory']))
        editor.path=source
        with patch('mediaanvil_qt.metadata.QFileDialog.getExistingDirectory',return_value='') as choose:
            editor.export('lyrics')
        self.assertEqual(choose.call_args.args[2],str(directories['last_output_directory']))
        output_page=self.window.pages['audio'].output
        with patch('mediaanvil_qt.common.QFileDialog.getExistingDirectory',return_value='') as choose:
            output_page.choose()
        self.assertEqual(choose.call_args.args[2],str(directories['last_output_directory']))

    def test_dialog_selection_is_ignored_on_cancel_and_falls_back_when_missing(self):
        from mediaanvil_qt.common import remember_dialog_selection
        settings=self.window.settings
        missing=self.base/'gone'
        settings['last_audio_directory']=str(missing)
        self.assertFalse(missing.exists())
        fallback=dialog_initial_directory(self.window,'audio')
        self.assertNotEqual(fallback,str(missing))
        self.assertTrue(Path(fallback).is_dir(),fallback)
        self.assertNotEqual(Path(fallback).resolve(),Path.cwd().resolve())
        before=settings['last_audio_directory']
        remember_dialog_selection(self.window,'audio','')
        remember_dialog_selection(self.window,'audio',None)
        self.assertEqual(settings['last_audio_directory'],before)
        settings['last_audio_directory']=str(missing)
        settings['last_output_directory']=str(missing)
        with patch('mediaanvil_qt.common.QFileDialog.getExistingDirectory',return_value='') as choose:
            self.window.pages['audio'].output.choose()
        self.assertEqual(choose.call_args.args[2],dialog_initial_directory(self.window,'output'))
        self.assertEqual(settings['last_output_directory'],str(missing))

    def test_dialog_categories_do_not_interfere(self):
        from mediaanvil_qt.common import remember_dialog_selection
        settings=self.window.settings
        for key in ('last_audio_directory','last_image_directory','last_subtitle_directory','last_output_directory'):
            settings[key]=''
        audio=self.base/'a';image=self.base/'i';subtitle=self.base/'s';output=self.base/'o'
        for folder in (audio,image,subtitle,output):folder.mkdir()
        remember_dialog_selection(self.window,'audio',str(audio))
        remember_dialog_selection(self.window,'image',str(image))
        remember_dialog_selection(self.window,'subtitle',str(subtitle))
        remember_dialog_selection(self.window,'output',str(output))
        self.assertEqual(settings['last_audio_directory'],str(audio.resolve()))
        self.assertEqual(settings['last_image_directory'],str(image.resolve()))
        self.assertEqual(settings['last_subtitle_directory'],str(subtitle.resolve()))
        self.assertEqual(settings['last_output_directory'],str(output.resolve()))

    def test_remembered_directory_survives_restart(self):
        config=self.base/'restart.json'
        self.window.settings['last_audio_directory']=str(self.base)
        self.window.settings_file=config
        self.window.close();self.qt.processEvents()
        reopened=MainWindow(config);reopened.show();self.qt.processEvents()
        try:
            self.assertEqual(reopened.settings['last_audio_directory'],str(self.base))
            self.assertEqual(dialog_initial_directory(reopened,'audio'),str(self.base))
        finally:
            reopened.close();self.qt.processEvents()

    def test_dynamic_dialogs_have_no_chinese_left_in_english_mode(self):
        from PySide6.QtWidgets import QMessageBox
        self.window.set_language('en_US');self.qt.processEvents()
        viewer=DocumentViewer('User Guide','# Title\n\n## Section\n','en_US')
        leftovers=[]
        for widget in [viewer,*viewer.findChildren(QWidget)]:
            values=[]
            if isinstance(widget,(QLabel,QAbstractButton)):values.append(widget.text())
            if isinstance(widget,(QLineEdit,QPlainTextEdit)):values.append(widget.placeholderText())
            if isinstance(widget,QListWidget):values.extend(widget.item(i).text() for i in range(widget.count()))
            values.append(widget.windowTitle() if isinstance(widget,QDialog) else '')
            leftovers.extend(value for value in values if value and re.search(r'[\u3400-\u9fff]',value))
        self.assertEqual(leftovers,[],leftovers)
        box=QMessageBox(self.window);box.setStandardButtons(QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel)
        self.assertEqual(box.button(QMessageBox.StandardButton.Ok).text(),'OK')
        self.assertEqual(box.button(QMessageBox.StandardButton.Cancel).text(),'Cancel')
        viewer.close();box.close()
        self.window.set_language('zh_CN');self.qt.processEvents()
        box=QMessageBox(self.window);box.setStandardButtons(QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel)
        self.assertEqual(box.button(QMessageBox.StandardButton.Ok).text(),'确定')
        self.assertEqual(box.button(QMessageBox.StandardButton.Cancel).text(),'取消')
        box.close()

    def test_bundled_documents_are_readable_and_never_leave_the_install(self):
        from mediaanvil_qt.common import resource
        for name in ('USER_GUIDE.md','USER_GUIDE.en.md','THIRD_PARTY_NOTICES.md'):
            path=resource(name)
            self.assertTrue(path.is_file(),name)
            self.assertTrue(path.read_text(encoding='utf-8').strip(),name)
        self.window.settings['language']='en_US'
        with patch.object(self.window,'present_document') as shown:
            self.window.show_document('使用说明','USER_GUIDE.md','USER_GUIDE.en.md')
        self.assertIn('# MediaAnvil User Guide',shown.call_args.args[1])
        self.window.settings['language']='zh_CN'
        with patch.object(self.window,'present_document') as shown:
            self.window.show_document('使用说明','USER_GUIDE.md','USER_GUIDE.en.md')
        self.assertIn('# MediaAnvil 使用说明',shown.call_args.args[1])
        resolved=self.window.resolve_document(QUrl('USER_GUIDE.en.md'))
        self.assertIsNotNone(resolved)
        self.assertIn('# MediaAnvil User Guide',resolved[1])
        self.assertIsNone(self.window.resolve_document(QUrl('https://example.com/x.md')))
        self.assertIsNone(self.window.resolve_document(QUrl('../../secret.md')))
        self.assertIsNone(self.window.resolve_document(QUrl('NOT_A_REAL_FILE.md')))

    def test_fixed_footer_never_overlaps_scrolling_content(self):
        for width,height in ((1440,900),(1100,700),(900,640)):
            self.window.resize(width,height)
            for index,key in enumerate(self.window.keys):
                self.window.navigation.setCurrentRow(index)
                for _ in range(3):self.qt.processEvents()
                page=self.window.pages[key]
                scroll=getattr(page,'scroll',None)
                if scroll is None:continue
                self.assertGreater(scroll.viewport().height(),0,key)
                if not hasattr(page,'footer'):continue
                footer_top=page.footer.mapTo(self.window,page.footer.rect().topLeft()).y()
                scroll_bottom=scroll.mapTo(self.window,scroll.rect().bottomLeft()).y()
                self.assertLessEqual(scroll_bottom,footer_top+1,f'{key} at {width}x{height}')
                bottom=page.footer.mapTo(self.window,page.footer.rect().bottomRight())
                self.assertTrue(self.window.rect().contains(bottom),f'{key} footer clipped at {width}x{height}')

    def test_default_window_size_adapts_to_available_space(self):
        self.assertEqual(default_window_size(QSize(1536,824),30,1.25),(1152,738))
        self.assertEqual(default_window_size(QSize(1280,680),30,1),(969,616))
        self.assertEqual(default_window_size(QSize(2560,1440),30,1),(1440,930))
        self.assertEqual(default_window_size(QSize(1920,1080),30,1),(1440,930))
        # a 1536x816 logical desktop (1920x1080 at 125%) must reach the design size
        self.assertEqual(default_window_size(QSize(1536,816),30,1.25),(1152,738))
        self.assertEqual(default_window_size(QSize(3840,2160),30,1),(1440,930))
        # small screens still scale down and never exceed the usable area
        tiny=default_window_size(QSize(1024,600),30,1)
        self.assertLessEqual(tiny[1]+30,600)
        self.assertGreaterEqual(tiny[0],760)

    def test_window_starts_at_default_size_in_screen_center(self):
        actual_size=(self.window.width(),self.window.height());expected_size=default_window_size()
        for actual,expected in zip(actual_size,expected_size):self.assertAlmostEqual(actual,expected,delta=1)
        available=QApplication.primaryScreen().availableGeometry();center=self.window.frameGeometry().center()
        self.assertLessEqual(abs(center.x()-available.center().x()),2)
        self.assertLessEqual(abs(center.y()-available.center().y()),2)
        self.assertNotIn('remember_window_geometry',self.window.pages['settings'].controls)

    def test_startup_always_opens_audio_preview(self):
        config=self.base/'startup-settings.json';values=dict(self.window.settings)
        values['remember_last_page']=True;values['last_page']='image';save_settings(values,config)
        other=MainWindow(config);other.show();self.qt.processEvents()
        self.assertEqual(other.current_page,other.pages['preview'])
        self.assertEqual(other.navigation.currentRow(),other.keys.index('preview'))
        self.assertNotIn('remember_last_page',other.pages['settings'].controls)
        other.close();self.qt.processEvents()

    def test_lyric_list_uses_a_symbol_font(self):
        lyrics=(
            self.window.pages['preview'].lyrics,
            self.window.pages['editor'].lyrics,
            self.window.pages['subtitle'].results,
        )
        for view in lyrics:self.assertIn('Segoe UI Symbol',view.styleSheet())
        self.qt.processEvents()
        for view in lyrics:self.assertEqual(QFontInfo(view.font()).family(),'Segoe UI Symbol')
        self.assertIn('font-size:17px; font-weight:600',self.window.pages['preview'].lyrics.styleSheet())
        self.assertIn('background:#edf4ff; font-weight:700',self.window.pages['preview'].lyrics.styleSheet())
        self.assertIn('QListWidget::item:focus { border:0; outline:0; }',self.window.pages['preview'].lyrics.styleSheet())
        self.assertEqual(type(self.window.pages['preview'].lyrics.itemDelegate()).__name__,'LyricItemDelegate')
    def test_settings_cards_fill_width_and_keyboard_switch_preserves_value(self):
        self.window.navigation.setCurrentRow(self.window.keys.index('settings'));self.qt.processEvents()
        page=self.window.pages['settings'];switch=page.controls['include_subfolders']
        for _ in range(4):self.qt.processEvents()
        self.assertEqual(page.scroll.verticalScrollBar().maximum(),0)
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0)
        scan=page.sections[-1]
        self.assertTrue(scan.isVisible())
        self.assertFalse(hasattr(page,'search'))
        self.assertLessEqual(abs(page.section_host.width()-page.contentsRect().width()+page.layout.contentsMargins().left()+page.layout.contentsMargins().right()),1)
        self.assertLessEqual(abs(scan.width()-page.section_host.width()),1)
        self.assertLess(scan.mapTo(page,scan.rect().bottomRight()).y(),page.height())
        self.assertLess(scan.mapTo(self.window,scan.rect().bottomRight()).y(),page.footer.mapTo(self.window,page.footer.rect().topLeft()).y())
        before=switch.isChecked()
        switch.setFocus();QTest.keyClick(switch,Qt.Key.Key_Space)
        self.assertEqual(switch.isChecked(),not before)
    def test_narrow_window_keeps_navigation_and_actions_accessible(self):
        self.window.resize(900,640);self.qt.processEvents()
        for index,key in enumerate(self.window.keys):
            self.window.navigation.setCurrentRow(index)
            for _ in range(4):self.qt.processEvents()
            page=self.window.pages[key]
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0,key)
            if hasattr(page,'footer'):
                self.assertTrue(page.footer.isVisible(),key)
                bottom=page.footer.mapTo(self.window,page.footer.rect().bottomRight())
                self.assertTrue(self.window.rect().contains(bottom),key)

    def test_default_window_uses_expected_responsive_conversion_layout(self):
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key));self.qt.processEvents()
            page=self.window.pages[key]
            expected_direction=(page.columns.box.Direction.LeftToRight if page.columns.width()>=page.columns.breakpoint
                                else page.columns.box.Direction.TopToBottom)
            self.assertEqual(page.columns.box.direction(),expected_direction,key)
            expected_height={'subtitle':170,'audio':170,'image':160}[key] if page._roomy else 28
            self.assertEqual(page.files.height(),expected_height,key)
            expected_add='添加图片' if page._roomy and key=='image' else '添加文件' if page._roomy else '添加…'
            self.assertEqual([button.text() for button in page.toolbar.findChildren(QPushButton)],[expected_add,'移除','清空'])
            self.assertNotIn('文件夹',''.join(button.text() for button in page.toolbar.findChildren(QPushButton)))
            maximum=page.scroll.verticalScrollBar().maximum()
            if page._roomy:self.assertLessEqual(maximum,40,key)
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0,key)
        self.window.resize(1200,800);self.qt.processEvents()
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key))
            for _ in range(4):self.qt.processEvents()
            page=self.window.pages[key]
            self.assertFalse(page.source_detail.isVisible(),key)
            expected_height={'subtitle':170,'audio':170,'image':160}[key] if page._roomy else 28
            self.assertEqual(page.files.height(),expected_height,key)
            maximum=page.scroll.verticalScrollBar().maximum()
            if page._roomy:self.assertEqual(maximum,0,key)
            toolbar_buttons=page.toolbar.findChildren(QPushButton)
            self.assertLessEqual(max(button.width() for button in toolbar_buttons)-min(button.width() for button in toolbar_buttons),1,key)
            self.assertLessEqual(abs(page.toolbar.width()-page.files.width()),1,key)
            self.assertLessEqual(abs(page.select_all.mapTo(page,QPoint(0,0)).y()-page.file_count.mapTo(page,QPoint(0,0)).y()),2,key)
            self.assertLessEqual(abs(page.file_count.mapTo(page.selection_row,page.file_count.rect().topRight()).x()-page.selection_row.contentsRect().right()),1,key)
            if page.columns.box.direction()==page.columns.box.Direction.LeftToRight:
                left_bottom=page.step_cards[1].mapTo(page,page.step_cards[1].rect().bottomRight()).y()
                right_bottom=page.step_cards[2].mapTo(page,page.step_cards[2].rect().bottomRight()).y()
                self.assertLessEqual(abs(left_bottom-right_bottom),1,key)
        self.window.resize(*default_window_size());
        for _ in range(4):self.qt.processEvents()
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key))
            for _ in range(4):self.qt.processEvents()
            page=self.window.pages[key];maximum=page.scroll.verticalScrollBar().maximum()
            if page._roomy:self.assertLessEqual(maximum,40,key)
    def test_remove_uses_file_checkboxes_on_every_batch_page(self):
        extensions={'subtitle':'.lrc','audio':'.wav','image':'.png','renamer':'.mp3'}
        for key,extension in extensions.items():
            page=self.window.pages[key];paths=[]
            for index in range(3):
                path=self.base/f'{key}-{index}{extension}';path.write_bytes(b'test');paths.append(path)
            page.files.clear();page.files.add_paths(paths)
            page.files.item(1).setCheckState(Qt.CheckState.Unchecked)
            remove=next(control for control in page.toolbar.findChildren(QPushButton) if control.text()=='移除')
            remove.click();self.qt.processEvents()
            self.assertEqual(page.files.paths(),(paths[1],),key)
            self.assertTrue(all(path.exists() for path in paths),key)
            page.files.clear();page.files.add_paths(paths);remove.click();self.qt.processEvents()
            self.assertEqual(page.files.count(),0,key)
            self.assertTrue(all(path.exists() for path in paths),key)
    def test_worker_keeps_event_loop_live_and_delivers_on_gui_thread(self):
        pulses=[];received=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:pulses.append(1));timer.start()
        def work(report):
            time.sleep(.15);report(50,'test');return threading.get_ident()
        self.window.run_task(work,lambda result:received.append((result,threading.get_ident())))
        self.wait();timer.stop()
        self.assertGreater(len(pulses),5)
        self.assertNotEqual(received[0][0],received[0][1]);self.assertEqual(received[0][1],threading.get_ident())
        self.assertTrue(self.window.centralWidget().isEnabled())
    def test_worker_failure_recovers_interface(self):
        self.window.run_task(lambda report:1/0,lambda value:None);self.wait()
        self.assertIn('division by zero',self.messages[-1]);self.assertTrue(self.window.centralWidget().isEnabled())
    def test_worker_can_be_cancelled_and_recovers_interface(self):
        completed=[]
        def work(report):
            while True:
                report.raise_if_cancelled();time.sleep(.005)
        self.window.run_task(work,completed.append);self.qt.processEvents()
        self.assertTrue(self.window.cancel_button.isVisible())
        self.window.cancel_button.click();self.wait()
        self.assertFalse(completed);self.assertFalse(self.window.cancel_button.isVisible())
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertEqual(self.window.statusBar().currentMessage(),'任务已取消')
    def test_close_during_work_is_blocked(self):
        self.window.run_task(lambda report:time.sleep(.1),lambda value:None)
        self.assertFalse(self.window.close());self.wait();self.assertTrue(self.window.isVisible())
    def test_subtitle_ui_conversion_is_safe_and_uses_source_folder(self):
        source=self.base/'歌曲.srt';source.write_text('1\n00:00:01,000 --> 00:00:02,000\n你好\n',encoding='utf8')
        before=source.read_bytes();page=self.window.pages['subtitle'];page.receive([source]);page.start();self.wait()
        self.assertEqual(source.read_bytes(),before);self.assertTrue((self.base/'歌曲.lrc').exists())
        page.start();self.wait();self.assertTrue((self.base/'歌曲_1.lrc').exists())
    def test_image_conversion_retains_source_and_flattens_alpha(self):
        source=self.base/'透明.png';Image.new('RGBA',(15,21),(0,0,0,0)).save(source);original=source.read_bytes()
        outputs,lines=convert_files('image',[source],'',ImageConversionSettings('jpg',90),lambda *args:None)
        with Image.open(outputs[0]) as image:
            self.assertEqual(image.size,(15,21));self.assertGreater(image.getpixel((0,0))[0],245)
        self.assertEqual(source.read_bytes(),original);self.assertIn('透明区域已填白',lines[0])
    def test_folder_import_honours_recursion_and_deduplication(self):
        (self.base/'a.lrc').write_text('[00:01]a');(self.base/'child').mkdir();(self.base/'child'/'b.lrc').write_text('[00:01]b')
        self.assertEqual(len(collect_paths([self.base,self.base/'a.lrc'],{'.lrc'},False)),1)
        self.assertEqual(len(collect_paths([self.base],{'.lrc'},True)),2)
    def test_ambiguous_matches_do_not_autoselect(self):
        page=self.window.pages['editor'];paths=[self.base/'a.lrc',self.base/'b.lrc']
        page.candidates(page.lyric_match,paths);self.assertIsNone(page.lyric_match.currentData())
    def test_metadata_media_actions_align_without_a_separate_crop_button(self):
        page=self.window.pages['editor'];self.window.navigation.setCurrentRow(self.window.keys.index('editor'));self.qt.processEvents()
        self.assertFalse(page.match_content.isVisible());self.assertEqual(page.match_toggle.text(),'展开匹配区域')
        self.assertFalse(page.match_note.wordWrap())
        actions=(page.import_lyrics_button,page.export_lyrics_button,page.import_cover_button,page.export_cover_button)
        for action in actions:
            self.assertEqual(action.sizePolicy().horizontalPolicy(),QSizePolicy.Policy.Ignored)
            self.assertTrue(action.isVisible());self.assertGreater(action.width(),70)
        self.assertLessEqual(abs(page.import_lyrics_button.width()-page.export_lyrics_button.width()),1)
        self.assertLessEqual(abs(page.import_cover_button.width()-page.export_cover_button.width()),1)
        self.assertNotIn('方形裁剪…',[item.text() for item in page.findChildren(QPushButton)])
        self.assertLessEqual(abs(page.match_toggle.geometry().right()-page.match_header.contentsRect().right()),1)
        self.assertEqual(page.lyrics.height(),page.cover.height())
        self.assertGreaterEqual(page.lyrics.height(),130)
        self.assertEqual(page.lyric_actions.mapTo(page,QPoint(0,0)).y(),page.cover_actions.mapTo(page,QPoint(0,0)).y())
        lyric_y=page.import_lyrics_button.mapTo(page,QPoint(0,0)).y();cover_y=page.import_cover_button.mapTo(page,QPoint(0,0)).y()
        self.assertLessEqual(abs(lyric_y-cover_y),1)
        page.scroll.verticalScrollBar().setValue(page.scroll.verticalScrollBar().maximum());self.qt.processEvents()
        footer_top=page.footer.mapTo(self.window,page.footer.rect().topLeft()).y()
        for action in actions:self.assertLess(action.mapTo(self.window,action.rect().bottomRight()).y(),footer_top)
        self.assertEqual(page.cover.objectName(),'coverPreview')
        self.assertTrue(page.footer.isAncestorOf(page.output));self.assertTrue(page.output.isVisible())
        output_bottom=page.output.mapTo(self.window,page.output.rect().bottomRight())
        self.assertTrue(self.window.rect().contains(output_bottom))
        self.assertEqual(page.match_card.layout().contentsMargins().top(),8)
        self.assertEqual(page.match_card.layout().contentsMargins().bottom(),8)
        match_y=page.match_card.mapTo(page,QPoint(0,0)).y();editor_y=page.editor.mapTo(page,QPoint(0,0)).y()
        self.assertGreater(match_y,editor_y)
        page.toggle_matches();self.assertTrue(page.match_content.isVisible());self.assertEqual(page.match_toggle.text(),'收起匹配区域')
    def test_crop_maps_pixel_coordinates(self):
        source=self.base/'cover.png';Image.new('RGB',(90,60),'red').save(source)
        dialog=CropDialog(source,self.window);dialog.show();self.qt.processEvents()
        dialog.width.setValue(35);dialog.height.setValue(25);dialog.x.setValue(50);dialog.y.setValue(20)
        self.assertEqual(dialog.cropped().size,(35,25))
        dialog.reset_selection();self.assertEqual(dialog.cropped().size,(90,60));dialog.close()
    def test_importing_cover_opens_crop_and_cancel_keeps_current_cover(self):
        page=self.window.pages['editor'];source=self.base/'new-cover.png';Image.new('RGB',(90,60),'red').save(source)
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=(str(source),'')),patch('mediaanvil_qt.metadata.CropDialog') as crop:
            crop.return_value.exec.return_value=1;crop.return_value.cropped.return_value=Image.new('RGB',(40,25),'blue')
            page.import_cover()
        with Image.open(page.cover_path) as imported_image:self.assertEqual(imported_image.size,(40,25))
        imported=page.cover_path
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=(str(source),'')),patch('mediaanvil_qt.metadata.CropDialog') as crop:
            crop.return_value.exec.return_value=0;page.import_cover()
        self.assertEqual(page.cover_path,imported)
    def test_cover_preview_expands_and_matching_results_can_be_cleared(self):
        page=self.window.pages['editor'];self.window.navigation.setCurrentRow(self.window.keys.index('editor'))
        source=self.base/'wide-cover.png';Image.new('RGB',(800,500),'red').save(source);page.set_cover(source);self.qt.processEvents()
        self.assertGreater(page.cover.pixmap().width(),170)
        match=type('Match',(),{'audio':self.base/'track.mp3','lyric_candidates':(), 'cover_candidates':()})()
        page.scanned([match]);self.assertEqual(page.matches.rowCount(),1);self.assertTrue(page.clear_matches_button.isEnabled())
        page.clear_matches();self.assertEqual(page.matches.rowCount(),0);self.assertFalse(page.clear_matches_button.isEnabled());self.assertEqual(page.match_rows,[])
    def test_import_failure_explains_unsupported_and_missing_files(self):
        from mediaanvil_qt.services import explain_rejected
        page=self.window.pages['audio']
        extensions=page.files.extensions
        wrong=self.base/'notes.txt';wrong.write_text('x',encoding='utf-8')
        detail=explain_rejected([wrong],extensions)
        self.assertEqual(detail['unsupported'],{'.txt':1})
        self.assertEqual(detail['missing'],())
        message=self.window.import_failure_reason([wrong],extensions,False)
        self.assertIn('.txt',message)
        self.assertIn('不支持',message)
        self.assertIn('*.mp3',message)
        absent=self.base/'ghost.mp3'
        missing=self.window.import_failure_reason([absent],extensions,False)
        self.assertIn('不存在或无法访问',missing)
        self.assertIn('ghost.mp3',missing)
        self.assertIn('没有找到当前页面支持的文件',self.window.import_failure_reason([],extensions,False))
        folder=self.base/'mixed';folder.mkdir()
        (folder/'a.txt').write_text('x',encoding='utf-8');(folder/'b.png').write_text('x',encoding='utf-8')
        recursive=self.window.import_failure_reason([folder],extensions,True)
        self.assertIn('.txt',recursive);self.assertIn('.png',recursive)

    def test_expanding_match_area_reveals_it_on_a_long_page(self):
        page=self.window.pages['editor'];self.window.navigation.setCurrentRow(self.window.keys.index('editor'))
        self.window.resize(1000,560)
        for _ in range(3):self.qt.processEvents()
        self.assertFalse(page.match_content.isVisible())
        page.toggle_matches()
        for _ in range(4):self.qt.processEvents()
        self.assertTrue(page.match_content.isVisible())
        self.assertEqual(page.match_toggle.text(),'收起匹配区域')
        bar=page.scroll.verticalScrollBar()
        if bar.maximum()>0:
            self.assertGreater(bar.value(),0,'expanding should scroll the matching area into view')
        page.toggle_matches()
        self.assertFalse(page.match_content.isVisible())
        self.assertEqual(page.match_toggle.text(),'展开匹配区域')

    def test_task_log_records_counts_only_without_media_content(self):
        from core.task_log import read_entries, record_task
        directory=self.base/'logs'
        record_task('convert:audio',3,2,('转换失败：不支持的编码',),directory=directory)
        record_task('convert:image',1,1,(),directory=directory)
        entries=read_entries(directory)
        self.assertEqual(len(entries),2)
        first,second=entries
        self.assertEqual((first['task'],first['inputs'],first['succeeded'],first['failed']),(('convert:audio'),3,2,1))
        self.assertEqual(first['reasons'],['转换失败：不支持的编码'])
        self.assertEqual(second['failed'],0)
        raw=(directory/'tasks.log').read_text(encoding='utf-8')
        for secret in ('歌词正文','/music/private-song.mp3','sample-tone'):
            self.assertNotIn(secret,raw)
        self.assertEqual(set(first),{'time','task','inputs','succeeded','failed','reasons'})

    def test_task_log_rotates_and_never_grows_without_bound(self):
        from core.task_log import BACKUP_COUNT, LOG_FILE_NAME, record_task
        directory=self.base/'rotating'
        for index in range(40):
            record_task('convert:audio',1,1,(f'原因{index}'.ljust(200,'x'),),directory=directory,maximum=512)
        files=sorted(directory.glob(f'{LOG_FILE_NAME}*'))
        self.assertLessEqual(len(files),BACKUP_COUNT)
        for path in files:
            self.assertLessEqual(path.stat().st_size,512+400,path.name)

    def test_task_log_failure_never_breaks_a_task(self):
        from core.task_log import record_task
        blocked=self.base/'not-a-directory';blocked.write_text('x',encoding='utf-8')
        self.assertIsNone(record_task('convert:audio',1,1,(),directory=blocked))

    def test_conversion_writes_a_log_entry_without_media_content(self):
        from core.task_log import read_entries
        source=self.base/'log-source.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*800)
        page=self.window.pages['audio'];page.receive([source]);page.start();self.wait()
        entries=read_entries(self.window.log_directory())
        self.assertTrue(entries)
        entry=entries[-1]
        self.assertEqual(entry['task'],'convert:audio')
        self.assertEqual(entry['inputs'],1)
        self.assertEqual(entry['succeeded'],1)
        raw=(self.window.log_directory()/'tasks.log').read_text(encoding='utf-8')
        self.assertNotIn('log-source',raw)

    def test_preview_reports_a_file_that_was_moved_or_deleted(self):
        page=self.window.pages['preview']
        source=self.base/'vanishing.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*800)
        page.receive([source]);self.wait()
        self.assertEqual(Path(page.path),source)
        player=page.player;player.pause=MagicMock()
        page.timer.stop()          # drive the check deterministically, not from the timer
        page._ticks=0;page._missing_reported=False
        source.unlink()
        for _ in range(26):page.check_loaded_file()
        player.pause.assert_called_once()
        self.assertIn('移动或删除',page.status.text())
        for _ in range(26):page.check_loaded_file()
        self.assertEqual(player.pause.call_count,1,'the warning must be reported once only')

    def test_open_log_directory_creates_and_reveals_the_folder(self):
        with patch.object(self.window,'open_path') as opened:
            self.window.open_log_directory()
        directory=self.window.log_directory()
        self.assertTrue(directory.is_dir())
        opened.assert_called_once_with(directory)
        self.assertIn('已打开日志目录',self.window.statusBar().currentMessage())

    def test_timeout_error_names_the_input_file_and_stage(self):
        from sub2lrc.audio_converter import AudioConversionError, AudioConversionSettings, convert_audio
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'slow-track.wav';source.write_bytes(b'wav')
            ffmpeg=root/'ffmpeg.exe';ffmpeg.write_bytes(b'fake')
            def popen(command,**_kwargs):
                Path(command[-1]).write_bytes(b'partial')
                from tests.test_audio_converter import FakeProcess
                return FakeProcess(command)
            with patch('sub2lrc.audio_converter._duration_seconds',return_value=None),patch('sub2lrc.audio_converter.subprocess.Popen',side_effect=popen):
                with self.assertRaises(AudioConversionError) as caught:
                    convert_audio(source,root,AudioConversionSettings('mp3'),ffmpeg_path=ffmpeg,timeout_seconds=0)
            message=str(caught.exception)
            self.assertIn('slow-track.wav',message)
            self.assertIn('MP3',message)
            self.assertIn('转换超时',message)

    def test_file_filter_memory_reorders_the_dialog_list(self):
        from mediaanvil_qt.common import dialog_filters, remember_dialog_filter
        supported='支持的文件 (*.mp3 *.wav)'
        every='所有文件 (*)'
        settings=self.window.settings
        settings['last_audio_filter']=''
        self.assertEqual(dialog_filters(self.window,'audio',(supported,every)),f'{supported};;{every}')
        remember_dialog_filter(self.window,'audio',every)
        self.assertEqual(settings['last_audio_filter'],every)
        self.assertEqual(dialog_filters(self.window,'audio',(supported,every)),f'{every};;{supported}')
        remember_dialog_filter(self.window,'audio',supported)
        self.assertEqual(dialog_filters(self.window,'audio',(supported,every)),f'{supported};;{every}')
        # a single-filter dialog stays untouched, and unknown filters are ignored
        self.assertEqual(dialog_filters(self.window,'output',(supported,)),supported)
        settings['last_audio_filter']='已经不存在的筛选器 (*)'
        self.assertEqual(dialog_filters(self.window,'audio',(supported,every)),f'{supported};;{every}')
        remember_dialog_filter(self.window,'audio','')
        self.assertEqual(settings['last_audio_filter'],'已经不存在的筛选器 (*)')

    def test_open_dialogs_pass_two_filters_and_remember_the_choice(self):
        first=self.base/'audio-a';first.mkdir();second=self.base/'audio-b';second.mkdir()
        selected=second/'track.mp3';selected.touch()
        self.window.settings['last_audio_directory']=str(first)
        self.window.settings['last_audio_filter']=''
        page=self.window.pages['preview']
        with patch.object(page,'receive') as receive,patch('mediaanvil_qt.preview.QFileDialog.getOpenFileNames',return_value=([str(selected)],'所有文件 (*)')) as choose:
            page.choose()
        filters=choose.call_args.args[3]
        self.assertIn(';;',filters,'the dialog must offer more than one filter')
        self.assertTrue(filters.startswith('音频 ('),filters)
        self.assertEqual(self.window.settings['last_audio_filter'],'所有文件 (*)')
        self.assertEqual(self.window.settings['last_audio_directory'],str(second.resolve()))
        receive.assert_called_once_with([selected])
        with patch.object(page,'receive'),patch('mediaanvil_qt.preview.QFileDialog.getOpenFileNames',return_value=([],'')) as choose:
            page.choose()
        self.assertTrue(choose.call_args.args[3].startswith('所有文件 (*)'),choose.call_args.args[3])
        editor=self.window.pages['editor']
        with patch('mediaanvil_qt.metadata.QFileDialog.getOpenFileName',return_value=('','')) as choose:
            editor.import_cover()
        self.assertIn(';;',choose.call_args.args[3])
        self.assertIn('图片 (',choose.call_args.args[3])

    def test_output_directory_is_checked_before_a_conversion_starts(self):
        from mediaanvil_qt.services import output_directory_problem
        blank=self.base/'folder-not-created'
        self.assertIn('不存在',output_directory_problem(str(blank)))
        file_as_dir=self.base/'a-file.txt';file_as_dir.write_text('x',encoding='utf-8')
        self.assertIn('不是一个文件夹',output_directory_problem(str(file_as_dir)))
        self.assertIsNone(output_directory_problem(''))
        self.assertIsNone(output_directory_problem(str(self.base)))
        self.assertEqual([p.name for p in self.base.glob('.mediaanvil-write-*')],[])

    def test_conversion_refuses_an_unwritable_output_directory(self):
        page=self.window.pages['audio']
        source=self.base/'guard.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*800)
        page.receive([source])
        page.output.edit.setText(str(self.base/'missing-output'))
        page.start()
        self.assertEqual(self.messages[-1],'输出目录不存在或无法访问。')
        self.assertIsNone(self.window._worker,'no worker may start for a bad output folder')
        self.assertEqual(page.records,[])
        page.output.edit.setText('')
        page.start();self.wait()
        self.assertEqual(len(page.last_outputs),1)

    def test_long_lyric_lists_stay_responsive(self):
        from sub2lrc.audio_preview import LyricLine
        page=self.window.pages['preview']
        class FakePlayer:
            duration=1000.0;position=0.0;state=None
            def set_volume(self,value):pass
            def close(self):pass
        timeline=tuple(LyricLine(i*0.2,f'line {i} lyric text',i) for i in range(5000))
        started=time.perf_counter()
        page.loaded((self.base/'long.mp3',FakePlayer(),('embedded',timeline),None))
        load_seconds=time.perf_counter()-started
        self.assertEqual(page.lyrics.count(),5002)
        self.assertLess(load_seconds,3.0,f'loading 5000 lyric lines took {load_seconds:.2f}s')
        started=time.perf_counter()
        for _ in range(200):page.update_display(100.0)
        self.assertLess(time.perf_counter()-started,2.0)
        self.assertEqual(page.active_line,500)

    def test_scrolled_content_is_never_hidden_behind_the_fixed_footer(self):
        """The footer sits outside the scroll area, so it cannot cover content."""
        for width,height in ((1440,900),(1100,700),(900,640),(760,480)):
            self.window.resize(width,height)
            for index in range(len(self.window.keys)):
                self.window.navigation.setCurrentRow(index)
                for _ in range(4):self.qt.processEvents()
                key=self.window.keys[index]
                page=self.window.pages[key]
                scroll=getattr(page,'scroll',None)
                if scroll is None or not hasattr(page,'footer'):continue
                # the footer must be a sibling of the scroll area, not inside it
                self.assertIs(page.footer.parent(),scroll.parent(),key)
                footer_top=page.footer.mapTo(self.window,page.footer.rect().topLeft()).y()
                scroll_bottom=scroll.mapTo(self.window,scroll.rect().bottomLeft()).y()
                self.assertLessEqual(scroll_bottom,footer_top+1,f'{key} at {width}x{height}')
                bar=scroll.verticalScrollBar();bar.setValue(bar.maximum())
                for _ in range(2):self.qt.processEvents()
                footer_top=page.footer.mapTo(self.window,page.footer.rect().topLeft()).y()
                scroll_bottom=scroll.mapTo(self.window,scroll.rect().bottomLeft()).y()
                self.assertLessEqual(scroll_bottom,footer_top+1,f'{key} scrolled at {width}x{height}')

    def test_switching_pages_returns_to_the_top(self):
        page=self.window.pages['editor']
        self.window.resize(900,600)
        self.window.navigation.setCurrentRow(self.window.keys.index('editor'))
        for _ in range(4):self.qt.processEvents()
        bar=page.scroll.verticalScrollBar()
        if bar.maximum()>0:bar.setValue(bar.maximum())
        self.window.navigation.setCurrentRow(self.window.keys.index('preview'))
        for _ in range(3):self.qt.processEvents()
        self.window.navigation.setCurrentRow(self.window.keys.index('editor'))
        for _ in range(3):self.qt.processEvents()
        self.assertEqual(page.scroll.verticalScrollBar().value(),0)

    def test_error_dialogs_offer_copyable_details(self):
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox,'exec',return_value=0) as run:
            box=self.window.show_message('MediaAnvil Qt','处理失败：详细原因')
        self.assertTrue(run.called)
        labels=[button.text() for button in box.buttons()]
        self.assertIn('复制详情',labels)
        self.assertIn('确定',labels)
        # the copy button copies the full technical detail text
        copy_button=next(button for button in box.buttons() if button.text()=='复制详情')
        copy_button.click()
        self.assertEqual(self.qt.clipboard().text(),'处理失败：详细原因')
        self.window.settings['language']='en_US'
        with patch.object(QMessageBox,'exec',return_value=0):
            english=self.window.show_message('MediaAnvil Qt','Task failed: details')
        self.assertIn('Copy Details',[button.text() for button in english.buttons()])
        self.assertIn('OK',[button.text() for button in english.buttons()])
        self.window.settings['language']='zh_CN'

    def test_settings_numeric_controls_share_one_aligned_width(self):
        groups=(('subtitle_final_duration','default_volume'),
                ('default_image_quality','default_webp_quality'),
                ('default_mp3_bitrate','default_aac_bitrate'))
        for width,height in ((1440,960),(1280,800),(1100,700)):
            self.window.resize(width,height)
            self.window.navigation.setCurrentRow(self.window.keys.index('settings'))
            for _ in range(6):self.qt.processEvents()
            page=self.window.pages['settings']
            for group in groups:
                controls=[page.controls[key] for key in group]
                widths={control.width() for control in controls}
                self.assertEqual(len(widths),1,f'{group} at {width}x{height}: {sorted(widths)}')
                rights={control.mapTo(page,QPoint(control.width(),0)).x() for control in controls}
                self.assertEqual(len(rights),1,f'{group} at {width}x{height} right edges: {sorted(rights)}')
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0,f'{width}x{height}')
        page=self.window.pages['settings']
        duration=page.controls['subtitle_final_duration'];volume=page.controls['default_volume']
        self.assertEqual(duration.width(),volume.width())
        self.assertEqual(duration.width(),135)

    def test_settings_controls_shrink_instead_of_scrolling_when_narrow(self):
        groups=(('subtitle_final_duration','default_volume'),
                ('default_image_quality','default_webp_quality'))
        for width,height in ((900,640),(760,480)):
            self.window.resize(width,height)
            self.window.navigation.setCurrentRow(self.window.keys.index('settings'))
            for _ in range(6):self.qt.processEvents()
            page=self.window.pages['settings']
            for group in groups:
                controls=[page.controls[key] for key in group]
                rights={control.mapTo(page,QPoint(control.width(),0)).x() for control in controls}
                self.assertEqual(len(rights),1,f'{group} at {width}x{height} right edges: {sorted(rights)}')
                self.assertLessEqual(max(control.width() for control in controls),135)
        self.window.resize(900,640)
        self.window.navigation.setCurrentRow(self.window.keys.index('settings'))
        for _ in range(6):self.qt.processEvents()
        self.assertEqual(self.window.pages['settings'].scroll.horizontalScrollBar().maximum(),0)

    def test_settings_persist_and_apply(self):
        page=self.window.pages['settings'];page.controls['default_mp3_bitrate'].setCurrentIndex(3);page.save()
        self.assertEqual(self.window.pages['audio'].parameter.currentData(),320)
        self.assertTrue((self.base/'settings.json').exists())
    def test_language_can_switch_live_and_persists(self):
        page=self.window.pages['settings'];language=page.controls['language']
        language.setCurrentIndex(language.findData('en_US'));page.save();self.qt.processEvents()
        self.assertEqual(self.window.settings['language'],'en_US')
        self.assertEqual(self.window.windowTitle(),'MediaAnvil Qt — Multimedia Toolbox')
        self.assertEqual(self.window.navigation.buttons[0].text(),'Audio Preview')
        self.assertEqual(self.window.navigation.buttons[6].text(),'Settings')
        self.assertEqual(page.language.currentText(),'English')
        self.assertEqual(self.window.pages['preview'].lyrics.item(0).text(),'Synced lyrics will appear here after selecting audio')
        self.assertEqual(self.window.pages['subtitle'].files.empty_hint,'Supports .lrc, .srt and .vtt subtitle files')
        self.assertEqual(self.window.pages['audio'].files.empty_hint,'Supports .mp3, .wav, .flac, .m4a, .aac and .ogg audio files')
        self.assertEqual(self.window.pages['image'].files.empty_hint,'Supports .jpg, .jpeg, .png, .webp and .bmp image files')
        for key in ('subtitle','audio','image'):
            self.assertEqual(self.window.pages[key].result_picker.placeholderText(),'Select a conversion result')
        untranslated=[]
        for key,page_widget in self.window.pages.items():
            for widget in [page_widget,*page_widget.findChildren(QWidget)]:
                values=[]
                if isinstance(widget,(QLabel,QAbstractButton)):values.append(widget.text())
                if isinstance(widget,(QLineEdit,QPlainTextEdit)):values.append(widget.placeholderText())
                if isinstance(widget,QComboBox):
                    values.append(widget.placeholderText());values.extend(widget.itemText(i) for i in range(widget.count()))
                if isinstance(widget,QTableWidget):
                    values.extend(widget.horizontalHeaderItem(i).text() for i in range(widget.columnCount()) if widget.horizontalHeaderItem(i))
                if isinstance(widget,QListWidget):values.extend(widget.item(i).text() for i in range(widget.count()))
                values.extend((widget.toolTip(),getattr(widget,'empty_title',''),getattr(widget,'empty_hint','')))
                untranslated.extend((key,value) for value in values if value and re.search(r'[\u3400-\u9fff]',value))
        self.assertEqual(untranslated,[])
        source=self.base/'language-crop.png';Image.new('RGB',(320,180),'navy').save(source)
        crop=CropDialog(source,self.window.pages['editor'])
        self.assertEqual(crop.windowTitle(),'Free Crop Artwork');crop.close()
        self.window.navigation.setCurrentRow(self.window.keys.index('settings'))
        for _ in range(4):self.qt.processEvents()
        for control in (page.controls['default_output_location'],page.controls['default_save_mode'],page.language):
            self.assertLess(control.fontMetrics().horizontalAdvance(control.currentText()),control.width()-34,control.currentText())
        for section in (page.sections[1],page.sections[2],page.sections[3]):
            for unit in (label for label in section.findChildren(QLabel) if label.text() in ('kbps','s','%')):
                self.assertTrue(section.rect().contains(unit.mapTo(section,unit.rect().bottomRight())),unit.text())
        other=MainWindow(self.base/'settings.json');other.show();self.qt.processEvents()
        self.assertEqual(other.settings['language'],'en_US')
        self.assertEqual(other.navigation.buttons[5].text(),'Batch Rename')
        other.close();self.qt.processEvents()
        language.setCurrentIndex(language.findData('zh_CN'));page.save();self.qt.processEvents()
        self.assertEqual(self.window.navigation.buttons[0].text(),'音频预览')
    def test_rename_plan_invalidated_when_template_changes(self):
        page=self.window.pages['renamer'];page.plan=object();page.execute_button.setEnabled(True);page.template.setCurrentText('{title}')
        self.assertIsNone(page.plan);self.assertFalse(page.execute_button.isEnabled())

    def test_rename_page_matches_responsive_conversion_layout(self):
        self.window.resize(1200,720);self.window.navigation.setCurrentRow(self.window.keys.index('renamer'))
        for _ in range(4):self.qt.processEvents()
        page=self.window.pages['renamer'];buttons=page.toolbar.findChildren(QPushButton)
        expected_labels=['添加文件','移除','清空'] if page._roomy else ['添加…','移除','清空']
        self.assertEqual([button.text() for button in buttons],expected_labels)
        self.assertNotIn('文件夹',''.join(button.text() for button in buttons))
        self.assertLessEqual(max(button.width() for button in buttons)-min(button.width() for button in buttons),1)
        self.assertLessEqual(abs(page.toolbar.width()-page.files.width()),1)
        self.assertEqual(page.files.height(),170 if page._roomy else 28)
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0)
        expected_direction=(page.columns.box.Direction.LeftToRight if page.columns.width()>=page.columns.breakpoint
                            else page.columns.box.Direction.TopToBottom)
        self.assertEqual(page.columns.box.direction(),expected_direction)
        if page._roomy:
            self.assertEqual(page.scroll.verticalScrollBar().maximum(),0)
            left_bottom=page.step_cards[1].mapTo(page,page.step_cards[1].rect().bottomRight()).y()
            right_bottom=page.step_cards[2].mapTo(page,page.step_cards[2].rect().bottomRight()).y()
            self.assertLessEqual(abs(left_bottom-right_bottom),1)
    def test_slider_click_seeks_to_clicked_position(self):
        page=self.window.pages['preview'];slider=page.position;self.assertGreaterEqual(slider.minimumHeight(),24);self.assertGreaterEqual(page.volume.minimumHeight(),24);slider.setRange(0,10000);slider.setValue(0)
        released=[];slider.sliderReleased.connect(lambda:released.append(slider.value()))
        QTest.mouseClick(slider,Qt.MouseButton.LeftButton,pos=QPoint(slider.width()//2,slider.height()//2))
        self.assertTrue(released);self.assertAlmostEqual(released[-1],5000,delta=200)
    def test_native_file_drop_routes_to_current_page(self):
        source=self.base/'drop.lrc';source.write_text('[00:01]drop')
        self.window.navigation.setCurrentRow(self.window.keys.index('subtitle'));self.qt.processEvents()
        mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(source))])
        enter=QDragEnterEvent(QPoint(400,200),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.window,enter);self.assertTrue(enter.isAccepted())
        event=QDropEvent(QPointF(400,200),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.window,event);self.wait()
        self.assertEqual(self.window.pages['subtitle'].files.paths(),(source,))
    def test_audio_metadata_save_as_then_rename_and_undo(self):
        source=self.base/'sample.wav'
        with wave.open(str(source),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(8000);out.writeframes(b'\0\0'*4000)
        outputs,lines=convert_files('audio',[source],'',AudioConversionSettings('mp3',128),lambda *args:None)
        self.assertEqual(len(outputs),1,lines);mp3=outputs[0];original=mp3.read_bytes()
        page=self.window.pages['editor'];page.load(mp3);self.wait();page.title.setText('新歌');page.artist.setText('歌手')
        lyric=self.base/'words.lrc';lyric.write_text('[00:00.10]歌词测试',encoding='utf8');page.set_lyrics(lyric)
        cover=self.base/'cover.webp';Image.new('RGB',(12,18),'blue').save(cover);page.set_cover(cover)
        page.save();self.wait()
        saved=read_metadata(page.path)
        self.assertEqual(mp3.read_bytes(),original);self.assertEqual(saved.title,'新歌')
        self.assertTrue(saved.has_cover);self.assertIn('歌词测试',saved.lyrics)
        export=self.base/'export';export.mkdir()
        with patch('mediaanvil_qt.metadata.QFileDialog.getExistingDirectory',return_value=str(export)):
            page.export('lyrics');self.wait();page.export('cover');self.wait()
        self.assertEqual(len(list(export.glob('*.lrc'))),1);self.assertEqual(len(list(export.glob('*.png'))),1)
        rename=self.window.pages['renamer'];rename.receive([page.path]);rename.preview();self.wait();self.assertEqual(rename.plan.ready_count,1)
        old=page.path;rename.execute();self.wait();self.assertFalse(old.exists());self.assertTrue(rename.records[0].new_path.exists())
        rename.undo();self.wait();self.assertTrue(old.exists());self.assertFalse(rename.records)
    def test_metadata_editor_imports_srt_and_vtt_as_embedded_lrc(self):
        page=self.window.pages['editor']
        for suffix,timing in (('.srt','00:00:01,000 --> 00:00:02,000'),('.vtt','00:00:03.000 --> 00:00:04.000')):
            source=self.base/f'lyrics{suffix}';header='WEBVTT\n\n' if suffix=='.vtt' else '1\n'
            source.write_text(f'{header}{timing}\n第一行\n第二行\n',encoding='utf-8')
            page.set_lyrics(source)
            self.assertEqual(page.lyric_path.suffix,'.lrc');self.assertIn('第一行',page.lyrics.toPlainText())
            self.assertIn('[00:',page.lyrics.toPlainText());self.assertEqual(source.read_text(encoding='utf-8'),f'{header}{timing}\n第一行\n第二行\n')
    def test_preview_load_and_lyric_seek(self):
        source=self.base/'play.wav'
        with wave.open(str(source),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(8000);out.writeframes(b'\0\0'*16000)
        source.with_suffix('.lrc').write_text('[00:00.10]第一句\n[00:01.00]第二句',encoding='utf8')
        page=self.window.pages['preview'];page.load(source);self.wait();self.assertEqual(len(page.timeline),2)
        page.lyric_clicked(page.lyrics.item(2));self.assertAlmostEqual(page.player.position,1,places=1)
    def test_checked_conversion_and_result_preview_include_failures(self):
        good=self.base/'good.srt';good.write_text('1\n00:00:01,000 --> 00:00:02,000\n结果预览\n',encoding='utf8')
        bad=self.base/'bad.srt';bad.write_text('invalid subtitle',encoding='utf8')
        page=self.window.pages['subtitle'];page.receive([good,bad]);page.files.item(1).setCheckState(Qt.CheckState.Unchecked)
        page.start();self.wait();self.assertEqual(len(page.records),1);self.assertIn('结果预览',page.results.toPlainText())
        page.check_all(True);page.start();self.wait();self.assertEqual(len(page.records),2)
        self.assertIsNone(page.records[1]['path']);page.result_picker.setCurrentIndex(1);self.assertIn('失败',page.results.toPlainText())
    def test_image_result_details_save_as_and_reconvert(self):
        source=self.base/'picture.png';Image.new('RGB',(31,47),'blue').save(source)
        page=self.window.pages['image'];page.receive([source]);page.start();self.wait()
        self.assertEqual(page.records[0]['dimensions'],'31 × 47');self.assertGreater(page.records[0]['size'],0)
        first=page.last_outputs[0];destination=self.base/'copied.jpg'
        with patch('mediaanvil_qt.conversion.QFileDialog.getSaveFileName',return_value=(str(destination),'JPG')):
            page.save_result();self.wait()
        self.assertEqual(first.read_bytes(),destination.read_bytes())
        with patch.object(self.window,'open_path') as opened:page.open_output();opened.assert_called_once_with(first.parent)
        page.reconvert();self.wait();self.assertNotEqual(page.last_outputs[0],first);self.assertTrue(first.exists())
    def test_rename_checked_subset_search_and_csv_export(self):
        from core.audio_renamer import RenamePlan,RenamePlanItem
        source1=self.base/'first.mp3';source2=self.base/'second.mp3';source1.write_bytes(b'one');source2.write_bytes(b'two')
        page=self.window.pages['renamer'];page.receive([source1,source2])
        plan=RenamePlan(tuple(RenamePlanItem(p,p.name,p.with_stem(p.stem+'-new'),p.stem+'-new.mp3','可重命名') for p in (source1,source2)),'{title}')
        page.previewed(plan);page.table.item(1,0).setCheckState(Qt.CheckState.Unchecked)
        page.search.setText('second');self.assertTrue(page.table.isRowHidden(0));self.assertFalse(page.table.isRowHidden(1))
        output=self.base/'preview.csv'
        with patch('mediaanvil_qt.rename.QFileDialog.getSaveFileName',return_value=(str(output),'CSV')):
            page.export_preview();self.wait()
        self.assertIn('first-new.mp3',output.read_text(encoding='utf-8-sig'))
        page.execute();self.wait();self.assertFalse(source1.exists());self.assertTrue(source2.exists())
        page.undo();self.wait();self.assertEqual(source1.read_bytes(),b'one');self.assertEqual(source2.read_bytes(),b'two')
    def test_playback_controls_are_centered_and_skip_thirty_seconds(self):
        page=self.window.pages['preview'];player=MagicMock();player.position=45;player.duration=60;page.player=player
        page.jump_by(-30);player.seek.assert_called_once_with(15)
        player.seek.reset_mock();page.jump_by(30);player.seek.assert_called_once_with(60)
        self.assertEqual(page.skip_back.text(),'');self.assertEqual(page.skip_forward.text(),'')
        controls=page.skip_back.parentWidget().layout()
        self.assertEqual(controls.count(),5);self.assertIsNone(controls.itemAt(0).widget());self.assertIsNone(controls.itemAt(4).widget())
    def test_space_starts_freshly_loaded_audio_even_when_sidebar_has_focus(self):
        class Player:
            def __init__(self):self.state=PlaybackState.STOPPED;self.position=0;self.duration=60
            def play(self):self.state=PlaybackState.PLAYING
            def pause(self):self.state=PlaybackState.PAUSED
            def close(self):pass
        page=self.window.pages['preview'];page.player=Player()
        self.window.navigation.buttons[0].setFocus();self.qt.processEvents()
        QTest.keyClick(self.window.navigation.buttons[0],Qt.Key.Key_Space);self.qt.processEvents()
        self.assertEqual(page.player.state,PlaybackState.PLAYING)
        page.player.state=PlaybackState.STOPPED
        self.window.navigation.setCurrentRow(self.window.keys.index('settings'))
        self.window.pages['settings'].language.setFocus();self.qt.processEvents()
        QTest.keyClick(self.window.pages['settings'].language,Qt.Key.Key_Space);self.qt.processEvents()
        self.assertEqual(page.player.state,PlaybackState.STOPPED)
    def test_batch_match_write_kind_excludes_other_media(self):
        from core.media_matcher import MediaMatch
        page=self.window.pages['editor'];audio=self.base/'song.mp3';lyrics=self.base/'song.lrc';cover=self.base/'song.png'
        page.scanned([MediaMatch(audio,(lyrics,),(cover,))])
        with patch('mediaanvil_qt.metadata.write_matches',return_value=['完成']) as write:
            page.batch_write('lyrics');self.wait();self.assertEqual(write.call_args.args[0],((audio,lyrics,None),))
            page.batch_write('cover');self.wait();self.assertEqual(write.call_args.args[0],((audio,None,cover),))
    def test_batch_match_converts_vtt_to_lrc_before_embedding(self):
        audio=self.base/'song.mp3';audio.write_bytes(b'audio')
        subtitle=self.base/'song.mp3.vtt';subtitle.write_text('WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n批量字幕\n',encoding='utf-8')
        captured=[]
        def fake_write(source,changes,target):
            captured.append(changes.lyrics_path.read_text(encoding='utf-8-sig'));return source
        with patch('mediaanvil_qt.services.write_metadata',side_effect=fake_write):
            lines=write_matches(((audio,subtitle,None),),True,'',lambda *args:None)
        self.assertIn('[00:01.00]批量字幕',captured[0]);self.assertIn('完成：',lines[0])

if __name__=='__main__':unittest.main()

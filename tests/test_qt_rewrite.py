import os,time,tempfile,unittest,threading,subprocess,wave,re
from pathlib import Path
from unittest.mock import MagicMock,patch
from PIL import Image
try:
    from PySide6.QtCore import QTimer,Qt,QThread,QPoint,QPointF,QMimeData,QUrl,QSize
    from PySide6.QtWidgets import (QApplication,QPushButton,QSizePolicy,QLabel,QAbstractButton,
        QComboBox,QLineEdit,QPlainTextEdit,QTableWidget,QListWidget,QWidget)
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QDragEnterEvent,QDropEvent,QFontInfo
except ImportError:
    raise unittest.SkipTest('Install requirements-qt.txt to run Qt interface tests')
from mediaanvil_qt.app import MainWindow,default_window_size
from mediaanvil_qt import __version__ as qt_version
from mediaanvil_qt.design import STYLE
from mediaanvil_qt.services import collect_paths,convert_files,tagged_destination,write_matches
from mediaanvil_qt.metadata import CropDialog
from core.settings import save_settings
from sub2lrc.audio_converter import AudioConversionSettings,find_ffmpeg
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
        self.window.show();self.qt.processEvents()
    def tearDown(self):
        self.wait();self.window.close();self.qt.processEvents();self.temp.cleanup()
    def wait(self):
        deadline=time.monotonic()+20
        while self.window._worker and time.monotonic()<deadline:
            self.qt.processEvents();time.sleep(.005)
        self.assertIsNone(self.window._worker,'worker did not complete');self.qt.processEvents()
    def test_pages_preserve_native_window_and_data(self):
        self.assertEqual(qt_version,'1.0.0')
        self.assertIn('v1.0.0',[label.text() for label in self.window.findChildren(QLabel)])
        self.assertEqual(len(self.window.pages),8)
        self.assertEqual((self.window.width(),self.window.height()),default_window_size())
        self.assertFalse(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertIn('QPushButton#navItem { background:transparent; border:0; border-left:2px solid transparent; border-radius:8px; text-align:left; padding:12px 14px; min-height:22px; font-size:15px; font-weight:600; }',STYLE)
        self.assertIn('QSlider:horizontal { padding:0 8px; }',STYLE)
        self.assertIn('QSlider::handle:horizontal { background:white; border:2px solid #397bf3; width:12px; height:12px;',STYLE)
        self.assertFalse(hasattr(self.window.pages['preview'],'open_folder'))
        self.assertIn('使用说明',[button.text() for button in self.window.pages['about'].findChildren(QPushButton)])
        self.window.pages['editor'].title.setText('未保存的草稿')
        for i in range(8):self.window.navigation.setCurrentRow(i);self.qt.processEvents()
        self.assertEqual(self.window.pages['editor'].title.text(),'未保存的草稿')

    def test_default_window_size_adapts_to_available_space(self):
        self.assertEqual(default_window_size(QSize(1536,824),30,1.25),(1152,690))
        self.assertEqual(default_window_size(QSize(1280,680),30,1),(979,582))
        self.assertEqual(default_window_size(QSize(2560,1440),30,1),(1440,870))

    def test_window_starts_at_default_size_in_screen_center(self):
        self.assertEqual((self.window.width(),self.window.height()),default_window_size())
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

    def test_default_window_keeps_conversion_pages_in_two_columns(self):
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key));self.qt.processEvents()
            page=self.window.pages[key]
            self.assertEqual(page.columns.box.direction(),page.columns.box.Direction.LeftToRight,key)
            expected_height={'subtitle':170,'audio':170,'image':160}[key] if page._roomy else 28
            self.assertEqual(page.files.height(),expected_height,key)
            expected_add='添加图片' if page._roomy and key=='image' else '添加文件' if page._roomy else '添加…'
            self.assertEqual([button.text() for button in page.toolbar.findChildren(QPushButton)],[expected_add,'移除','清空'])
            self.assertNotIn('文件夹',''.join(button.text() for button in page.toolbar.findChildren(QPushButton)))
            self.assertLessEqual(page.scroll.verticalScrollBar().maximum(),40,key)
            self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0,key)
        self.window.resize(1200,800);self.qt.processEvents()
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key))
            for _ in range(4):self.qt.processEvents()
            page=self.window.pages[key]
            self.assertFalse(page.source_detail.isVisible(),key)
            self.assertEqual(page.files.height(),{'subtitle':170,'audio':170,'image':160}[key],key)
            self.assertEqual(page.scroll.verticalScrollBar().maximum(),0,key)
            toolbar_buttons=page.toolbar.findChildren(QPushButton)
            self.assertLessEqual(max(button.width() for button in toolbar_buttons)-min(button.width() for button in toolbar_buttons),1,key)
            self.assertLessEqual(abs(page.toolbar.width()-page.files.width()),1,key)
            self.assertLessEqual(abs(page.select_all.mapTo(page,QPoint(0,0)).y()-page.file_count.mapTo(page,QPoint(0,0)).y()),2,key)
            self.assertLessEqual(abs(page.file_count.mapTo(page.selection_row,page.file_count.rect().topRight()).x()-page.selection_row.contentsRect().right()),1,key)
            left_bottom=page.step_cards[1].mapTo(page,page.step_cards[1].rect().bottomRight()).y()
            right_bottom=page.step_cards[2].mapTo(page,page.step_cards[2].rect().bottomRight()).y()
            self.assertLessEqual(abs(left_bottom-right_bottom),1,key)
        self.window.resize(*default_window_size());
        for _ in range(4):self.qt.processEvents()
        for key in ('subtitle','audio','image'):
            self.window.navigation.setCurrentRow(self.window.keys.index(key))
            for _ in range(4):self.qt.processEvents()
            self.assertLessEqual(self.window.pages[key].scroll.verticalScrollBar().maximum(),40,key)
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

    def test_rename_page_matches_conversion_layout(self):
        self.window.resize(1200,720);self.window.navigation.setCurrentRow(self.window.keys.index('renamer'))
        for _ in range(4):self.qt.processEvents()
        page=self.window.pages['renamer'];buttons=page.toolbar.findChildren(QPushButton)
        self.assertEqual([button.text() for button in buttons],['添加文件','移除','清空'])
        self.assertNotIn('文件夹',''.join(button.text() for button in buttons))
        self.assertLessEqual(max(button.width() for button in buttons)-min(button.width() for button in buttons),1)
        self.assertLessEqual(abs(page.toolbar.width()-page.files.width()),1)
        self.assertEqual(page.files.height(),170)
        self.assertEqual(page.scroll.horizontalScrollBar().maximum(),0)
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

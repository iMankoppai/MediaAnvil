"""User-visible upgrade workflows, using generated scratch media only."""
import csv
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from core.tasks import TaskHistory, TaskRecord, save_task_histories, load_task_histories
from core.task_reports import export_report
from mediaanvil_qt.app import MainWindow
from mediaanvil_qt.common import fill_table
from core.media_matcher import MediaMatch


class UpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.window=MainWindow(self.base/'settings.json');self.messages=[]
        self.window.inform=lambda message:self.messages.append(str(message))
        self.window.show_text=lambda title,text:self.messages.append(str(text))
        self.release=threading.Event()
    def tearDown(self):
        self.release.set();self.wait();self.window.close();self.qt.processEvents();self.temp.cleanup()
    def wait(self):
        deadline=time.monotonic()+30
        while (self.window._worker or self.window.pending_tasks or self.window._importing) and time.monotonic()<deadline:
            self.qt.processEvents();time.sleep(.005)
        self.qt.processEvents();self.assertIsNone(self.window._worker);self.assertFalse(self.window.pending_tasks)
    def block(self,report):
        while not self.release.wait(.01):report.raise_if_cancelled()
    def subtitle(self,name):
        path=self.base/(name+'.srt');path.write_text('1\n00:00:01,000 --> 00:00:02,000\n你好\n',encoding='utf8');return path

    def test_queued_conversions_capture_parameters_and_can_reorder_and_cancel(self):
        self.window.run_task(self.block,lambda result:None)
        page=self.window.pages['subtitle']
        first=self.subtitle('first');second=self.subtitle('second');third=self.subtitle('third')
        page.convert_paths([first],{'format':'lrc','duration':5,'output_directory':''})
        page.convert_paths([second],{'format':'vtt','duration':5,'output_directory':''})
        page.convert_paths([third],{'format':'lrc','duration':5,'output_directory':''})
        ids=[j.task_id for j in self.window.pending_tasks]
        self.window.queue_table.selectRow(1);self.window.move_queued_task(-1)
        self.assertEqual([j.task_id for j in self.window.pending_tasks],[ids[1],ids[0],ids[2]])
        self.window.queue_table.selectRow(2);self.window.cancel_queued_task()
        page.format.setCurrentIndex(page.format.findData('srt'))
        self.release.set();self.wait()
        self.assertTrue((self.base/'first.lrc').is_file());self.assertTrue((self.base/'second.vtt').is_file())
        self.assertFalse((self.base/'third.lrc').exists())
        cancelled=next(h for h in self.window.task_histories if h.task_id==ids[2])
        self.assertEqual(cancelled.records[0].state,'已取消')
        self.assertEqual(self.messages,[])

    def test_cancel_active_task_still_runs_next_queued_task(self):
        self.window.run_task(self.block,lambda result:None)
        source=self.subtitle('next');self.window.pages['subtitle'].convert_paths([source])
        self.window.cancel_task();self.wait()
        self.assertTrue((self.base/'next.lrc').exists())

    def test_pending_jobs_survive_history_retention_and_restart_as_interrupted(self):
        pending=TaskHistory('audio',(TaskRecord(self.base/'pending.wav','排队'),),{'format':'flac'})
        finished=[TaskHistory('audio',(TaskRecord(self.base/f'{i}.wav','已完成'),)) for i in range(25)]
        path=self.base/'history.json';save_task_histories(path,[pending,*finished])
        loaded=load_task_histories(path)
        self.assertEqual(len(loaded),21);self.assertEqual(loaded[0].records[0].state,'已中断')
        self.assertEqual(loaded[0].parameters,{'format':'flac'})

    def test_matching_pages_keep_manual_choices_for_offscreen_files(self):
        page=self.window.pages['editor'];matches=[]
        for i in range(205):
            audio=self.base/f'{i}.mp3';lyric=self.base/f'{i}.lrc'
            matches.append(MediaMatch(audio,(lyric,),()))
        page.scanned(matches);self.assertEqual(page.matches.rowCount(),100)
        page.matches.cellWidget(0,1).setCurrentIndex(0)
        page.match_page.setValue(3);self.assertEqual(page.matches.rowCount(),5)
        page.match_page.setValue(1);self.assertIsNone(page.matches.cellWidget(0,1).currentData())
        with patch.object(page,'submit_batch') as submit:
            page.batch_write()
        self.assertEqual(len(submit.call_args.args[1]),205)
        rows=submit.call_args.args[2]['rows']
        self.assertIsNone(rows[0][1]);self.assertEqual(rows[-1][1],str(matches[-1].lyric_candidates[0]))

    def test_virtual_rename_table_supports_checks_filtering_and_translation(self):
        table=self.window.pages['renamer'].table
        fill_table(table,[('',i,f'{i}.mp3','new.mp3','可重命名') for i in range(10000)])
        table.item(9999,0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(table.rowCount(),10000);self.assertEqual(table.item(9999,0).checkState(),Qt.CheckState.Checked)
        self.window.pages['renamer'].search.setText('9999')
        self.assertTrue(table.isRowHidden(0));self.assertFalse(table.isRowHidden(9999))
        self.window.set_language('en_US')
        self.assertEqual(table.model().headerData(2,Qt.Orientation.Horizontal),'Original Filename')

    def test_organizer_follows_saved_and_renamed_outputs_instead_of_rescanning_originals(self):
        from mediaanvil_qt.organizer import OrganizerDialog
        from core.media_matcher import MediaCheckRow
        source=self.base/'song.mp3';saved=self.base/'song_tagged.mp3';renamed=self.base/'artist-song.mp3'
        flow=OrganizerDialog(self.window);self.window.organizer=flow
        flow.inspected([MediaCheckRow(source,True,True,('title',))])
        flow.follow_outputs(TaskHistory('tags',(TaskRecord(source,'已完成',output=saved),)))
        flow.follow_outputs(TaskHistory('rename',(TaskRecord(saved,'已完成',output=renamed),)))
        self.assertEqual(flow.paths(),(renamed,))
        with patch('mediaanvil_qt.organizer.check_audio_paths',return_value=()) as check:
            flow.recheck();self.wait()
        self.assertEqual(check.call_args.args[0],(renamed,));flow.close()

    def test_exported_report_retains_errors_outputs_and_chinese(self):
        history=TaskHistory('audio',(TaskRecord(Path('=危险.wav'),'失败','文件被占用'),
            TaskRecord(Path('歌曲.wav'),'已完成',output=Path('歌曲.mp3'))))
        path=self.base/'report.csv';export_report(history,path)
        with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
        self.assertEqual(rows[1][2],"'=危险.wav");self.assertEqual(rows[1][4],'文件被占用')
        self.assertEqual(rows[2][5],'歌曲.mp3')

    def test_native_player_controls_keep_one_decoder_and_leave_original_unlocked(self):
        import wave
        from sub2lrc.audio_preview import AudioPreviewPlayer,PlaybackState
        from mediaanvil_qt.player import QtAudioPreviewPlayer,prepare_playback_copy
        from core.tasks import CancellationToken
        from mediaanvil_qt.common import TaskReporter
        from unittest.mock import MagicMock
        source=self.base/'可编辑原文件.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*40000)
        prepared=AudioPreviewPlayer();prepared.load(source);prepared.set_volume(0)
        prepare_playback_copy(prepared,TaskReporter(MagicMock(),CancellationToken()))
        player=QtAudioPreviewPlayer(prepared,self.window)
        try:
            deadline=time.monotonic()+10
            while player.media.duration()==0 and time.monotonic()<deadline:
                self.qt.processEvents();time.sleep(.01)
            self.assertGreater(player.media.duration(),0);self.assertFalse(player.compatibility)
            decoder=player.media
            with patch('sub2lrc.audio_preview.subprocess.Popen') as popen:
                player.play();self.qt.processEvents();player.pause();self.qt.processEvents()
                player.set_volume(35);player.set_speed(1.5);player.seek(2)
                self.qt.processEvents()
                self.assertIs(player.media,decoder);self.assertFalse(player.compatibility)
                self.assertEqual(player.state,PlaybackState.PAUSED)
                self.assertAlmostEqual(player.position,2,delta=.15)
                popen.assert_not_called()
            # Moving the source is possible while the native decoder is loaded.
            renamed=source.with_name('已改名.wav');source.rename(renamed)
            self.assertTrue(renamed.is_file())
        finally:player.close();self.qt.processEvents()

    def test_verification_checks_real_results_including_corrupt_images(self):
        from PIL import Image
        from core.task_reports import verify_outputs
        good=self.base/'good.png';Image.new('RGB',(2,2)).save(good)
        broken=self.base/'broken.png';broken.write_bytes(b'broken')
        missing=self.base/'missing.png'
        history=TaskHistory('image',tuple(TaskRecord(self.base/f'{i}.png','已完成',output=p) for i,p in enumerate((good,broken,missing))))
        records=verify_outputs(history)
        self.assertEqual([r.state for r in records],['已完成','失败','失败'])

    def test_job_submitted_from_completion_waits_for_history_finalization(self):
        from core.tasks import TaskRecord
        order=[]
        def first_done(result,task_id):
            order.append('first')
            self.window.submit_task('audio',[self.base/'two.wav'],{},
                lambda report:report.checkpoint(TaskRecord(self.base/'two.wav','失败','fixture error')),
                lambda result,second_id:order.append('second'))
        first_id=self.window.submit_task('audio',[self.base/'one.wav'],{},lambda report:None,first_done)
        self.wait()
        self.assertEqual(order,['first','second'])
        self.assertEqual(next(h for h in self.window.task_histories if h.task_id==first_id).records[0].state,'已完成')
        self.assertEqual(self.window.task_histories[-1].records[0].state,'失败')

    def test_organizer_repairs_and_renames_real_audio_then_follows_undo(self):
        import wave
        from sub2lrc.audio_converter import convert_audio,AudioConversionSettings
        from sub2lrc.audio_metadata import read_metadata,write_metadata,AudioMetadataChanges
        from core.media_matcher import check_audio_paths
        from mediaanvil_qt.organizer import OrganizerDialog
        wav=self.base/'song.wav'
        with wave.open(str(wav),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*8000)
        source=convert_audio(wav,self.base,AudioConversionSettings('mp3',128))
        write_metadata(source,AudioMetadataChanges(title='Title'))
        original=source.read_bytes();source.with_suffix('.lrc').write_text('[00:00.00]歌词\n',encoding='utf8')
        flow=OrganizerDialog(self.window);self.window.organizer=flow;flow.inspected(check_audio_paths([source]))
        flow.load_repairs();self.wait()
        editor=self.window.pages['editor'];editor.batch_write('lyrics');self.wait()
        with_lyrics=flow.paths()[0]
        self.assertNotEqual(with_lyrics,source);self.assertTrue(read_metadata(with_lyrics).has_lyrics)
        flow.load_repairs();self.wait()
        for key,text in {'artist':'Artist','album':'Album'}.items():editor.batch_values[key].setText(text)
        editor.apply_batch_tags();self.wait();tagged=flow.paths()[0]
        flow.load_rename();self.wait()
        renamer=self.window.pages['renamer'];self.assertIsNotNone(renamer.plan)
        renamer.execute();self.wait();renamed=flow.paths()[0]
        self.assertEqual(renamed.name,'Artist - Title.mp3');self.assertTrue(renamed.is_file())
        renamer.undo();self.wait()
        self.assertEqual(flow.paths(),(tagged,));self.assertTrue(tagged.is_file())
        self.assertEqual(source.read_bytes(),original);flow.close()

    def test_completion_reports_do_not_block_pending_jobs(self):
        from PySide6.QtWidgets import QDialog
        reports=[];completed=[]
        self.window.run_task(self.block,lambda result:None)
        self.window.submit_task('tags',[self.base/'one.mp3'],{},lambda report:None,
            lambda result,task_id:reports.append(MainWindow.show_text(self.window,'结果','已完成')))
        self.window.submit_task('tags',[self.base/'two.mp3'],{},lambda report:None,
            lambda result,task_id:completed.append(task_id))
        with patch.object(QDialog,'exec',return_value=0) as execute:
            self.release.set();self.wait();execute.assert_not_called()
        self.assertEqual(len(completed),1)
        for dialog in reports:dialog.close()

    def test_worker_error_preserves_completed_files_and_records_reason_before_next_job(self):
        first=self.base/'one.wav';second=self.base/'two.wav'
        def work(report):
            report.checkpoint(TaskRecord(first,'已完成',output=self.base/'one.mp3'))
            raise ValueError('文件被占用')
        self.window.run_task(self.block,lambda result:None)
        task_id=self.window.submit_task('audio',[first,second],{},work,lambda result,task_id:None)
        self.window.submit_task('image',[self.base/'next.png'],{},lambda report:None,lambda result,task_id:None)
        self.release.set();self.wait()
        history=next(h for h in self.window.task_histories if h.task_id==task_id)
        self.assertEqual([r.state for r in history.records],['已完成','失败'])
        self.assertEqual(history.records[1].message,'文件被占用')


class FastExportTests(unittest.TestCase):
    def test_fast_export_uses_copy_only_for_compatible_unfiltered_inputs(self):
        from sub2lrc.audio_join import AudioPolish, can_stream_copy
        paths=[Path('one.mp3'),Path('two.mp3')]
        with patch('sub2lrc.audio_join.stream_copy_signature',side_effect=[('mp3','44100 Hz','stereo','fltp')]*2):
            self.assertTrue(can_stream_copy(Path('ffmpeg.exe'),paths,'mp3',AudioPolish()))
        with patch('sub2lrc.audio_join.stream_copy_signature',side_effect=[('mp3','44100 Hz','stereo','fltp'),('mp3','48000 Hz','stereo','fltp')]):
            self.assertFalse(can_stream_copy(Path('ffmpeg.exe'),paths,'mp3',AudioPolish()))
        for polish in (AudioPolish(normalize=True),AudioPolish(fade_seconds=1)):
            self.assertFalse(can_stream_copy(Path('ffmpeg.exe'),paths,'mp3',polish))

    def test_real_wav_fast_split_and_merge_preserve_pcm_samples(self):
        import wave
        import struct
        from sub2lrc.audio_join import split_audio,merge_audio,SplitPlan
        from sub2lrc.audio_converter import find_ffmpeg
        try:find_ffmpeg()
        except ValueError:self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'中文音频.wav'
            samples=b''.join(struct.pack('<h',(i%1000)-500) for i in range(16000))
            with wave.open(str(source),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(samples)
            pieces=split_audio(source,(SplitPlan(0,1),SplitPlan(1,1)),'wav',root,fast=True)
            merged=merge_audio(pieces,'wav',root,fast=True)
            with wave.open(str(merged),'rb') as stream:actual=stream.readframes(stream.getnframes())
            self.assertEqual(actual,samples)
            with wave.open(str(source),'rb') as stream:self.assertEqual(stream.readframes(16000),samples)


if __name__=='__main__':unittest.main()

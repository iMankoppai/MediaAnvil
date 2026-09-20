from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from sub2lrc.audio_preview import (
    AudioPreviewError,
    AudioPreviewPlayer,
    PlaybackState,
    current_lyric_index,
    load_audio_lyrics,
    lyric_index_from_display_line,
    parse_lrc_timeline,
)


class FakeProcess:
    next_pid = 100

    def __init__(self, command: list[str], **_kwargs: object) -> None:
        self.command = command
        self.returncode: int | None = None
        self.pid = FakeProcess.next_pid
        FakeProcess.next_pid += 1
        self._handle = self.pid
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode or 0

    def kill(self) -> None:
        self.returncode = -9


class AudioPreviewTests(unittest.TestCase):
    def test_lrc_timeline_and_current_line_support_multiple_timestamps(self) -> None:
        content = "[ar:歌手]\n[00:01.00][00:02.50]第一句\n[00:05.125]第二句\n"
        timeline = parse_lrc_timeline(content)
        self.assertEqual([line.time_seconds for line in timeline], [1.0, 2.5, 5.125])
        self.assertIsNone(current_lyric_index(timeline, 0.5))
        self.assertEqual(current_lyric_index(timeline, 2.6), 1)
        self.assertEqual(timeline[current_lyric_index(timeline, 6.0) or 0].text, "第二句")
        self.assertEqual(lyric_index_from_display_line(timeline, 2), 1)
        self.assertIsNone(lyric_index_from_display_line(timeline, 99))

    def test_same_name_external_lrc_is_loaded_without_changing_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "中文歌曲.flac"
            audio.write_bytes(b"audio-data")
            before = audio.read_bytes()
            audio.with_suffix(".lrc").write_text("[00:01.00]歌词\n", encoding="utf-8")
            content, timeline = load_audio_lyrics(audio)
            self.assertIn("歌词", content)
            self.assertEqual(timeline[0].time_seconds, 1.0)
            self.assertEqual(audio.read_bytes(), before)

    def test_same_name_srt_and_vtt_are_loaded_directly_with_end_times(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for suffix,header,timing in (
                ('.srt','1\n','00:00:01,000 --> 00:00:02,500'),
                ('.vtt','WEBVTT\n\n','00:00:03.000 --> 00:00:04.500'),
            ):
                audio=root/f'voice-{suffix[1:]}.flac';audio.write_bytes(b'audio')
                audio.with_suffix(suffix).write_text(f'{header}{timing}\n第一行\n第二行\n',encoding='utf-8')
                content,timeline=load_audio_lyrics(audio)
                self.assertIn('第一行',content);self.assertEqual(timeline[0].text,'第一行\n第二行')
                self.assertIsNotNone(timeline[0].end_seconds)
                self.assertIsNone(current_lyric_index(timeline,timeline[0].end_seconds or 0))

    def test_subtitle_name_may_retain_the_audio_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio=Path(directory)/'ex01.平凡日子的掏耳朵.wav';audio.write_bytes(b'audio')
            retained=Path(str(audio)+'.vtt')
            retained.write_text('WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n完整文件名字幕\n',encoding='utf-8')
            content,timeline=load_audio_lyrics(audio)
            self.assertIn('完整文件名字幕',content);self.assertEqual(timeline[0].time_seconds,1.0)

    def test_retained_audio_extension_wins_within_the_same_subtitle_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio=Path(directory)/'song.flac';audio.write_bytes(b'audio')
            audio.with_suffix('.lrc').write_text('[00:01.00]普通同名\n',encoding='utf-8')
            Path(str(audio)+'.lrc').write_text('[00:02.00]完整文件名\n',encoding='utf-8')
            self.assertEqual(load_audio_lyrics(audio)[1][0].text,'完整文件名')

    @patch('sub2lrc.audio_preview.read_embedded_lyrics')
    def test_external_priority_and_embedded_preference_switch(self,embedded) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio=Path(directory)/'song.mp3';audio.write_bytes(b'audio')
            audio.with_suffix('.lrc').write_text('[00:01.00]外置歌词\n',encoding='utf-8')
            audio.with_suffix('.srt').write_text('1\n00:00:02,000 --> 00:00:03,000\n字幕\n',encoding='utf-8')
            embedded.return_value=SimpleNamespace(extension='.lrc',text='[00:04.00]内嵌歌词\n')
            self.assertEqual(load_audio_lyrics(audio)[1][0].text,'外置歌词')
            self.assertEqual(load_audio_lyrics(audio,prefer_embedded=True)[1][0].text,'内嵌歌词')

    def test_external_lrc_can_be_disabled_by_global_setting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "song.flac"
            audio.write_bytes(b"audio-data")
            audio.with_suffix(".lrc").write_text("[00:01.00]外置歌词\n", encoding="utf-8")
            content, timeline = load_audio_lyrics(audio, load_external=False)
            self.assertEqual(content, "")
            self.assertEqual(timeline, ())

    @patch("sub2lrc.audio_preview._duration_seconds", return_value=12.0)
    def test_load_accepts_every_current_audio_format_and_switch_stops_previous(self, _probe: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player = AudioPreviewPlayer(Path(__file__))
            sources: list[Path] = []
            for suffix in (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"):
                source = root / f"音频{suffix}"
                source.write_bytes(b"test")
                sources.append(source)
                self.assertEqual(player.load(source), 12.0)
                self.assertEqual(player.source, source)
            previous_process = FakeProcess(["ffplay"])
            player._process = previous_process
            player.state = PlaybackState.PLAYING
            player.load(sources[0])
            self.assertTrue(previous_process.terminated)

    @patch("sub2lrc.audio_preview._resume_process")
    @patch("sub2lrc.audio_preview._suspend_process")
    @patch("sub2lrc.audio_preview.subprocess.Popen", side_effect=FakeProcess)
    def test_play_pause_seek_volume_and_stop(
        self, popen: object, suspend: object, resume: object
    ) -> None:
        now = [100.0]
        player = AudioPreviewPlayer(Path(__file__), clock=lambda: now[0])
        player.source = Path("song.mp3")
        player.duration = 30.0

        player.play()
        now[0] = 104.0
        self.assertAlmostEqual(player.position, 4.0)
        player.pause()
        self.assertEqual(player.state, PlaybackState.PAUSED)
        now[0] = 110.0
        self.assertAlmostEqual(player.position, 4.0)
        player.play()
        self.assertEqual(player.state, PlaybackState.PLAYING)
        player.seek(20.0)
        self.assertAlmostEqual(player.position, 20.0)
        player.set_volume(35)
        self.assertEqual(player.volume, 35)
        self.assertIn("35", player._process.command)  # type: ignore[union-attr]
        player.stop()
        self.assertEqual((player.state, player.position), (PlaybackState.STOPPED, 0.0))
        self.assertGreaterEqual(popen.call_count, 3)  # type: ignore[attr-defined]
        self.assertTrue(suspend.called)  # type: ignore[attr-defined]
        self.assertTrue(resume.called)  # type: ignore[attr-defined]

    def test_errors_are_clear_and_no_lyrics_is_normal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audio.wav"
            source.write_bytes(b"data")
            content, timeline = load_audio_lyrics(source)
            self.assertEqual((content, timeline), ("", ()))
            player = AudioPreviewPlayer(Path(__file__))
            with self.assertRaisesRegex(AudioPreviewError, "不支持"):
                player.load(source.with_suffix(".xyz"))
            with self.assertRaises(AudioPreviewError):
                player.set_volume(101)


if __name__ == "__main__":
    unittest.main()

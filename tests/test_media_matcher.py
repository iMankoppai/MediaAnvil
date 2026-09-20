from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.media_matcher import MatchPriority, find_associated_files, scan_audio_folder


class MediaMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def touch(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(b"fixture")
        return path

    def test_exact_mp3_lrc_and_jpg_match_wins_over_copy_candidates(self) -> None:
        audio = self.touch("歌曲.mp3")
        exact_lyric = self.touch("歌曲.lrc")
        exact_cover = self.touch("歌曲.jpg")
        self.touch("歌曲(1).jpg")
        result = find_associated_files(audio)
        self.assertEqual(result.lyric, exact_lyric)
        self.assertEqual(result.cover, exact_cover)
        self.assertEqual(result.lyric_priority, MatchPriority.EXACT)
        self.assertEqual(result.cover_priority, MatchPriority.EXACT)

    def test_flac_vtt_png_and_chinese_folder_scan(self) -> None:
        audio = self.touch("夜曲.flac")
        lyric = self.touch("夜曲.vtt")
        cover = self.touch("夜曲.png")
        results = scan_audio_folder(self.root)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].audio, audio)
        self.assertEqual(results[0].lyric, lyric)
        self.assertEqual(results[0].cover, cover)

    def test_double_suffix_lyrics_and_cover_match_the_full_audio_name(self) -> None:
        audio=self.touch('ex01.平凡日子的掏耳朵.wav')
        lyric=self.touch('ex01.平凡日子的掏耳朵.wav.vtt')
        cover=self.touch('ex01.平凡日子的掏耳朵.wav.png')
        result=find_associated_files(audio)
        self.assertEqual(result.lyric,lyric);self.assertEqual(result.cover,cover)
        self.assertEqual(result.lyric_priority,MatchPriority.FULL_AUDIO_NAME)
        self.assertEqual(result.cover_priority,MatchPriority.FULL_AUDIO_NAME)

    def test_double_suffix_candidate_wins_over_conventional_same_format(self) -> None:
        audio=self.touch('song.flac')
        self.touch('song.vtt');specific=self.touch('song.flac.vtt')
        self.touch('song.png');specific_cover=self.touch('song.flac.png')
        result=find_associated_files(audio)
        self.assertEqual(result.lyric,specific);self.assertEqual(result.cover,specific_cover)

    def test_space_and_copy_suffix_rules_are_conservative(self) -> None:
        audio = self.touch("晴 天.mp3")
        spaced = self.touch("晴天.lrc")
        self.assertEqual(find_associated_files(audio).lyric, spaced)
        copied_audio = self.touch("副歌.mp3")
        copied_lyric = self.touch("副歌 - 副本.lrc")
        copied_cover = self.touch("副歌(1).jpg")
        result = find_associated_files(copied_audio)
        self.assertEqual(result.lyric, copied_lyric)
        self.assertEqual(result.cover, copied_cover)
        self.assertEqual(result.lyric_priority, MatchPriority.COPY_SUFFIX)
        self.assertEqual(result.cover_priority, MatchPriority.COPY_SUFFIX)

    def test_multiple_best_candidates_are_not_selected_automatically(self) -> None:
        audio = self.touch("歌曲.mp3")
        first = self.touch("歌曲 - 副本.lrc")
        second = self.touch("歌曲(1).lrc")
        result = find_associated_files(audio)
        self.assertEqual(result.lyric_candidates, tuple(sorted((first, second), key=lambda path: path.name.casefold())))
        self.assertTrue(result.lyric_ambiguous)
        self.assertIsNone(result.lyric)

    def test_scans_multiple_songs_and_supports_txt_without_cross_matching(self) -> None:
        a = self.touch("A.mp3")
        a_lyric = self.touch("A.txt")
        a_cover = self.touch("A.webp")
        b = self.touch("B.flac")
        b_lyric = self.touch("B.srt")
        b_cover = self.touch("B.bmp")
        self.touch("unrelated.lrc")
        results = {result.audio.name: result for result in scan_audio_folder(self.root)}
        self.assertEqual(results[a.name].lyric, a_lyric)
        self.assertEqual(results[a.name].cover, a_cover)
        self.assertEqual(results[b.name].lyric, b_lyric)
        self.assertEqual(results[b.name].cover, b_cover)

    def test_no_match_returns_empty_candidates(self) -> None:
        audio = self.touch("没有关联文件.ogg")
        result = find_associated_files(audio)
        self.assertFalse(result.has_matches)
        self.assertEqual(result.lyric_candidates, ())
        self.assertEqual(result.cover_candidates, ())

    def test_folder_scan_can_include_subfolders_when_enabled(self) -> None:
        nested = self.root / "子文件夹"
        nested.mkdir()
        audio = nested / "嵌套歌曲.mp3"
        audio.write_bytes(b"fixture")
        lyric = nested / "嵌套歌曲.lrc"
        lyric.write_bytes(b"fixture")
        self.assertEqual(scan_audio_folder(self.root), ())
        results = scan_audio_folder(self.root, include_subfolders=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].audio, audio)
        self.assertEqual(results[0].lyric, lyric)


if __name__ == "__main__":
    unittest.main()

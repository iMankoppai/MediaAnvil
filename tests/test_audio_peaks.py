import math
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sub2lrc.audio_join import audio_peaks


def write_wav(path: Path, frames, rate: int = 8000) -> None:
    import wave
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(frames)}h", *frames))


class AudioPeaksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_peaks_reflect_the_loudest_part_and_normalise(self) -> None:
        quiet = [int(3000 * math.sin(i * 0.1)) for i in range(8000)]
        loud = [int(20000 * math.sin(i * 0.1)) for i in range(8000)]
        source = self.root / "shape.wav"
        write_wav(source, quiet + loud)
        duration, peaks = audio_peaks(source, buckets=16)
        self.assertAlmostEqual(duration, 2.0, delta=0.1)
        self.assertEqual(len(peaks), 16)
        self.assertGreater(max(peaks[8:]), max(peaks[:8]))
        self.assertLessEqual(max(peaks), 1.0)

    def test_missing_file_raises_a_clear_error(self) -> None:
        from sub2lrc.audio_converter import AudioConversionError
        with self.assertRaisesRegex(AudioConversionError, "不存在"):
            audio_peaks(self.root / "absent.wav")

    def test_cache_is_reused_and_invalidated_when_the_source_changes(self):
        source=self.root/'cached.wav';write_wav(source,[1000]*8000)
        cache=self.root/'cache';first=audio_peaks(source,16,cache_directory=cache)
        with patch('sub2lrc.audio_join.find_ffmpeg',side_effect=AssertionError('cache should avoid decoding')):
            self.assertEqual(audio_peaks(source,16,cache_directory=cache),first)
        write_wav(source,[2000]*16000)
        second=audio_peaks(source,16,cache_directory=cache)
        self.assertAlmostEqual(second[0],2,delta=.1)

    def test_cancel_stops_the_registered_decoder_and_does_not_cache(self):
        from core.tasks import CancellationToken,TaskCancelled
        source=self.root/'cancel.wav';write_wav(source,[1000]*8000)
        token=CancellationToken();processes=[]
        def register(process):
            token.register_process(process)
            if process is not None:processes.append(process);token.cancel()
        with self.assertRaises(TaskCancelled):
            audio_peaks(source,cancel_check=token.raise_if_cancelled,process_callback=register,cache_directory=self.root/'cache')
        self.assertIsNotNone(processes[0].poll())
        self.assertFalse((self.root/'cache'/'peaks.json').exists())

    def test_stream_without_duration_is_reduced_without_retaining_pcm(self):
        source=self.root/'unprobed.wav';write_wav(source,[2000]*8000)
        with patch('sub2lrc.audio_join._duration_seconds',return_value=None):
            duration,peaks=audio_peaks(source,16)
        self.assertAlmostEqual(duration,1);self.assertEqual(len(peaks),16)


if __name__ == "__main__":
    unittest.main()

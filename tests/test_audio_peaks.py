import math
import struct
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

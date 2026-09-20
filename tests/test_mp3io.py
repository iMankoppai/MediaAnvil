from pathlib import Path
import tempfile
import unittest

from sub2lrc.mp3io import apply_to_mp3_copy


class AtomicMp3OutputTests(unittest.TestCase):
    def test_failed_overwrite_keeps_original_and_cleans_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            source.write_bytes(b"ORIGINAL")

            def fail_after_edit(path: Path) -> None:
                path.write_bytes(b"BROKEN")
                raise RuntimeError("test failure")

            with self.assertRaisesRegex(RuntimeError, "test failure"):
                apply_to_mp3_copy(source, None, fail_after_edit)

            self.assertEqual(source.read_bytes(), b"ORIGINAL")
            self.assertEqual(list(root.glob(".sub2lrc-*.mp3")), [])

    def test_failed_save_as_keeps_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp3"
            destination = root / "destination.mp3"
            source.write_bytes(b"SOURCE")
            destination.write_bytes(b"EXISTING DESTINATION")

            def fail_after_edit(path: Path) -> None:
                path.write_bytes(b"BROKEN")
                raise RuntimeError("test failure")

            with self.assertRaisesRegex(RuntimeError, "test failure"):
                apply_to_mp3_copy(source, destination, fail_after_edit)

            self.assertEqual(source.read_bytes(), b"SOURCE")
            self.assertEqual(destination.read_bytes(), b"EXISTING DESTINATION")
            self.assertEqual(list(root.glob(".sub2lrc-*.mp3")), [])


if __name__ == "__main__":
    unittest.main()

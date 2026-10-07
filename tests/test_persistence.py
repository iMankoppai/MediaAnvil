import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.persistence import replace_file


class AtomicReplaceTests(unittest.TestCase):
    def test_transient_windows_lock_is_retried_without_losing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'new';target=Path(directory)/'old'
            source.write_bytes(b'new');target.write_bytes(b'old')
            import os
            replace=os.replace;calls=[]
            def busy_then_replace(src,dst):
                calls.append(1)
                if len(calls)<3:
                    self.assertEqual(target.read_bytes(),b'old')
                    error=PermissionError('sharing lock');error.winerror=32;raise error
                replace(src,dst)
            with patch('core.persistence.os.replace',side_effect=busy_then_replace),patch('core.persistence.time.sleep'):
                replace_file(source,target)
            self.assertEqual(target.read_bytes(),b'new');self.assertEqual(len(calls),3)

    def test_permanent_lock_is_reported_and_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'new';target=Path(directory)/'old'
            source.write_bytes(b'new');target.write_bytes(b'old')
            error=PermissionError('locked');error.winerror=5
            with patch('core.persistence.os.replace',side_effect=error) as replace,patch('core.persistence.time.sleep'):
                with self.assertRaises(PermissionError):replace_file(source,target)
            self.assertEqual(replace.call_count,5)
            self.assertEqual(source.read_bytes(),b'new');self.assertEqual(target.read_bytes(),b'old')

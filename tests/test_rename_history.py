import tempfile
import unittest
from pathlib import Path

from core.audio_renamer import RenameRecord,undo_rename
from core.rename_history import RenameJournal


class RenameJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'rename.json'
        self.journal=RenameJournal(self.path)

    def move(self,name='audio.mp3'):
        old=self.root/name;new=self.root/('renamed-'+name);old.write_bytes(b'original')
        record=RenameRecord(old,new);self.journal.prepare(record);old.rename(new);return record

    def test_restart_recovers_audio_and_companions_and_undo_removes_only_restored_records(self):
        self.journal.begin();audio=self.move();lyric=self.move('audio.lrc');self.journal.finish()
        restored=RenameJournal(self.path)
        self.assertEqual(restored.records(),(audio,lyric))
        audio.old_path.write_bytes(b'occupied')
        result=undo_rename(restored.records(),identities=restored.identities(),on_restored=restored.restored)
        self.assertEqual(result.records,(lyric,));self.assertEqual(restored.records(),(audio,))
        self.assertEqual(audio.old_path.read_bytes(),b'occupied')

    def test_pending_journal_recovers_a_move_but_ignores_an_unexecuted_intent(self):
        self.journal.begin();audio=self.move()
        untouched=self.root/'untouched.mp3';untouched.write_bytes(b'keep')
        self.journal.prepare(RenameRecord(untouched,self.root/'next.mp3'))
        self.assertEqual(RenameJournal(self.path).records(),(audio,))

    def test_failed_new_batch_keeps_previous_undo(self):
        self.journal.begin();audio=self.move();self.journal.finish()
        self.journal.begin();self.journal.finish()
        self.assertEqual(self.journal.records(),(audio,))

    def test_changed_target_is_not_renamed_back(self):
        self.journal.begin();audio=self.move();self.journal.finish()
        audio.new_path.write_bytes(b'replacement with different content')
        result=undo_rename(self.journal.records(),identities=self.journal.identities())
        self.assertFalse(result.records);self.assertEqual(len(result.failures),1)
        self.assertTrue(audio.new_path.exists());self.assertFalse(audio.old_path.exists())

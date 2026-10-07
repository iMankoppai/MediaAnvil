from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from core.tasks import CancellationToken, TaskCancelled, TaskHistory, TaskRecord, load_task_histories, save_task_histories


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


class CancellationTokenTests(unittest.TestCase):
    def test_cancel_sets_flag_raises_and_terminates_registered_process(self) -> None:
        token = CancellationToken()
        process = FakeProcess()
        token.register_process(process)
        token.cancel()
        self.assertTrue(token.cancelled)
        self.assertTrue(process.terminated)
        with self.assertRaises(TaskCancelled):
            token.raise_if_cancelled()

    def test_registering_after_cancel_terminates_immediately(self) -> None:
        token = CancellationToken()
        token.cancel()
        process = FakeProcess()
        token.register_process(process)
        self.assertTrue(process.terminated)


class TaskHistoryTests(unittest.TestCase):
    def test_roundtrip_preserves_parameters_outputs_and_marks_interrupted_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'tasks.json'
            task=TaskHistory('audio',(TaskRecord(Path('a.wav'),'已完成',output=Path('a.mp3')),
                                      TaskRecord(Path('b.wav'),'等待')),
                             {'format':'mp3','parameter':192,'rate':None})
            save_task_histories(path,[task])
            restored=load_task_histories(path)[0]
            self.assertEqual(restored.parameters,task.parameters)
            self.assertEqual(restored.created_at,task.created_at)
            self.assertEqual(restored.records[0].output,Path('a.mp3'))
            self.assertEqual(restored.records[1].state,'已中断')
            self.assertEqual(len(restored.succeeded),1)
            self.assertEqual(len(restored.retryable),1)

    def test_corrupt_store_and_invalid_entries_do_not_block_startup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'tasks.json';path.write_text('{broken',encoding='utf8')
            self.assertEqual(load_task_histories(path),[])
            path.write_text('{"version":1,"tasks":[null,{"parameters":[]}] }',encoding='utf8')
            self.assertEqual(load_task_histories(path),[])


if __name__ == "__main__":
    unittest.main()

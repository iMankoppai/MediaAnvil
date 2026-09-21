from __future__ import annotations

import unittest

from core.tasks import CancellationToken, TaskCancelled


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


if __name__ == "__main__":
    unittest.main()

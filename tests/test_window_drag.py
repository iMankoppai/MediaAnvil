import unittest

from sub2lrc.window_drag import (
    RDW_ALLCHILDREN,
    RDW_FRAME,
    RDW_INVALIDATE,
    RDW_UPDATENOW,
    VK_LBUTTON,
    WM_SETREDRAW,
    WindowsDragRedrawGuard,
)


class FakeRoot:
    def __init__(self) -> None:
        self.bindings = {}
        self.jobs = {}
        self.cancelled = []
        self.next_job = 0

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)

    def winfo_id(self):
        return 1234

    def after(self, delay, callback):
        self.next_job += 1
        job = f"job-{self.next_job}"
        self.jobs[job] = (delay, callback)
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)
        self.jobs.pop(job, None)


class FakeUser32:
    def __init__(self) -> None:
        self.left_pressed = True
        self.messages = []
        self.redraws = []

    def GetAsyncKeyState(self, key):
        self.last_key = key
        return 0x8000 if self.left_pressed else 0

    def SendMessageW(self, *args):
        self.messages.append(args)

    def RedrawWindow(self, *args):
        self.redraws.append(args)


class Event:
    def __init__(self, widget) -> None:
        self.widget = widget


class WindowDragRedrawGuardTests(unittest.TestCase):
    def test_suspends_during_root_configure_and_restores_once(self) -> None:
        root = FakeRoot()
        user32 = FakeUser32()
        guard = WindowsDragRedrawGuard(root, restore_delay_ms=90, user32=user32)

        guard._on_configure(Event(root))
        self.assertEqual(user32.last_key, VK_LBUTTON)
        self.assertEqual(user32.messages, [(1234, WM_SETREDRAW, 0, 0)])
        first_job = guard._restore_job
        self.assertEqual(root.jobs[first_job][0], 90)

        guard._on_configure(Event(root))
        self.assertEqual(user32.messages, [(1234, WM_SETREDRAW, 0, 0)])
        self.assertIn(first_job, root.cancelled)

        guard.restore()
        self.assertEqual(user32.messages[-1], (1234, WM_SETREDRAW, 1, 0))
        flags = RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN | RDW_FRAME
        self.assertEqual(user32.redraws[-1], (1234, None, None, flags))

    def test_ignores_child_configure_and_unpressed_mouse(self) -> None:
        root = FakeRoot()
        user32 = FakeUser32()
        guard = WindowsDragRedrawGuard(root, user32=user32)

        guard._on_configure(Event(object()))
        user32.left_pressed = False
        guard._on_configure(Event(root))

        self.assertFalse(user32.messages)
        self.assertFalse(root.jobs)


if __name__ == "__main__":
    unittest.main()

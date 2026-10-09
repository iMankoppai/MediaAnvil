"""Serial background jobs with immutable submission snapshots."""
from dataclasses import dataclass
from typing import Callable


@dataclass
class QueuedTask:
    task_id: str
    kind: str
    work: Callable
    done: Callable


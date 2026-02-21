"""Queue entry dataclass and file queue model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from compresswitch.utils import file_operation, target_name


class Status(Enum):
    PENDING = auto()
    PROCESSING = auto()
    DONE = auto()
    ERROR = auto()


@dataclass
class QueueEntry:
    path: Path
    operation: str  # "compress" or "decompress"
    target: str  # expected output filename
    status: Status = Status.PENDING
    progress: int = 0
    error_message: str = ""

    @classmethod
    def from_path(cls, path: Path) -> QueueEntry | None:
        """Create a QueueEntry from a file path, or None if unsupported."""
        op = file_operation(path)
        if op is None:
            return None
        return cls(
            path=path,
            operation=op,
            target=target_name(path),
        )


class FileQueue:
    """Manages the ordered list of queue entries."""

    def __init__(self) -> None:
        self._entries: list[QueueEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __getitem__(self, index: int) -> QueueEntry:
        return self._entries[index]

    def add(self, path: Path) -> QueueEntry | None:
        """Add a file to the queue. Returns the entry or None if invalid/duplicate."""
        # Skip duplicates
        for entry in self._entries:
            if entry.path == path:
                return None
        entry = QueueEntry.from_path(path)
        if entry:
            self._entries.append(entry)
        return entry

    def remove(self, index: int) -> None:
        """Remove entry at index."""
        if 0 <= index < len(self._entries):
            del self._entries[index]

    def clear(self) -> None:
        self._entries.clear()

    def next_pending(self) -> QueueEntry | None:
        """Return the first pending entry, or None."""
        for entry in self._entries:
            if entry.status == Status.PENDING:
                return entry
        return None

    def has_pending(self) -> bool:
        return any(e.status == Status.PENDING for e in self._entries)

    def has_any_compress(self) -> bool:
        """Return True if any entry is a compress operation."""
        return any(e.operation == "compress" for e in self._entries)

    def index_of(self, entry: QueueEntry) -> int:
        return self._entries.index(entry)

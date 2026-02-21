"""File validation, extension mapping, and progress parsing."""

from __future__ import annotations

import re
from pathlib import Path

COMPRESS_EXTENSIONS = {".xci", ".nsp"}
DECOMPRESS_EXTENSIONS = {".xcz", ".nsz", ".ncz"}
ALL_EXTENSIONS = COMPRESS_EXTENSIONS | DECOMPRESS_EXTENSIONS

TARGET_EXTENSION = {
    ".xci": ".xcz",
    ".nsp": ".nsz",
    ".xcz": ".xci",
    ".nsz": ".nsp",
    ".ncz": ".nca",
}

# enlighten progress bars emit lines like: " 62%|████████████░░░░░░░░"
# We look for a percentage anywhere in the ANSI-laden output.
_PROGRESS_RE = re.compile(r"(\d{1,3})%\|")


def file_operation(path: Path) -> str | None:
    """Return 'compress' or 'decompress' based on extension, or None if unsupported."""
    ext = path.suffix.lower()
    if ext in COMPRESS_EXTENSIONS:
        return "compress"
    if ext in DECOMPRESS_EXTENSIONS:
        return "decompress"
    return None


def target_name(path: Path) -> str:
    """Return the expected output filename after conversion."""
    ext = path.suffix.lower()
    new_ext = TARGET_EXTENSION.get(ext, ext)
    return path.stem + new_ext


def is_valid_switch_file(path: Path) -> bool:
    """Check if path is a supported Switch file."""
    return path.is_file() and path.suffix.lower() in ALL_EXTENSIONS


def parse_progress(line: str) -> int | None:
    """Extract integer percentage from an enlighten progress line.

    Returns None if no percentage found.
    """
    m = _PROGRESS_RE.search(line)
    if m:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val
    return None


def file_filter_extensions() -> list[str]:
    """Return glob patterns for the file chooser filter."""
    return [f"*{ext}" for ext in sorted(ALL_EXTENSIONS)]

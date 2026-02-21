"""Background nsz subprocess with pty-based progress capture."""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from gi.repository import GLib

from compresswitch.file_queue import QueueEntry
from compresswitch.utils import parse_progress


def _find_nsz_command() -> list[str]:
    """Find how to invoke nsz.

    In PyInstaller: re-invokes ourselves with --nsz-worker flag.
    In dev mode: uses python -m nsz from the venv.
    """
    if getattr(sys, "_MEIPASS", None):
        return [sys.executable, "--nsz-worker"]
    return [sys.executable, "-m", "nsz"]


class NszWorker:
    """Runs nsz as a subprocess in a pty, parsing progress output."""

    def __init__(
        self,
        entry: QueueEntry,
        *,
        compression_level: int = 18,
        block_compression: bool = True,
        output_dir: str = "",
        on_progress: Callable[[QueueEntry, int], None] | None = None,
        on_done: Callable[[QueueEntry, bool, str], None] | None = None,
    ):
        self.entry = entry
        self.compression_level = compression_level
        self.block_compression = block_compression
        self.output_dir = output_dir
        self.on_progress = on_progress
        self.on_done = on_done

        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._cancelled = False

    def _build_command(self) -> list[str]:
        cmd = list(_find_nsz_command())
        if self.entry.operation == "compress":
            cmd += ["-C"]
            if self.entry.path.suffix.lower() == ".xci" and self.block_compression:
                cmd += ["-B"]
            elif self.entry.path.suffix.lower() == ".xci":
                cmd += ["-S"]
            else:
                # NSP: block vs solid
                if self.block_compression:
                    cmd += ["-B"]
                else:
                    cmd += ["-S"]
            cmd += ["-l", str(self.compression_level)]
        else:
            cmd += ["-D"]

        if self.output_dir:
            cmd += ["-o", self.output_dir]

        # --no-verify to skip post-compression verification (faster)
        cmd.append(str(self.entry.path))
        return cmd

    def start(self) -> None:
        """Launch the nsz subprocess in a background thread."""
        self._cancelled = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Cancel the running operation."""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _run(self) -> None:
        """Thread target: run nsz and capture progress."""
        try:
            cmd = self._build_command()
        except FileNotFoundError as e:
            self._report_done(False, str(e))
            return

        master_fd, slave_fd = pty.openpty()
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
            os.close(slave_fd)
            slave_fd = -1

            output_lines: list[str] = []
            buf = b""
            while True:
                if self._cancelled:
                    break
                ready, _, _ = select.select([master_fd], [], [], 0.2)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    buf += data
                    # Process line-like chunks (enlighten uses \r for updates)
                    while b"\r" in buf or b"\n" in buf:
                        # Split on either \r or \n
                        idx_r = buf.find(b"\r")
                        idx_n = buf.find(b"\n")
                        if idx_r == -1:
                            idx = idx_n
                        elif idx_n == -1:
                            idx = idx_r
                        else:
                            idx = min(idx_r, idx_n)
                        line = buf[:idx].decode("utf-8", errors="replace")
                        buf = buf[idx + 1 :]
                        if line.strip():
                            output_lines.append(line)
                            pct = parse_progress(line)
                            if pct is not None:
                                self._report_progress(pct)
                elif self._process.poll() is not None:
                    break

            # Read any remaining data
            try:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        break
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    output_lines.append(data.decode("utf-8", errors="replace"))
            except OSError:
                pass

            self._process.wait()
            returncode = self._process.returncode

            if self._cancelled:
                self._report_done(False, "Cancelled")
            elif returncode == 0:
                self._report_done(True, "")
            else:
                # Check for known errors
                full_output = "\n".join(output_lines)
                if "keys" in full_output.lower() and (
                    "missing" in full_output.lower()
                    or "not found" in full_output.lower()
                    or "prod.keys" in full_output.lower()
                ):
                    self._report_done(
                        False, "Switch keys not found. Place prod.keys in ~/.switch/"
                    )
                else:
                    self._report_done(
                        False, f"nsz exited with code {returncode}"
                    )
        except Exception as e:
            self._report_done(False, str(e))
        finally:
            if slave_fd >= 0:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            try:
                os.close(master_fd)
            except OSError:
                pass

    def _report_progress(self, percent: int) -> None:
        if self.on_progress:
            GLib.idle_add(self.on_progress, self.entry, percent)

    def _report_done(self, success: bool, message: str) -> None:
        if self.on_done:
            GLib.idle_add(self.on_done, self.entry, success, message)

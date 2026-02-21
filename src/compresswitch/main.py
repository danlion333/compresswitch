"""Adw.Application entry point for CompressSwitch."""

from __future__ import annotations

import os
import sys


def _run_nsz_worker() -> None:
    """Run nsz CLI with the remaining arguments (used in subprocess mode)."""
    # Strip our --nsz-worker flag and pass the rest to nsz
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    import nsz

    nsz.main()


def main() -> None:
    # If invoked as nsz subprocess worker, run nsz instead of the GUI
    if len(sys.argv) >= 2 and sys.argv[1] == "--nsz-worker":
        _run_nsz_worker()
        return

    # When running from PyInstaller bundle, set GI_TYPELIB_PATH
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        typelib_path = os.path.join(meipass, "gi_typelibs")
        existing = os.environ.get("GI_TYPELIB_PATH", "")
        if existing:
            os.environ["GI_TYPELIB_PATH"] = typelib_path + ":" + existing
        else:
            os.environ["GI_TYPELIB_PATH"] = typelib_path

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from compresswitch.window import CompressSwitchApp

    app = CompressSwitchApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()

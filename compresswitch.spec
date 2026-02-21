# -*- mode: python ; coding: utf-8 -*-
import glob
import os

# Find typelib directory (varies by distro)
_candidates = glob.glob('/usr/lib*/girepository-1.0') + \
              glob.glob('/usr/lib/*/girepository-1.0')
typelib_dir = _candidates[0] if _candidates else '/usr/lib/girepository-1.0'
typelibs = [
    'Adw-1.typelib',
    'Gdk-4.0.typelib',
    'GdkPixbuf-2.0.typelib',
    'GdkWayland-4.0.typelib',
    'GdkX11-4.0.typelib',
    'Gio-2.0.typelib',
    'GioUnix-2.0.typelib',
    'GLib-2.0.typelib',
    'GLibUnix-2.0.typelib',
    'GModule-2.0.typelib',
    'GObject-2.0.typelib',
    'Graphene-1.0.typelib',
    'Gsk-4.0.typelib',
    'Gtk-4.0.typelib',
    'Pango-1.0.typelib',
    'PangoCairo-1.0.typelib',
]

typelib_datas = [(os.path.join(typelib_dir, t), 'gi_typelibs') for t in typelibs]

a = Analysis(
    ['src/compresswitch/main.py'],
    pathex=[],
    binaries=[],
    datas=typelib_datas,
    hiddenimports=[
        'gi',
        'gi.repository.Adw',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.Gio',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Pango',
        'compresswitch',
        'compresswitch.main',
        'compresswitch.window',
        'compresswitch.worker',
        'compresswitch.file_queue',
        'compresswitch.utils',
        # nsz and all its dependencies (invoked via --nsz-worker flag)
        'nsz',
        'nsz.Fs',
        'nsz.nut',
    ],
    hookspath=[],
    hooksconfig={
        'gi': {
            'module-versions': {
                'Gtk': '4.0',
                'Gdk': '4.0',
                'Adw': '1',
            },
        },
    },
    runtime_hooks=['gi_runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='compresswitch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

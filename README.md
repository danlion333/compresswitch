# CompressSwitch

A GTK 4 desktop application for compressing and decompressing Nintendo Switch game files. Provides a simple drag-and-drop interface for the [nsz](https://github.com/nicoboss/nsz) compression tool.

## Features

- Compress XCI to XCZ and NSP to NSZ
- Decompress XCZ, NSZ, and NCZ back to their original formats
- Drag-and-drop file support
- Batch processing with a file queue
- Configurable compression level (1-22) and block compression
- Custom output directory
- Real-time progress tracking

## Requirements

- Python 3.11+
- GTK 4 and libadwaita
- Nintendo Switch `prod.keys` in `~/.switch/` (required by nsz)

### System dependencies

**Fedora:**

```sh
sudo dnf install gtk4-devel libadwaita-devel python3-gobject-devel
```

**Ubuntu / Debian:**

```sh
sudo apt install libgtk-4-dev libadwaita-1-dev python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

**Arch Linux:**

```sh
sudo pacman -S gtk4 libadwaita python-gobject
```

## Installation

### From source with uv

```sh
git clone https://github.com/danlion333/compresswitch.git
cd compresswitch
uv sync
uv run compresswitch
```

### With pip

```sh
pip install .
compresswitch
```

## Building a standalone binary

A PyInstaller spec is included for creating a single-file executable:

```sh
uv run pyinstaller compresswitch.spec
```

The binary will be at `dist/compresswitch`.

## Usage

1. Launch CompressSwitch
2. Add files by dragging them onto the window or clicking "Add Files"
3. Adjust compression settings if needed
4. Click "Start" to begin processing

Supported file types:

| Input | Output | Operation |
|-------|--------|-----------|
| `.xci` | `.xcz` | Compress |
| `.nsp` | `.nsz` | Compress |
| `.xcz` | `.xci` | Decompress |
| `.nsz` | `.nsp` | Decompress |
| `.ncz` | `.nca` | Decompress |

## License

[MIT](LICENSE)

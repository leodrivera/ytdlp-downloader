# ytdlp-downloader

A Python wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp) that adds cross-platform dependency validation, automatic update checks, and a simplified interface for the most common download scenarios.

## Features

- Validates `ffmpeg` and `ffprobe` before downloading, with OS-specific install hints
- Checks for yt-dlp updates on every run and offers to auto-update via pip
- Three container strategies for video output: `fast-remux`, `best-mp4`, and `force-mp4`
- Passes all remaining arguments directly to yt-dlp — no wrapping of flags you already know
- Progress and post-processor hooks for cleaner terminal output
- Works on Windows, Linux, and macOS

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10+ | For `match`/`BooleanOptionalAction` support |
| yt-dlp | latest | Install with `pip install "yt-dlp[default]"` |
| Deno | 2.0+ | Required by yt-dlp for YouTube and some extractors |
| ffmpeg + ffprobe | 4.0+ | Required for muxing and post-processing |

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/leodrivera/ytdlp-downloader.git
cd ytdlp-downloader

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Install yt-dlp
pip install "yt-dlp[default]"

# 4. Install Deno (https://deno.com)
# Windows:   winget install DenoLand.Deno
# Linux/mac: curl -fsSL https://deno.land/install.sh | sh

# 5. Install ffmpeg
# Windows:   winget install ffmpeg
# Ubuntu:    sudo apt install ffmpeg
# macOS:     brew install ffmpeg

# 6. (Linux/macOS) Make the script executable
chmod +x ytdlp_downloader.py
```

## Usage

```
python ytdlp_downloader.py [SCRIPT OPTIONS] [YT-DLP OPTIONS] URL
```

Any option not listed below is forwarded directly to yt-dlp.

### Script options

| Option | Default | Description |
|---|---|---|
| `--container-strategy` | `fast-remux` | `fast-remux` — remux only, output may be WebM/MKV if MP4 is incompatible; `best-mp4` — prefer H.264/AAC sources, remux to MP4; `force-mp4` — always output MP4, re-encode if necessary |
| `--check-updates` / `--no-check-updates` | enabled | Check for yt-dlp updates before downloading; prompts to update via pip if installed that way |
| `--script-help` | — | Show this script's help and exit |

### Pass-through yt-dlp options (examples)

| Flag | Effect |
|---|---|
| `-F URL` | List available formats |
| `-f FORMAT` | Select a specific format |
| `-x` | Extract audio only |
| `--audio-format mp3` | Convert extracted audio to mp3 |
| `--yes-playlist` | Download entire playlist |
| `-o TEMPLATE` | Output filename template |
| `--cookies cookies.txt` | Authenticate via cookie file |
| `--cookies-from-browser chrome` | Read cookies directly from Chrome |
| `-U` | Update yt-dlp |
| `--version` | Print yt-dlp version |

## Examples

```bash
# List available formats
python ytdlp_downloader.py -F "https://www.youtube.com/watch?v=VIDEO_ID"

# Download best quality (default fast-remux strategy)
python ytdlp_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Download and guarantee MP4 output
python ytdlp_downloader.py --container-strategy best-mp4 "URL"

# Extract audio as MP3 at 192 kbps
python ytdlp_downloader.py -x --audio-format mp3 --audio-quality 192 "URL"

# Download an entire playlist
python ytdlp_downloader.py --yes-playlist "https://www.youtube.com/playlist?list=PLxxxxxx"

# Custom output path and filename template
python ytdlp_downloader.py "URL" -o "./downloads/%(title)s [%(id)s].%(ext)s"

# Authenticate with YouTube via browser cookies
python ytdlp_downloader.py --cookies-from-browser chrome "URL"

# Skip the update check
python ytdlp_downloader.py --no-check-updates "URL"
```

## License

MIT — see [LICENSE](LICENSE).

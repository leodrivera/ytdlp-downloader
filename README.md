# ytdlp-downloader

A Python wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp) that adds cross-platform dependency validation, automatic update checks, and a simplified interface for the most common download scenarios.

## Features

- Validates `ffmpeg` and `ffprobe` before downloading, with OS-specific install hints
- Checks for yt-dlp updates before each download and offers to auto-update via pip
- Three container strategies for video output: `fast-remux`, `best-mp4`, and `force-mp4`
- Passes all remaining arguments directly to yt-dlp — no wrapping of flags you already know
- Progress and post-processor hooks for cleaner terminal output
- Works on Windows, Linux, and macOS

### Defaults

| Behavior | Default | Change it with |
|---|---|---|
| Output path | `./%(title)s.%(ext)s` (current directory) | `-o TEMPLATE` |
| Playlist URLs | Downloads the first video only, after a warning | `--yes-playlist` |
| Resume partial downloads | Enabled | `--no-continue` |
| Update check | Enabled; **stops the script** if yt-dlp is outdated | `--no-check-updates` |

These defaults are passed to yt-dlp as ordinary command-line options, ahead of your own
arguments. Since yt-dlp lets the last occurrence of an option win, passing the same option
explicitly always overrides the default — `-o`, `--yes-playlist`, `--recode-video` and so on.
The one exception is `-S`/`--format-sort`, which accumulates: your sort fields are evaluated
first and the preset's `ext:mp4:m4a` only breaks ties.

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.9+ | For `BooleanOptionalAction` and builtin generic types |
| yt-dlp | latest | Install with `pip install "yt-dlp[default]"` |
| Deno | 2.0+ | Required by yt-dlp for YouTube and some extractors |
| ffmpeg + ffprobe | 4.0+ | Required for muxing and post-processing |

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/leodrivera/ytdlp-downloader.git
cd ytdlp-downloader

# 2. Create and activate a virtual environment
# Debian/Ubuntu: if this fails with "ensurepip is not available", see Troubleshooting
python3 -m venv .venv             # Linux / macOS
py -m venv .venv                  # Windows (`python`/`python3` also work if on PATH)
source .venv/bin/activate         # Linux / macOS
.venv\Scripts\activate            # Windows

# 3. Install yt-dlp
# Use the [default] extra so the EJS solver scripts YouTube needs are included
pip install "yt-dlp[default]"

# 4. Install Deno 2.0+ (JavaScript runtime, required for YouTube and some extractors)
# https://docs.deno.com/runtime/getting_started/installation/
# Windows:   winget install DenoLand.Deno   OR   irm https://deno.land/install.ps1 | iex
# Linux:     curl -fsSL https://deno.land/install.sh | sh
# macOS:     brew install deno              OR   curl -fsSL https://deno.land/install.sh | sh
# If `deno --version` isn't found in a new terminal, run `source ~/.deno/env`
# (the installer appends this to ~/.bashrc, but non-bash/non-interactive
# shells won't pick it up automatically — check with `echo $SHELL`)

# 5. Install ffmpeg (and ffprobe — required for muxing and post-processing)
# Windows:   winget install ffmpeg
#            OR download 'ffmpeg-git-essentials.7z' from https://www.gyan.dev/ffmpeg/builds/
#            then copy ffmpeg.exe/ffprobe.exe from its 'bin' folder next to the
#            script (or add that folder to PATH)
# Ubuntu:    sudo apt install ffmpeg        # CentOS/RHEL: sudo yum install ffmpeg
# macOS:     brew install ffmpeg            # requires Homebrew
```

On Linux/macOS the script is committed with the executable bit, so `./ytdlp_downloader.py URL`
works after cloning. If you downloaded the file outside git, run `chmod +x ytdlp_downloader.py` first.

## Troubleshooting

**`n challenge` / `found 0 n function possibilities` on YouTube**

The signature solver is outdated or missing. In order:

1. Update yt-dlp and its extras: `pip install -U "yt-dlp[default]"`
2. Confirm Deno 2.0+ is on PATH: `deno --version`
3. Let yt-dlp fetch solver scripts at runtime: `--remote-components ejs:npm` (requires Deno or Bun)

Details: [yt-dlp EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

**`ensurepip is not available` when creating the venv (Debian/Ubuntu)**

Install the matching venv package, e.g. `sudo apt install python3.12-venv`, then retry step 2.

**`ffmpeg not found`**

The script validates `ffmpeg` and `ffprobe` before downloading and prints an OS-specific hint.
Re-run step 5 and make sure both binaries are on PATH.

**`Failed to decrypt with DPAPI` when using `--cookies-from-browser` (Windows + Chrome)**

Chrome encrypts its cookie store in a way yt-dlp cannot always read. Export the cookies with a
browser extension such as
[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
(Netscape format), then pass the file: `--cookies cookies.txt "URL"`.

## Usage

```
python ytdlp_downloader.py [SCRIPT OPTIONS] [YT-DLP OPTIONS] URL
```

With the virtual environment activated, `python` resolves to the venv interpreter on every
platform. Outside a venv, use whichever name is on your PATH (`python3` on most Linux/macOS
setups, `py` on Windows). On Linux/macOS you can also run `./ytdlp_downloader.py URL` directly.

Any option not listed below is forwarded directly to yt-dlp.

### Script options

| Option | Default | Description |
|---|---|---|
| `--container-strategy` | `fast-remux` | Presets over native yt-dlp flags. Affects video downloads only (skipped with `-x`). `fast-remux` → `--remux-video mp4`; `best-mp4` → `-S ext:mp4:m4a --remux-video mp4`; `force-mp4` → `--recode-video mp4` |
| `--check-updates` / `--no-check-updates` | enabled | Check for yt-dlp updates before downloading. If outdated, the script stops without downloading; when yt-dlp was installed via pip it first offers to run the update for you |
| `--script-help` | — | Show this script's help and exit. Note `-h`/`--help` is forwarded to yt-dlp instead |

### Controlling output

The script's own messages follow yt-dlp's verbosity flags:

| Flag | Effect |
|---|---|
| *(none)* | Dependency check, title, per-chunk progress, post-processor steps, final filename |
| `--no-progress` | Same, without the percentage lines |
| `-q` / `--quiet` | Errors only — nothing on success |

Errors are never silenced, so `-q` still reports a failed download and exits non-zero.
`-F` also keeps printing its format table under `-q`, since that output *is* the result.

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

# Prefer MP4-compatible sources, remux only (no re-encoding)
python ytdlp_downloader.py --container-strategy best-mp4 "URL"

# Guarantee MP4 output, re-encoding if the source codecs are incompatible
python ytdlp_downloader.py --container-strategy force-mp4 "URL"

# Extract audio as MP3 at 192 kbps (the K suffix means bitrate; a bare number is a 0-10 VBR level)
python ytdlp_downloader.py -x --audio-format mp3 --audio-quality 192K "URL"

# Download an entire playlist
python ytdlp_downloader.py --yes-playlist "https://www.youtube.com/playlist?list=PLxxxxxx"

# Custom output path and filename template (see the section below)
python ytdlp_downloader.py "URL" -o "./downloads/%(title)s [%(id)s].%(ext)s"

# Authenticate with YouTube via browser cookies
python ytdlp_downloader.py --cookies-from-browser chrome "URL"

# Export browser cookies to a file (no URL = export only), then reuse that file
# Warning: the export contains cookies for ALL sites — protect the file
python ytdlp_downloader.py --cookies-from-browser chrome --cookies cookies.txt
python ytdlp_downloader.py --cookies cookies.txt "URL"

# Show help
python ytdlp_downloader.py --script-help   # this script's options
python ytdlp_downloader.py -h              # yt-dlp's own help

# Skip the update check
python ytdlp_downloader.py --no-check-updates "URL"

# Quieter output: milestones only, or nothing at all
python ytdlp_downloader.py --no-progress "URL"
python ytdlp_downloader.py -q "URL"
```

## Picking a specific format

Start with `-F` to see what the site offers:

```
$ python ytdlp_downloader.py -F "https://www.youtube.com/watch?v=pBUlV7rZp_c"
ID  EXT  RESOLUTION FPS HDR |  FILESIZE    TBR PROTO | VCODEC          VBR ACODEC      ABR MORE INFO
139 m4a  audio only          |   4.20MiB    49k https | audio only          mp4a.40.5   49k low, m4a_dash
140 m4a  audio only          |  11.13MiB   129k https | audio only          mp4a.40.2  129k medium, m4a_dash
251 webm audio only          |  11.38MiB   132k https | audio only          opus       132k medium, webm_dash
160 mp4  256x144      30     |   4.06MiB    47k https | avc1.4d400c     47k video only      144p, mp4_dash
18  mp4  640x360      30     | ~32.93MiB   383k https | avc1.42001E         mp4a.40.2       360p
134 mp4  640x360      30     |  21.84MiB   254k https | avc1.4d401e    254k video only      360p, mp4_dash
299 mp4  1920x1080    60     | 423.35MiB  4923k https | avc1.64002a   4923k video only      1080p60, mp4_dash
303 webm 1920x1080    60     | 249.27MiB  2899k https | vp9           2899k video only      1080p60, webm_dash
699 mp4  1920x1080    60 10  | 431.65MiB  5020k https | av01.0.09M.10 5020k video only      1080p60 HDR, mp4_dash
315 webm 3840x2160    60     |   2.09GiB 24833k https | vp9          24833k video only      2160p60, webm_dash
```

The `MORE INFO` column marks each entry as `video only`, `audio only`, or neither — an entry
with both a VCODEC and an ACODEC (such as `18` above) is already muxed and needs no merging.
Note how the same resolution appears several times with different codecs and bitrates: at
1080p60 the AVC track is 423 MiB while the VP9 one is 249 MiB.

```bash
# One ID that already carries video and audio — no merge step
python ytdlp_downloader.py -f 18 "URL"

# Video-only ID + audio-only ID, joined with '+' (1080p60 AVC video + 129k m4a audio)
python ytdlp_downloader.py -f 299+140 "URL"

# By resolution instead of ID: best video up to 720p, plus the best audio
python ytdlp_downloader.py -f "bv*[height<=720]+ba" "URL"

# By resolution, without failing when that height is unavailable:
# -S picks the closest match rather than filtering candidates out
python ytdlp_downloader.py -S "res:720" "URL"

# Smallest file: lowest resolution, then lowest bitrate
python ytdlp_downloader.py -S "+res,+br" "URL"

# Prefer a codec (AV1 over VP9 over H.264) at up to 1080p
python ytdlp_downloader.py -S "res:1080,vcodec:av01" "URL"
```

`bv*` means "best video, muxed formats allowed" and `ba` "best audio"; `-f` **filters**
(no match, no download) while `-S` **sorts** (always downloads something, closest first).

## Output templates

`-o` sets the path and the filename in one string; missing directories are created.
Downloading the video above with:

```bash
python ytdlp_downloader.py -f 18 -o "./downloads/%(title)s [%(id)s].%(ext)s" "https://www.youtube.com/watch?v=pBUlV7rZp_c"
```

produces:

```
downloads/4K HDR Video ULTRA HD 120 FPS - Dolby Vision [pBUlV7rZp_c].mp4
```

Each `%(field)s` is replaced by that field's value: `%(title)s` → `4K HDR Video ULTRA HD 120
FPS - Dolby Vision`, `%(id)s` → `pBUlV7rZp_c`, `%(ext)s` → the container that ends up on disk
(`mp4`). Literal text such as the brackets and the `downloads/` prefix is kept as typed.

```bash
# Group a playlist in its own folder, numbered in playlist order
python ytdlp_downloader.py --yes-playlist -o "./%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" "PLAYLIST_URL"

# Sort by uploader and date, e.g.
# downloads/4K Video ULTRA HD/20240416 - 4K HDR Video ULTRA HD 120 FPS - Dolby Vision.mp4
python ytdlp_downloader.py -o "./downloads/%(uploader)s/%(upload_date)s - %(title)s.%(ext)s" "URL"

# Keep the ID only, which is always filesystem-safe
python ytdlp_downloader.py -o "./%(id)s.%(ext)s" "URL"
```

Full field list: [yt-dlp output template](https://github.com/yt-dlp/yt-dlp#output-template).

## License

MIT — see [LICENSE](LICENSE).

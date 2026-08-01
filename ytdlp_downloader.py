#!/usr/bin/env python3
"""
A yt-dlp wrapper with dependency validation, update checks, and container strategies.

Requirements (Python 3.9+, yt-dlp, Deno 2.0+, ffmpeg + ffprobe), full installation
steps, option reference, and troubleshooting live in README.md:
https://github.com/leodrivera/ytdlp-downloader#readme

Run:
  python ytdlp_downloader.py [SCRIPT OPTIONS] [YT-DLP OPTIONS] URL
  ./ytdlp_downloader.py URL                    # Linux/macOS, script is executable
  python ytdlp_downloader.py --script-help     # script options only
"""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
import sys
from typing import Any

from yt_dlp import YoutubeDL, parse_options
from yt_dlp.utils import DownloadError


# Verbosity, mirrored from yt-dlp's own --quiet and --no-progress options so that the
# messages this script prints itself follow the same flags.
_quiet = False
_show_progress = True


def set_verbosity(ydl_opts: dict[str, Any]) -> None:
    """Adopt the verbosity yt-dlp parsed from the command line."""
    global _quiet, _show_progress

    _quiet = bool(ydl_opts.get("quiet"))
    _show_progress = not (_quiet or ydl_opts.get("noprogress"))


def print_info(msg: str) -> None:
    """Print a message unless --quiet was requested."""
    if not _quiet:
        print(msg, flush=True)


def print_progress(msg: str) -> None:
    """Print a per-chunk progress update unless --quiet or --no-progress was requested."""
    if _show_progress:
        print(msg, flush=True)


def print_error(msg: str) -> None:
    """Print a message regardless of verbosity: errors are never silenced."""
    print(msg, flush=True)


class CustomLogger:
    """Reduce yt-dlp verbosity: only show warnings and errors."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        print_info(f"Warning: {msg}")

    def error(self, msg: str) -> None:
        print_error(f"Error: {msg}")


def stream_label(info: dict[str, Any]) -> str:
    """
    Describe which stream a hook event refers to.

    Video and audio arrive as separate downloads whenever yt-dlp has to merge them, so every
    progress message would otherwise be indistinguishable from the previous one.
    """
    vcodec = info.get("vcodec") or "none"
    acodec = info.get("acodec") or "none"
    has_video, has_audio = vcodec != "none", acodec != "none"

    if has_video and has_audio:
        return "video+audio"
    if has_video:
        return f"video ({info.get('resolution') or info.get('format_note') or vcodec})"
    if has_audio:
        return f"audio ({acodec})"

    # Direct file URLs go through the generic extractor, which reports no codecs at all.
    ext = info.get("ext")
    return f"file ({ext})" if ext else "file"


def progress_hook(d: dict[str, Any]) -> None:
    """Print simple progress information for downloads."""
    status = d.get("status")
    label = stream_label(d.get("info_dict") or {})

    if status == "downloading":
        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")
        print_progress(f"Downloading {label}: {percent} at {speed}, ETA: {eta}")

    elif status == "finished":
        print_info(f"Finished downloading {label}.")

    elif status == "error":
        print_error(f"Error while downloading {label}.")


_last_pp_event: tuple[Any, ...] | None = None


def postprocessor_hook(d: dict[str, Any]) -> None:
    """Hook specifically for post-processor progress."""
    global _last_pp_event

    status = d.get("status")
    postprocessor = d.get("postprocessor", "Processing")

    # yt-dlp fires some post-processor hooks twice with an identical payload; report once.
    event = (status, postprocessor, (d.get("info_dict") or {}).get("filepath"))
    if event == _last_pp_event:
        return
    _last_pp_event = event

    if status == "started":
        print_info(f"[Post-Processor] Started: {postprocessor}")

    elif status == "processing":
        # Some post-processors provide progress info
        if "progress" in d:
            progress = d.get("progress", {})
            percent = progress.get("percent", "N/A")
            print_progress(f"[Post-Processor] {postprocessor}: {percent}%")
        else:
            print_progress(f"[Post-Processor] {postprocessor} in progress...")

    elif status == "finished":
        print_info(f"[Post-Processor] Completed: {postprocessor}")


def print_ffmpeg_install_hint(os_name: str) -> None:
    """Print OS-specific installation instructions for ffmpeg."""
    if os_name == "Windows":
        print_error(
            "To install ffmpeg, run 'winget install ffmpeg'\n"
            "  OR download 'ffmpeg-git-essentials.7z' from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-github\n"
            "     Extract and copy ffmpeg.exe/ffprobe.exe from 'bin' folder to this script's directory (or add to PATH)."
        )
    elif os_name == "Linux":
        print_error(
            "To install ffmpeg, run 'sudo apt install ffmpeg' (Ubuntu/Debian) or 'sudo yum install ffmpeg' (CentOS/RHEL)."
        )
    elif os_name == "Darwin":  # macOS
        print_error("To install ffmpeg, run 'brew install ffmpeg' (requires Homebrew).")
    else:
        print_error("Please install ffmpeg for your operating system.")


def check_tool(tool: str) -> bool:
    """
    Check if a tool (ffmpeg/ffprobe) is installed and functional.
    Validates across Windows, Linux, and macOS.
    Returns True if tool is available, False otherwise.
    """
    if not shutil.which(tool):
        print_error(f"Error: {tool} is not installed.")
        return False

    # Verify the tool actually executes
    try:
        result = subprocess.run(
            [tool, "-version"], capture_output=True, text=True, timeout=10, check=False
        )

        if result.returncode != 0:
            print_error(f"Error: {tool} exists but failed to execute properly.")
            return False

        # Extract and check version
        version_match = re.search(r"version\s+([\d.]+)", result.stdout)
        if version_match:
            version = version_match.group(1)
            print_info(f"{tool} version {version} detected.")

            # Warn if version is too old
            major_version = int(version.split(".")[0])
            if major_version < 4:
                print_info(
                    f"Warning: {tool} version {version} is below 4.0. Consider upgrading for better compatibility."
                )
        else:
            print_info(f"Warning: Could not determine {tool} version.")

        return True

    except subprocess.TimeoutExpired:
        print_error(f"Error: {tool} command timed out.")
        return False
    except FileNotFoundError:
        print_error(f"Error: {tool} not found in PATH.")
        return False
    except (OSError, ValueError) as e:
        print_error(f"Error: Unexpected error checking {tool}: {e}")
        return False


def check_dependencies() -> None:
    """Ensure ffmpeg and ffprobe are installed and functional."""
    os_name = platform.system()
    print_info(f"Operating system detected: {os_name}")

    ffmpeg_ok = check_tool("ffmpeg")
    ffprobe_ok = check_tool("ffprobe")

    if not ffmpeg_ok or not ffprobe_ok:
        print_ffmpeg_install_hint(os_name)
        print_error("Error: Required dependencies are missing. Please install them to proceed.")
        sys.exit(1)

    print_info("All dependencies validated successfully.")


def build_default_argv(args: argparse.Namespace, extra: list[str]) -> list[str]:
    """
    Build the script's defaults as native yt-dlp arguments.

    These are placed *before* the user's arguments so that yt-dlp's own parser resolves
    precedence: for repeated options the last occurrence wins, so anything the user passes
    explicitly overrides the default here.
    """
    argv = ["-o", "./%(title)s.%(ext)s", "--no-playlist"]

    # The script does its own update check; silence yt-dlp's outdated warning when it is off.
    if not args.check_updates:
        argv.append("--no-update")

    # Audio-only downloads have no video container to remux or recode: adding those
    # post-processors would run them over the extracted audio file.
    if "-x" in extra or "--extract-audio" in extra:
        return argv

    # Container strategy: presets over native remux/recode/format-sort options.
    if args.container_strategy == "fast-remux":
        # Copy streams into MP4 when the codecs allow it; keep the original container otherwise.
        argv += ["--remux-video", "mp4"]
    elif args.container_strategy == "best-mp4":
        # Prefer MP4/M4A sources so the remux above succeeds without re-encoding.
        argv += ["-S", "ext:mp4:m4a", "--remux-video", "mp4"]
    elif args.container_strategy == "force-mp4":
        argv += ["--recode-video", "mp4"]

    return argv


def build_script_ydl_opts() -> dict[str, Any]:
    """yt-dlp options with no command-line equivalent (logging and progress reporting)."""
    return {
        "logger": CustomLogger(),
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }


def _run_ytdlp_update_check() -> tuple[bool, str, bool]:
    """
    Run yt-dlp -U and return (outdated, combined_output, is_pip_install).
    outdated: True if a newer version is available (or update failed).
    is_pip_install: True if output indicates yt-dlp was installed via pip.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "-U"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Warning: Update check timed out.", False
    except FileNotFoundError:
        return False, "", False

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    combined = "\n".join(filter(None, [out, err]))

    # Non-zero exit usually means update failed (e.g. outdated + pip install)
    outdated = result.returncode != 0
    pip_msg = "you installed yt-dlp with pip" in combined.lower() or "use that to update" in combined.lower()
    return outdated, combined, pip_msg


def main() -> int:
    parser = argparse.ArgumentParser(
        add_help=False,
        description="Download videos or audio using yt-dlp with cross-platform support. "
        "Pass URL and options as with yt-dlp (e.g. URL, -F URL, -U, --version, --cookies). "
        "Use -h/--help for yt-dlp help, --script-help for this script's help.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples (use yt-dlp options for -F, -f, -x, --yes-playlist, etc.):\n"
            "  # List available formats\n"
            '  python ytdlp_downloader.py -F "https://www.youtube.com/watch?v=VIDEO_ID"\n\n'
            "  # Basic video download\n"
            '  python ytdlp_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"\n\n'
            "  # Download entire playlist\n"
            '  python ytdlp_downloader.py --yes-playlist "https://www.youtube.com/playlist?list=PLxxxxxx"\n\n'
            "  # Audio-only (mp3, 192k)\n"
            '  python ytdlp_downloader.py -x --audio-format mp3 --audio-quality 192K "URL" -o "./downloads/%(title)s.%(ext)s"\n\n'
            "  # Skip update check (check is on by default; script stops if outdated)\n"
            '  python ytdlp_downloader.py --no-check-updates "URL"\n\n'
            "  # Fast remux strategy\n"
            '  python ytdlp_downloader.py --container-strategy fast-remux "URL"\n\n'
            "  # Best MP4, remux only\n"
            '  python ytdlp_downloader.py --container-strategy best-mp4 "URL"\n\n'
            "  # Playlist with fast remux\n"
            '  python ytdlp_downloader.py --yes-playlist --container-strategy fast-remux "PLAYLIST_URL"\n\n'
            "  # Force MP4 (re-encode if needed)\n"
            '  python ytdlp_downloader.py --container-strategy force-mp4 "URL"\n\n'
            "  # Custom format\n"
            '  python ytdlp_downloader.py -f "bestvideo[height<=1080]+bestaudio" --container-strategy fast-remux "URL"\n\n'
            "  # Video format ID X + audio format ID Y (list IDs with -F URL first)\n"
            '  python ytdlp_downloader.py -f "137+140" "URL"   # e.g. 1080p video + m4a audio\n'
            "  # Single format ID that already has video+audio (e.g. 18 = 360p mp4)\n"
            '  python ytdlp_downloader.py -f 18 "URL"\n\n'
            "  # Disable resume\n"
            '  python ytdlp_downloader.py --no-continue "URL"\n\n'
            "  # YouTube login via cookies (yt-dlp options; OAuth no longer supported)\n"
            '  python ytdlp_downloader.py --cookies cookies.txt "URL"\n'
            '  python ytdlp_downloader.py --cookies-from-browser chrome "URL"\n\n'
            "  # Export browser cookies TO a file (no URL = export only):\n"
            '  python ytdlp_downloader.py --cookies-from-browser chrome --cookies cookies.txt\n'
            "  # Then use the file: --cookies cookies.txt \"URL\". Export includes ALL sites; protect the file.\n\n"
            "  # Output template (yt-dlp -o after URL; path + template in one):\n"
            '  python ytdlp_downloader.py "URL" -o "%(title)s [%(id)s].%(ext)s"\n'
            '  python ytdlp_downloader.py "PLAYLIST_URL" --yes-playlist -o "./out/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s"\n'
            "  Full docs: https://github.com/yt-dlp/yt-dlp#output-template\n\n"
            "  # Options that do not require a URL (passed through to yt-dlp):\n"
            "  python ytdlp_downloader.py -h             # yt-dlp help\n"
            "  python ytdlp_downloader.py --script-help  # This script's help\n"
            "  python ytdlp_downloader.py --version     # Print yt-dlp version\n\n"
            "  Cookies: two different uses\n"
            "  (A) EXPORT browser cookies TO a file (no URL; creates/overwrites the file):\n"
            "      --cookies-from-browser chrome --cookies cookies.txt\n"
            "      yt-dlp reads Chrome cookies and writes them to cookies.txt. Use that file later with (B).\n"
            "      Warning: exports cookies for ALL sites from the browser; protect the file.\n"
            "  (B) USE a cookie file FOR downloads (with URL):\n"
            "      --cookies cookies.txt \"URL\"\n"
            "      Reads cookies from the file for that download.\n"
            "  (C) USE browser cookies directly (with URL, no file):\n"
            "      --cookies-from-browser chrome \"URL\"\n\n"
            "  If you get 'Failed to decrypt with DPAPI' (e.g. Windows + Chrome), use a browser\n"
            "  extension to export cookies to a file, then --cookies FILE \"URL\". Example extension:\n"
            "  Get cookies.txt LOCALLY (Netscape format):\n"
            "  https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc\n\n"
        ),
    )
    parser.add_argument(
        "--script-help",
        action="store_true",
        help="Show this script's help (options and examples). Use -h or --help for yt-dlp help.",
    )
    parser.add_argument(
        "--check-updates",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="check_updates",
        help="Check for yt-dlp updates and stop if outdated.",
    )
    parser.add_argument(
        "--container-strategy",
        choices=["fast-remux", "best-mp4", "force-mp4"],
        default="fast-remux",
        help=(
            "Container strategy for VIDEO downloads (does not affect audio-only): "
            "'fast-remux' (default) = Only remuxes (copies streams), keeps original format if incompatible with MP4 (faster, may result in WebM/MKV). "
            "'best-mp4' = Prefers best-quality MP4-compatible formats, remux only (no conversion, fast, guarantees MP4 when available). "
            "'force-mp4' = Forces MP4 output, may re-encode incompatible codecs (slower, guarantees MP4)."
        ),
    )
    args, extra = parser.parse_known_args()

    if args.script_help:
        parser.print_help()
        return 0

    if not extra:
        parser.error("pass a URL and/or yt-dlp options (e.g. URL, -U, --version, -F URL)")

    # Let yt-dlp parse everything (URL, -F, -f, -U, ...); no argv[0] so URLs are correct.
    # Script defaults go first, so any option the user repeats later wins.
    try:
        parsed = parse_options(build_default_argv(args, extra) + extra)
    except Exception as e:  # noqa: BLE001 - yt-dlp raises assorted types on bad options
        print_error(f"Error parsing yt-dlp arguments: {e}")
        return 1

    ydl_opts = {**(parsed.ydl_opts or {}), **build_script_ydl_opts()}
    set_verbosity(ydl_opts)

    # No URLs: delegate to yt-dlp for -U, --version, cookie export, etc.
    if not parsed.urls:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "yt_dlp"] + extra,
                shell=False,
                check=False,
            )
            return result.returncode
        except FileNotFoundError:
            print_error("Error: Could not run yt-dlp (python -m yt_dlp). Ensure yt-dlp is installed.")
            return 1

    # Initial validation: check for yt-dlp updates when we have URLs; stop if outdated.
    if args.check_updates:
        print_info("Checking for yt-dlp updates...")
        outdated, update_output, is_pip_install = _run_ytdlp_update_check()
        if update_output:
            print_info(update_output)
        if outdated:
            if is_pip_install:
                try:
                    answer = input("Update yt-dlp via pip now? [y/N]: ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer in ("y", "yes"):
                    print_info("Running: pip install -U \"yt-dlp[default]\"")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]", "--no-warn-script-location"],
                        shell=False,
                        check=False,
                    )
                    if result.returncode == 0:
                        print_info("yt-dlp updated successfully. Run the script again to continue.")
                        return 0
                    print_error("Update failed. Please run: pip install -U \"yt-dlp[default]\"")
                else:
                    print_error("Script stopped. Update yt-dlp and run again, or use --no-check-updates to skip.")
            else:
                print_error("Script stopped. Update yt-dlp and run again, or use --no-check-updates to skip.")
            return 1

    check_dependencies()

    try:
        with YoutubeDL(ydl_opts) as ydl:
            url = parsed.urls[0]  # for metadata / listformats (first URL)
            # -F / listformats: yt-dlp option; list formats and exit (no download)
            if ydl_opts.get("listformats"):
                ydl.extract_info(url, download=False)
                return 0

            # Extract first to show metadata
            info = ydl.extract_info(url, download=False)
            if info is None:
                # yt-dlp already reported why through the logger.
                print_error("Could not read the URL. See the errors above.")
                return 1

            # Check if it's a playlist
            download_playlist = not ydl_opts.get("noplaylist", True)
            if "entries" in info:
                entries_list = list(info["entries"])
                playlist_count = len(entries_list)
                playlist_title = info.get("title", "Unknown Playlist")
                first_entry_title = (
                    entries_list[0].get("title", "Unknown") if entries_list else "Unknown"
                )

                if download_playlist:
                    print_info(f"Playlist: {playlist_title}")
                    print_info(f"Total videos: {playlist_count}")
                    print_info("Downloading entire playlist...")
                else:
                    title = first_entry_title  # for final "Saved" message
                    print_info(f"Warning: URL contains a playlist with {playlist_count} videos.")
                    print_info("Downloading only the first video. Use --yes-playlist to download all.")
            else:
                # Single video
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                print_info(f"Title: {title}")
                print_info(f"Duration: {duration} seconds")

            # Download (all URLs from yt-dlp). Errors during download or post-processing are
            # reported through the logger and surface here as a non-zero return code.
            retcode = ydl.download(parsed.urls)
            if retcode:
                print_error("Download failed. See the errors above.")
                return retcode

            # Prepare and print resulting filename
            try:
                postprocessors = ydl_opts.get("postprocessors", [])
                audio_pp = next(
                    (p for p in postprocessors if p.get("key") == "FFmpegExtractAudio"),
                    None,
                )
                recode_pp = next(
                    (p for p in postprocessors if p.get("key") == "FFmpegVideoConvertor"),
                    None,
                )
                if audio_pp:
                    # "best" means "keep the source codec", so the extension is unknown here.
                    codec = audio_pp.get("preferredcodec") or "best"
                    final_ext = "*" if codec == "best" else codec
                elif recode_pp:
                    # Recoding always produces the target container; remuxing may fall back
                    # to the original one, so its extension cannot be predicted here.
                    final_ext = recode_pp.get("preferedformat", "*")
                else:
                    final_ext = "*"

                if download_playlist and "entries" in info:
                    print_info("Playlist downloaded.")
                else:
                    if final_ext == "*":
                        print_info(f"Saved: {title} (check current dir for actual extension)")
                    else:
                        print_info(f"Saved: {title}.{final_ext}")
            except (AttributeError, KeyError, TypeError):
                print_info("Download completed successfully.")

        return 0
    except DownloadError as e:
        print_error(f"Download error: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 - top-level guard: report and exit non-zero
        print_error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


"""
Requirements to run this script:
  - yt_dlp: pip install "yt-dlp[default]"  (use [default] so EJS solver scripts are included for YouTube)
  - Deno (JavaScript runtime, required for YouTube and some extractors), min 2.0:
    https://docs.deno.com/runtime/getting_started/installation/
    - Windows: winget install DenoLand.Deno  OR  irm https://deno.land/install.ps1 | iex
    - Linux: curl -fsSL https://deno.land/install.sh | sh
    - macOS: brew install deno

  If you see "n challenge" / "found 0 n function possibilities" on YouTube:
  - Update: pip install -U "yt-dlp[default]"
  - Or pass: --remote-components ejs:npm  (lets yt-dlp fetch solver scripts; requires Deno/Bun)
  See: https://github.com/yt-dlp/yt-dlp/wiki/EJS

  YouTube login: OAuth is no longer supported. Use cookies (--cookies-file or --cookies).
  See: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies
"""
import argparse
import os
import shutil
import sys
from typing import Any, Dict
import platform
import subprocess
import re

from yt_dlp import YoutubeDL, parse_options
from yt_dlp.utils import DownloadError


class CustomLogger:
    """Reduce yt-dlp verbosity: only show warnings and errors."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        print(f"Warning: {msg}", flush=True)

    def error(self, msg: str) -> None:
        print(f"Error: {msg}", flush=True)


def progress_hook(d: Dict[str, Any]) -> None:
    """Print simple progress information for downloads and post-processing."""
    status = d.get("status")

    if status == "downloading":
        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")
        print(f"Downloading: {percent} at {speed}, ETA: {eta}", flush=True)

    elif status == "finished":
        print("Download finished. Starting post-processing...", flush=True)

    elif status == "processing":
        # Post-processing status
        postprocessor = d.get("postprocessor", "Unknown")
        print(f"Post-processing: {postprocessor}", flush=True)

    elif status == "error":
        print("Error occurred during processing.", flush=True)


def postprocessor_hook(d: Dict[str, Any]) -> None:
    """Hook specifically for post-processor progress."""
    status = d.get("status")
    postprocessor = d.get("postprocessor", "Processing")

    if status == "started":
        print(f"[Post-Processor] Started: {postprocessor}", flush=True)

    elif status == "processing":
        # Some post-processors provide progress info
        if "progress" in d:
            progress = d.get("progress", {})
            percent = progress.get("percent", "N/A")
            print(f"[Post-Processor] {postprocessor}: {percent}%", flush=True)
        else:
            print(f"[Post-Processor] {postprocessor} in progress...", flush=True)

    elif status == "finished":
        print(f"[Post-Processor] Completed: {postprocessor}", flush=True)


def check_tool(tool: str) -> bool:
    """
    Check if a tool (ffmpeg/ffprobe) is installed and functional.
    Validates across Windows, Linux, and macOS.
    Returns True if tool is available, False otherwise.
    """
    # Check if tool exists in PATH
    if not shutil.which(tool):
        os_name = platform.system()
        print(f"Error: {tool} is not installed.", flush=True)

        # Provide OS-specific installation instructions
        if os_name == "Windows":
            print(f"To install {tool} on Windows:", flush=True)
            print(
                "  1. Download 'ffmpeg-git-essentials.7z' from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-github",
                flush=True,
            )
            print("  2. Extract the 7z/ZIP file", flush=True)
            print(
                "  3. Copy ffmpeg.exe and ffprobe.exe from the 'bin' folder to the same directory as this script",
                flush=True,
            )
            print("  OR add the 'bin' folder to your system PATH", flush=True)
            print("  OR run: winget install ffmpeg", flush=True)
        elif os_name == "Linux":
            print(
                f"To install {tool}, run 'sudo apt install ffmpeg' (Ubuntu/Debian) or 'sudo yum install ffmpeg' (CentOS/RHEL).",
                flush=True,
            )
        elif os_name == "Darwin":  # macOS
            print(
                f"To install {tool}, run 'brew install ffmpeg' (requires Homebrew).",
                flush=True,
            )
        else:
            print(f"Please install {tool} for your operating system.", flush=True)

        return False

    # Verify the tool actually executes
    try:
        result = subprocess.run(
            [tool, "-version"], capture_output=True, text=True, timeout=10, check=False
        )

        if result.returncode != 0:
            print(f"Error: {tool} exists but failed to execute properly.", flush=True)
            return False

        # Extract and check version
        version_match = re.search(r"version\s+([\d.]+)", result.stdout)
        if version_match:
            version = version_match.group(1)
            print(f"{tool} version {version} detected.", flush=True)

            # Warn if version is too old
            major_version = int(version.split(".")[0])
            if major_version < 4:
                print(
                    f"Warning: {tool} version {version} is below 4.0. Consider upgrading for better compatibility.",
                    flush=True,
                )
        else:
            print(f"Warning: Could not determine {tool} version.", flush=True)

        return True

    except subprocess.TimeoutExpired:
        print(f"Error: {tool} command timed out.", flush=True)
        return False
    except FileNotFoundError:
        print(f"Error: {tool} not found in PATH.", flush=True)
        return False
    except Exception as e:
        print(f"Error: Unexpected error checking {tool}: {e}", flush=True)
        return False


def check_dependencies() -> None:
    """Ensure ffmpeg and ffprobe are installed and functional."""
    os_name = platform.system()
    print(f"Operating system detected: {os_name}", flush=True)

    ffmpeg_ok = check_tool("ffmpeg")
    ffprobe_ok = check_tool("ffprobe")

    if not ffmpeg_ok or not ffprobe_ok:
        print(
            "Error: Required dependencies are missing. Please install them to proceed.",
            flush=True,
        )
        sys.exit(1)

    print("All dependencies validated successfully.", flush=True)


def build_ydl_opts(args: argparse.Namespace) -> Dict[str, Any]:
    """Build default yt-dlp options. Use extra args (e.g. -F, -f, -x) for yt-dlp options."""
    # Video: container strategy; format/audio/playlist/resume come from extra if passed
    if args.container_strategy == "best-mp4":
        format_str = (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
            "bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio[ext=m4a]"
        )
    else:
        format_str = "bestvideo+bestaudio/best"

    if args.container_strategy == "force-mp4":
        postprocessors = [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
        ]
    else:
        postprocessors = [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
        ]

    # Default: current dir. Override with yt-dlp -o in extra (path + template).
    outtmpl = os.path.join(".", "%(title)s.%(ext)s")
    ydl_opts: Dict[str, Any] = {
        "format": format_str,
        "outtmpl": outtmpl,
        "logger": CustomLogger(),
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "postprocessors": postprocessors,
        "noplaylist": True,  # override with --yes-playlist in extra to download playlists
        "continuedl": True,
        "nooverwrites": False,
    }
    return ydl_opts


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
            '  python ytdlp_downloader.py -x --audio-format mp3 --audio-quality 192 "URL" -o "./downloads/%(title)s.%(ext)s"\n\n'
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

    # Let yt-dlp parse all arguments (URL, -F, -f, -U, etc.); no argv[0] so URLs are correct
    try:
        parsed = parse_options(extra)
    except Exception as e:
        print(f"Error parsing yt-dlp arguments: {e}", flush=True)
        return 1

    ydl_opts = {**build_ydl_opts(args), **(parsed.ydl_opts or {})}

    # No URLs: delegate to yt-dlp for -U, --version, cookie export, etc.
    if not parsed.urls:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "yt_dlp"] + extra,
                shell=False,
            )
            return result.returncode
        except FileNotFoundError:
            print("Error: Could not run yt-dlp (python -m yt_dlp). Ensure yt-dlp is installed.", flush=True)
            return 1

    # Initial validation: check for yt-dlp updates when we have URLs; stop if outdated.
    if args.check_updates:
        print("Checking for yt-dlp updates...", flush=True)
        outdated, update_output, is_pip_install = _run_ytdlp_update_check()
        if update_output:
            print(update_output, flush=True)
        if outdated:
            if is_pip_install:
                try:
                    answer = input("Update yt-dlp via pip now? [y/N]: ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer in ("y", "yes"):
                    print("Running: pip install -U \"yt-dlp[default]\"", flush=True)
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]", "--no-warn-script-location"],
                        shell=False,
                    )
                    if result.returncode == 0:
                        print("yt-dlp updated successfully. Run the script again to continue.", flush=True)
                        return 0
                    print("Update failed. Please run: pip install -U \"yt-dlp[default]\"", flush=True)
                else:
                    print("Script stopped. Update yt-dlp and run again, or use --no-check-updates to skip.", flush=True)
            else:
                print("Script stopped. Update yt-dlp and run again, or use --no-check-updates to skip.", flush=True)
            return 1
        ydl_opts["warn_when_outdated"] = True
    else:
        ydl_opts["warn_when_outdated"] = False

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
                    print(f"Playlist: {playlist_title}", flush=True)
                    print(f"Total videos: {playlist_count}", flush=True)
                    print("Downloading entire playlist...", flush=True)
                else:
                    title = first_entry_title  # for final "Saved" message
                    print(
                        f"Warning: URL contains a playlist with {playlist_count} videos.",
                        flush=True,
                    )
                    print(
                        "Downloading only the first video. Use --yes-playlist to download all.",
                        flush=True,
                    )
            else:
                # Single video
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                print(f"Title: {title}", flush=True)
                print(f"Duration: {duration} seconds", flush=True)

            # Download (all URLs from yt-dlp)
            ydl.download(parsed.urls)

            # Prepare and print resulting filename
            try:
                postprocessors = ydl_opts.get("postprocessors", [])
                audio_pp = next(
                    (p for p in postprocessors if p.get("key") == "FFmpegExtractAudio"),
                    None,
                )
                if audio_pp:
                    final_ext = audio_pp.get("preferredcodec", "mp3")
                else:
                    final_ext = (
                        "mp4"
                        if args.container_strategy in ("force-mp4", "best-mp4")
                        else "*"
                    )

                if download_playlist and "entries" in info:
                    print("Playlist downloaded.", flush=True)
                else:
                    if final_ext == "*":
                        print(
                            f"Saved: {title} (check current dir for actual extension)",
                            flush=True,
                        )
                    else:
                        print(f"Saved: {title}.{final_ext}", flush=True)
            except Exception:
                print("Download completed successfully.", flush=True)

        return 0
    except DownloadError as e:
        print(f"Download error: {e}", flush=True)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


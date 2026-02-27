"""
Requirements to run this script:
  - yt_dlp: pip install yt-dlp

  - Deno (JavaScript runtime, required for some extractors):
    https://docs.deno.com/runtime/getting_started/installation/
    - Windows: winget install DenoLand.Deno  OR  irm https://deno.land/install.ps1 | iex
    - Linux: curl -fsSL https://deno.land/install.sh | sh
    - macOS: brew install deno
"""
import argparse
import os
import shutil
import sys
from typing import Any, Dict
import platform
import subprocess
import re

from yt_dlp import YoutubeDL
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
    except subprocess.CalledProcessError as e:
        print(f"Error: {tool} execution failed: {e}", flush=True)
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


def list_formats(url: str) -> int:
    """List all available formats for the given URL."""
    print(f"Fetching available formats for: {url}", flush=True)
    print("-" * 80, flush=True)

    ydl_opts = {
        "listformats": True,  # This makes yt-dlp print formats and exit
        "quiet": False,  # Show output
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
        return 0
    except Exception as e:
        print(f"Error listing formats: {e}", flush=True)
        return 1


def build_ydl_opts(args: argparse.Namespace) -> Dict[str, Any]:
    """Build yt-dlp options based on args."""
    is_audio_only = args.audio_only is not None

    if is_audio_only:
        # Audio-only downloads always use FFmpegExtractAudio
        format_str = args.format or "bestaudio/best"
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": args.audio_only,  # 'mp3' or 'm4a'
                "preferredquality": str(args.audio_quality),  # e.g., '192'
            }
        ]
    else:
        # Video downloads: apply container strategy
        if args.container_strategy == "best-mp4":
            # Prefer MP4-compatible formats (H.264/AAC), remux only - no conversion
            format_str = args.format or (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                "bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio[ext=m4a]"
            )
        else:
            format_str = args.format or "bestvideo+bestaudio/best"

        if args.container_strategy == "force-mp4":
            # Force conversion to MP4 (may re-encode, slower but guarantees MP4)
            postprocessors = [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ]
        elif args.container_strategy in ("fast-remux", "best-mp4"):
            # Fast remux (only copies streams). best-mp4 prefers MP4-compatible formats.
            postprocessors = [
                {
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": "mp4",
                }
            ]
        else:
            # This should never happen due to argparse choices validation
            raise ValueError(
                f"Invalid container strategy: '{args.container_strategy}'. "
                f"Expected 'fast-remux', 'best-mp4', or 'force-mp4'."
            )

    outtmpl = (
        os.path.join(args.output_dir, args.output_name)
        if args.output_name
        else os.path.join(args.output_dir, "%(title)s.%(ext)s")
    )
    ydl_opts: Dict[str, Any] = {
        "format": format_str,
        "outtmpl": outtmpl,
        "logger": CustomLogger(),
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],  # Hook for post-processor progress
        "postprocessors": postprocessors,
        "noplaylist": not args.playlist,  # If --playlist flag present, download playlist
    }

    # Resume support (enabled by default)
    if not args.no_resume:
        ydl_opts["continuedl"] = True  # continue partial downloads if possible
        ydl_opts["nooverwrites"] = False  # allow resuming without forcing overwrite

    return ydl_opts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download videos or audio using yt-dlp with cross-platform support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # List available formats\n"
            '  python video_downloader.py -F "https://www.youtube.com/watch?v=VIDEO_ID"\n\n'
            "  # Basic video download (single video, best-mp4 default)\n"
            '  python video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"\n\n'
            "  # Download entire playlist\n"
            '  python video_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxxxxx"\n\n'
            "  # Audio-only download\n"
            '  python video_downloader.py --audio-only mp3 --audio-quality 192 "URL" -o ./downloads\n\n'
            "  # Fast remux strategy (keeps WebM if incompatible, much faster)\n"
            '  python video_downloader.py --container-strategy fast-remux "URL"\n\n'
            "  # Best MP4 without conversion (prefers MP4-compatible formats, remux only)\n"
            '  python video_downloader.py --container-strategy best-mp4 "URL"\n\n'
            "  # Download playlist with fast remux\n"
            '  python video_downloader.py --playlist --container-strategy fast-remux "PLAYLIST_URL"\n\n'
            "  # Force MP4 strategy (guarantees MP4, may be slower)\n"
            '  python video_downloader.py --container-strategy force-mp4 "URL"\n\n'
            "  # Custom format with fast remux\n"
            '  python video_downloader.py -f "bestvideo[height<=1080]+bestaudio" --container-strategy fast-remux "URL"\n\n'
            "  # Disable resume\n"
            '  python video_downloader.py --no-resume "URL"\n\n'
        ),
    )
    parser.add_argument("url", help="Video or playlist URL to download")
    parser.add_argument(
        "-F",
        "--list-formats",
        action="store_true",
        help="List all available formats and exit (equivalent to yt-dlp -F)",
    )
    parser.add_argument(
        "-o", "--output-dir", default=".", dest="output_dir", help="Output directory (default: current)"
    )
    parser.add_argument(
        "-O",
        "--output-name",
        metavar="TEMPLATE",
        help="Output filename template (e.g. %%(title)s.%%(ext)s or myfile.%%(ext)s). "
        "Placeholders: https://github.com/yt-dlp/yt-dlp#output-template",
    )
    parser.add_argument(
        "-f",
        "--format",
        help="Format string (video default: bestvideo+bestaudio/best; audio default: bestaudio/best)",
    )
    parser.add_argument(
        "--audio-only", choices=["mp3", "m4a"], help="Download audio only as mp3 or m4a"
    )
    parser.add_argument(
        "--audio-quality",
        type=int,
        default=192,
        help="Audio quality in kbps (default: 192)",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="Disable resume support"
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Download entire playlist if URL contains one (default: download single video only)",
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

    args = parser.parse_args()

    # If user wants to list formats, do that and exit (no need to check dependencies)
    if args.list_formats:
        return list_formats(args.url)

    check_dependencies()
    os.makedirs(args.output_dir, exist_ok=True)

    ydl_opts = build_ydl_opts(args)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Extract first to show metadata
            info = ydl.extract_info(args.url, download=False)

            # Check if it's a playlist
            if "entries" in info:
                # It's a playlist
                playlist_title = info.get("title", "Unknown Playlist")
                playlist_count = len(list(info["entries"]))

                if args.playlist:
                    print(f"Playlist: {playlist_title}", flush=True)
                    print(f"Total videos: {playlist_count}", flush=True)
                    print("Downloading entire playlist...", flush=True)
                else:
                    print(
                        f"Warning: URL contains a playlist with {playlist_count} videos.",
                        flush=True,
                    )
                    print(
                        "Downloading only the first video. Use --playlist to download all.",
                        flush=True,
                    )
            else:
                # Single video
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                print(f"Title: {title}", flush=True)
                print(f"Duration: {duration} seconds", flush=True)

            # Download
            ydl.download([args.url])

            # Prepare and print resulting filename
            try:
                if args.audio_only:
                    final_ext = args.audio_only
                else:
                    # With fast-remux, extension may vary (mp4, webm, mkv)
                    # With force-mp4 and best-mp4, it should be mp4
                    final_ext = (
                        "mp4"
                        if args.container_strategy in ("force-mp4", "best-mp4")
                        else "*"
                    )

                if args.playlist and "entries" in info:
                    print(f"Playlist downloaded to: {args.output_dir}/", flush=True)
                else:
                    if final_ext == "*":
                        final_path = os.path.join(args.output_dir, f"{title}.*")
                        print(
                            f"Saved to: {final_path} (check output directory for actual extension)",
                            flush=True,
                        )
                    else:
                        final_path = os.path.join(args.output_dir, f"{title}.{final_ext}")
                        print(f"Saved to: {final_path}", flush=True)
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


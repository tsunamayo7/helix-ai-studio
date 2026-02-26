"""
generate_demo_gif.py - スクリーンショットからデモGIF/MP4を生成

Usage:
    python scripts/generate_demo_gif.py
    python scripts/generate_demo_gif.py --input-dir screenshots/ --output demo.gif --fps 1
    python scripts/generate_demo_gif.py --format mp4 --output demo.mp4
"""

import subprocess
import argparse
import sys
from pathlib import Path


FFMPEG_PATHS = ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"]


def find_ffmpeg() -> str:
    """ffmpegの実行パスを検索して返す"""
    for path in FFMPEG_PATHS:
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return path
        except FileNotFoundError:
            continue
    return ""


def check_ffmpeg():
    """ffmpegが利用可能か確認"""
    return bool(find_ffmpeg())


def generate_gif(input_dir: Path, output: str, fps: int, ffmpeg: str = "ffmpeg"):
    """2パスGIF生成（高品質）"""
    images = sorted(input_dir.glob("*.png"))
    if not images:
        print(f"ERROR: No PNG files found in {input_dir}")
        sys.exit(1)

    # ffmpeg concat用ファイルリスト
    concat_file = input_dir / "_filelist.txt"
    duration = max(1.0 / fps, 0.5)
    with open(concat_file, "w", encoding="utf-8") as f:
        for img in images:
            f.write(f"file '{img.resolve()}'\n")
            f.write(f"duration {duration}\n")
        # 最後のフレームを繰り返す（ffmpeg仕様）
        f.write(f"file '{images[-1].resolve()}'\n")

    palette = input_dir / "_palette.png"

    try:
        # Pass 1: パレット生成
        subprocess.run([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-vf", "fps=10,scale=800:-1:flags=lanczos,palettegen",
            str(palette)
        ], check=True, capture_output=True, text=True)

        # Pass 2: GIF生成
        subprocess.run([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(palette),
            "-lavfi", "fps=10,scale=800:-1:flags=lanczos [x]; [x][1:v] paletteuse",
            output
        ], check=True, capture_output=True, text=True)

        print(f"Generated: {output} ({len(images)} frames)")
    finally:
        concat_file.unlink(missing_ok=True)
        palette.unlink(missing_ok=True)


def generate_mp4(input_dir: Path, output: str, fps: int, ffmpeg: str = "ffmpeg"):
    """MP4動画生成"""
    images = sorted(input_dir.glob("*.png"))
    if not images:
        print(f"ERROR: No PNG files found in {input_dir}")
        sys.exit(1)

    concat_file = input_dir / "_filelist.txt"
    duration = max(1.0 / fps, 0.5)
    with open(concat_file, "w", encoding="utf-8") as f:
        for img in images:
            f.write(f"file '{img.resolve()}'\n")
            f.write(f"duration {duration}\n")
        f.write(f"file '{images[-1].resolve()}'\n")

    try:
        subprocess.run([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-vf", "scale=800:-1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output
        ], check=True, capture_output=True, text=True)

        print(f"Generated: {output} ({len(images)} frames)")
    finally:
        concat_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Demo GIF/MP4 generator")
    parser.add_argument(
        "--input-dir", default="screenshots",
        help="Input directory with PNG screenshots (default: screenshots/)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output file path (default: demo.gif or demo.mp4)"
    )
    parser.add_argument("--fps", type=int, default=1, help="Frames per second (default: 1)")
    parser.add_argument(
        "--format", choices=["gif", "mp4"], default="gif",
        help="Output format (default: gif)"
    )
    args = parser.parse_args()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg not found. Install with: winget install --id Gyan.FFmpeg")
        sys.exit(1)

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}")
        sys.exit(1)

    output = args.output or f"demo.{args.format}"

    if args.format == "gif":
        generate_gif(input_dir, output, args.fps, ffmpeg)
    else:
        generate_mp4(input_dir, output, args.fps, ffmpeg)


if __name__ == "__main__":
    main()

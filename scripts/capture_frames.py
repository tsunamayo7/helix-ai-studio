"""
連続フレームキャプチャスクリプト（win32gui直接版）
Helix Pilotに依存せず、直接Windowsスクリーンショットを取得してGIFを生成する
Usage: python scripts/capture_frames.py --name <name> --duration <sec> --fps <fps> --window <title>
"""
import argparse
import os
import sys
import time
from pathlib import Path


def find_window(title_keyword):
    import win32gui
    result = []
    def cb(hwnd, _):
        t = win32gui.GetWindowText(hwnd)
        if title_keyword.lower() in t.lower() and win32gui.IsWindowVisible(hwnd):
            result.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return result[0] if result else None


def capture_window(hwnd, save_path):
    """mss（スクリーン直接キャプチャ）を使ってウィンドウ領域をキャプチャ"""
    import win32gui
    import ctypes
    import mss
    from PIL import Image

    # ウィンドウの画面上の座標を取得
    rect = win32gui.GetWindowRect(hwnd)
    x, y, x2, y2 = rect
    if x2 - x <= 0 or y2 - y <= 0:
        return False

    with mss.mss() as sct:
        monitor = {"top": y, "left": x, "width": x2 - x, "height": y2 - y}
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.save(save_path)

    return True


def capture_frames(name, duration, fps, window_title, frame_dir):
    interval = 1.0 / fps
    frames = []
    Path(frame_dir).mkdir(parents=True, exist_ok=True)

    hwnd = find_window(window_title)
    if not hwnd:
        print(f"[capture] Window not found: {window_title}", flush=True)
        return []

    print(f"[capture] Starting: {name}, {duration}s, {fps}fps, hwnd={hwnd}", flush=True)
    start_time = time.time()
    end_time = start_time + duration
    frame_idx = 0

    while time.time() < end_time:
        frame_path = str(Path(frame_dir) / f"{name}_f{frame_idx:04d}.png")
        try:
            ok = capture_window(hwnd, frame_path)
            if ok:
                frames.append(frame_path)
                print(f"[capture] frame {frame_idx:04d}", flush=True)
            else:
                print(f"[capture] frame {frame_idx:04d} failed (empty)", flush=True)
        except Exception as e:
            print(f"[capture] frame {frame_idx:04d} error: {e}", flush=True)

        frame_idx += 1
        next_tick = start_time + frame_idx * interval
        sleep_time = next_tick - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

    print(f"[capture] Done. {len(frames)} frames.", flush=True)
    return frames


def make_gif(frames, output_path, fps, max_width=900):
    from PIL import Image
    images = []
    for f in frames:
        try:
            img = Image.open(f).convert("RGB")
            if img.width > max_width:
                ratio = max_width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)
            images.append(img)
        except Exception as e:
            print(f"[gif] skip {f}: {e}", flush=True)

    if not images:
        print("[gif] No images!", flush=True)
        return False

    duration_ms = int(1000 / fps)
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=duration_ms,
        optimize=False
    )
    size_kb = Path(output_path).stat().st_size // 1024
    print(f"[gif] Saved: {output_path} ({len(images)} frames, {size_kb}KB)", flush=True)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--fps", type=float, default=2)
    parser.add_argument("--window", default="Helix AI Studio")
    parser.add_argument("--frame-dir", default=None)
    parser.add_argument("--gif-out", default=None)
    parser.add_argument("--max-width", type=int, default=900)
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    os.chdir(base_dir)

    frame_dir = args.frame_dir or str(base_dir / "data" / "helix_pilot_screenshots" / f"frames_{args.name}")
    gif_out = args.gif_out or str(base_dir / "demo_captures" / f"{args.name}.gif")

    frames = capture_frames(
        name=args.name,
        duration=args.duration,
        fps=args.fps,
        window_title=args.window,
        frame_dir=frame_dir
    )

    if frames:
        make_gif(frames, gif_out, args.fps, args.max_width)
    else:
        print("[capture] No frames captured.", flush=True)

"""Demo recording helper for Helix AI Studio.
Provides functions for capturing screenshots, recording screen sequences, and creating GIFs/MP4s.
"""
import time
import os
from pathlib import Path
from PIL import ImageGrab, Image
import pyautogui
import pygetwindow as gw

DEMO_DIR = Path(__file__).parent.parent / "demo_captures"
DEMO_DIR.mkdir(exist_ok=True)

def get_helix_window():
    """Find the main Helix AI Studio window."""
    wins = gw.getWindowsWithTitle('Helix AI Studio')
    for w in wins:
        if w.width > 500 and w.height > 400:
            return w
    return None

def activate_window(win=None):
    """Bring Helix window to foreground."""
    if win is None:
        win = get_helix_window()
    if win:
        win.activate()
        time.sleep(0.3)
    return win

def screenshot(name, win=None):
    """Take a named screenshot of the Helix window."""
    if win is None:
        win = get_helix_window()
    if not win:
        print("Window not found!")
        return None
    activate_window(win)
    time.sleep(0.2)
    img = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
    path = DEMO_DIR / f"{name}.png"
    img.save(str(path))
    print(f"Screenshot: {path.name} ({img.size[0]}x{img.size[1]})")
    return path

def click(x_offset, y_offset, win=None):
    """Click at offset from window top-left."""
    if win is None:
        win = get_helix_window()
    if not win:
        return
    activate_window(win)
    pyautogui.click(win.left + x_offset, win.top + y_offset)
    time.sleep(0.3)

def type_text(text, interval=0.03):
    """Type text with realistic speed."""
    pyautogui.typewrite(text, interval=interval) if text.isascii() else _type_unicode(text)

def _type_unicode(text):
    """Type unicode text (Japanese etc) via clipboard."""
    import pyperclip
    old = pyperclip.paste()
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyperclip.copy(old)

def record_sequence(name, duration_sec=10, fps=5, win=None):
    """Record a sequence of screenshots at given fps for duration."""
    if win is None:
        win = get_helix_window()
    if not win:
        print("Window not found!")
        return []

    activate_window(win)
    frames = []
    interval = 1.0 / fps
    start = time.time()
    frame_num = 0

    print(f"Recording '{name}' for {duration_sec}s at {fps}fps...")
    while time.time() - start < duration_sec:
        t0 = time.time()
        img = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
        frames.append(img)
        frame_num += 1
        elapsed = time.time() - t0
        if elapsed < interval:
            time.sleep(interval - elapsed)

    print(f"Captured {len(frames)} frames")
    return frames

def save_gif(frames, name, fps=5, optimize=True):
    """Save frames as animated GIF."""
    if not frames:
        return None
    path = DEMO_DIR / f"{name}.gif"
    duration_ms = int(1000 / fps)

    # Resize for reasonable GIF size
    target_w = min(frames[0].size[0], 1200)
    scale = target_w / frames[0].size[0]
    target_h = int(frames[0].size[1] * scale)

    resized = [f.resize((target_w, target_h), Image.LANCZOS) for f in frames]

    resized[0].save(
        str(path),
        save_all=True,
        append_images=resized[1:],
        duration=duration_ms,
        loop=0,
        optimize=optimize
    )
    size_kb = path.stat().st_size / 1024
    print(f"GIF saved: {path.name} ({len(frames)} frames, {size_kb:.0f}KB)")
    return path

def save_mp4(frames, name, fps=5):
    """Save frames as MP4 using opencv."""
    import cv2
    import numpy as np

    if not frames:
        return None
    path = DEMO_DIR / f"{name}.mp4"

    # Resize
    target_w = min(frames[0].size[0], 1920)
    scale = target_w / frames[0].size[0]
    target_h = int(frames[0].size[1] * scale)
    # Ensure even dimensions for codec
    target_w = target_w if target_w % 2 == 0 else target_w - 1
    target_h = target_h if target_h % 2 == 0 else target_h - 1

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(path), fourcc, fps, (target_w, target_h))

    for f in frames:
        resized = f.resize((target_w, target_h), Image.LANCZOS)
        frame_bgr = cv2.cvtColor(np.array(resized), cv2.COLOR_RGB2BGR)
        out.write(frame_bgr)

    out.release()
    size_kb = path.stat().st_size / 1024
    print(f"MP4 saved: {path.name} ({len(frames)} frames, {size_kb:.0f}KB)")
    return path

def wait_for_response(timeout=120, check_interval=2, win=None):
    """Wait until the chat response appears (status bar changes from busy)."""
    print(f"Waiting for response (max {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(check_interval)
    print(f"Wait complete ({time.time()-start:.0f}s)")


"""
撮影ヘルパースクリプト
DPI-aware screenshots for Helix AI Studio
"""
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import pyautogui, win32gui, win32con, time, sys, os
from PIL import Image

def find_helix_hwnd():
    """Helix AI Studio のメインウィンドウハンドルを取得"""
    results = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            try:
                t = win32gui.GetWindowText(hwnd)
                if 'Helix AI Studio v' in t:
                    r = win32gui.GetWindowRect(hwnd)
                    results.append((hwnd, t, r))
            except:
                pass
    win32gui.EnumWindows(cb, None)
    if not results:
        raise RuntimeError("Helix AI Studio window not found")
    return results[0][0]

def bring_to_front(hwnd):
    """ウィンドウをフォアグラウンドに"""
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.1)
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    time.sleep(0.2)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)

def screenshot_window(hwnd, save_path, crop_region=None):
    """ウィンドウ全体のスクリーンショットを撮影して保存"""
    rect = win32gui.GetWindowRect(hwnd)
    x1 = max(0, rect[0])
    y1 = max(0, rect[1])
    w = rect[2] - x1
    h = rect[3] - y1

    img = pyautogui.screenshot(region=(x1, y1, w, h))

    if crop_region:
        img = img.crop(crop_region)

    img.save(save_path)
    return img

def screenshot_preview(hwnd, save_path, max_width=1600):
    """プレビュー用にリサイズしたスクリーンショット"""
    rect = win32gui.GetWindowRect(hwnd)
    x1 = max(0, rect[0])
    y1 = max(0, rect[1])
    w = rect[2] - x1
    h = rect[3] - y1

    img = pyautogui.screenshot(region=(x1, y1, w, h))
    preview = img.copy()
    preview.thumbnail((max_width, max_width), Image.LANCZOS)
    preview.save(save_path)
    return img, preview

def click_tab(hwnd, tab_name):
    """タブ名に対応する位置をクリック"""
    # Physical pixel positions of tab centers (from 3851x2171 screenshot)
    tab_positions = {
        'mixAI':            (90, 45),
        'cloudAI':          (260, 45),
        'localAI':          (430, 45),
        'History':          (600, 45),
        'RAG':              (755, 45),
        'Virtual Desktop':  (940, 45),
        'settings':         (1130, 45),
    }

    if tab_name not in tab_positions:
        raise ValueError(f"Unknown tab: {tab_name}")

    rect = win32gui.GetWindowRect(hwnd)
    x1 = max(0, rect[0])
    y1 = max(0, rect[1])

    tx, ty = tab_positions[tab_name]
    abs_x = x1 + tx
    abs_y = y1 + ty

    # Use SendInput for reliable clicking
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ('dx', ctypes.c_long), ('dy', ctypes.c_long),
            ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
            ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
        ]
    class INPUT(ctypes.Structure):
        _fields_ = [('type', ctypes.c_ulong), ('mi', MOUSEINPUT)]

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    nx = int(abs_x * 65536 / screen_w)
    ny = int(abs_y * 65536 / screen_h)
    extra = ctypes.c_ulong(0)

    for flags in [MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                  MOUSEEVENTF_LEFTUP | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE]:
        inp = INPUT()
        inp.type = 0
        inp.mi = MOUSEINPUT(nx, ny, 0, flags, 0, ctypes.pointer(extra))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.05)

    time.sleep(0.5)


if __name__ == "__main__":
    hwnd = find_helix_hwnd()
    bring_to_front(hwnd)

    action = sys.argv[1] if len(sys.argv) > 1 else "screenshot"

    if action == "screenshot":
        out = sys.argv[2] if len(sys.argv) > 2 else "test_screenshot.png"
        img = screenshot_window(hwnd, out)
        print(f"Saved: {out} ({img.size})")

    elif action == "tab":
        tab = sys.argv[2]
        click_tab(hwnd, tab)
        time.sleep(0.5)
        out = sys.argv[3] if len(sys.argv) > 3 else f"tab_{tab}.png"
        img = screenshot_window(hwnd, out)
        print(f"Tab {tab} -> {out} ({img.size})")

    elif action == "preview":
        out = sys.argv[2] if len(sys.argv) > 2 else "preview.png"
        _, preview = screenshot_preview(hwnd, out)
        print(f"Preview: {out} ({preview.size})")

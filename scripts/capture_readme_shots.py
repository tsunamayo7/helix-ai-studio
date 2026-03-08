"""
README用スクリーンショット撮影スクリプト
v12.8.0 8タブ構成の全タブを撮影し docs/demo/best/README/ に保存する
"""
import ctypes
import sys
import time
import os
from pathlib import Path

# DPI Awareness = Per-Monitor V2 (physical pixel coords)
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

import pyautogui
import pygetwindow as gw
from PIL import Image

pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "demo" / "best" / "README"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_TITLE = "Helix AI Studio"

def find_window():
    wins = gw.getWindowsWithTitle(WINDOW_TITLE)
    candidates = [w for w in wins if w.width > 100 and w.height > 100]
    if not candidates:
        all_wins = gw.getAllWindows()
        candidates = [w for w in all_wins
                      if WINDOW_TITLE.lower() in w.title.lower()
                      and w.width > 100 and w.height > 100]
    if not candidates:
        raise RuntimeError(f"Window not found: {WINDOW_TITLE}")
    return candidates[0]

def activate_and_screenshot(win, name, wait=1.5):
    """ウィンドウをアクティブにしてスクリーンショットを撮影"""
    win.activate()
    time.sleep(0.3)
    # ウィンドウ領域のスクリーンショット
    img = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
    # 1920幅にリサイズ
    if img.width > 1920:
        ratio = 1920 / img.width
        new_w = 1920
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    path = OUTPUT_DIR / f"{name}.png"
    img.save(str(path))
    print(f"  Saved: {path} ({img.width}x{img.height})")
    return path

def click_tab(win, tab_x_offset, tab_y_offset=50):
    """ウィンドウ相対座標でタブをクリック"""
    abs_x = win.left + tab_x_offset
    abs_y = win.top + tab_y_offset
    win.activate()
    time.sleep(0.3)
    pyautogui.click(abs_x, abs_y)
    time.sleep(1.5)

def main():
    print("=== README Screenshot Capture v12.8.0 ===\n")
    print("Finding window...")
    win = find_window()
    print(f"Window: {win.title}")
    print(f"  Position: left={win.left}, top={win.top}")
    print(f"  Size: {win.width}x{win.height}")

    # タブの物理X座標（ウィンドウ相対、scale=2.0115想定）
    # 物理ピクセルでの位置。スクリーンショット座標×2.0115でクリック座標
    # v12.8.0 8タブ構成: mixAI, soloAI, CloudAI設定, Ollama設定,
    #                      History, RAG, Virtual Desktop, 一般設定
    #
    # ウィンドウ幅が約3860px (physical) の場合、
    # タブバーの実測Y中心 ≈ 50px (physical), 物理タブ幅 ≈ 460px
    TAB_Y = 50  # 物理ピクセル、ウィンドウ相対

    # 各タブの物理X中心（ウィンドウ相対）
    # スクリーンショット(1920px)上の位置を × scale_factor(≈2.0115) で算出
    # 実測: mixAI≈x38px → 38*2.01=76, soloAI≈x115→231, CloudAI設定≈x210→422, etc.
    tabs = [
        # (名前, 物理X中心, スクリーンショット保存名)
        ("mixAI",         76,  "readme_01_mixai_main"),
        ("soloAI_cloud", 231,  "readme_02_soloai_unified_cloud"),
        ("soloAI_ollama", 231, "readme_03_soloai_unified_ollama"),  # 後でモデル切替
        ("CloudAI設定",   422,  "readme_04_cloud_settings"),
        ("Ollama設定",    600,  "readme_05_ollama_settings"),
        ("History",       775,  "readme_06_history"),
        ("RAG",           935,  "readme_07_rag"),
        ("VD",           1115,  "readme_08_virtual_desktop"),
        ("一般設定",      1340,  "readme_09_general_settings"),
    ]

    # まず全タブを一周して座標を確認
    print("\n--- Phase 1: Tab coordinate calibration ---")
    print("Clicking mixAI tab...")
    click_tab(win, 76, TAB_Y)
    activate_and_screenshot(win, "calibration_mixai")

    print("\nCalibration shot saved. Check calibration_mixai.png")
    print("If the tab is correct, the script will continue.")
    print()

    # 本番撮影
    print("--- Phase 2: Full capture ---\n")

    # 1. mixAI
    print("[1/9] mixAI tab")
    click_tab(win, tabs[0][1], TAB_Y)
    activate_and_screenshot(win, tabs[0][2])

    # 2. soloAI (Cloud model)
    print("[2/9] soloAI tab (Cloud model)")
    click_tab(win, tabs[1][1], TAB_Y)
    activate_and_screenshot(win, tabs[1][2])

    # 3. soloAI (Ollama model) - 同じタブ、モデルを切り替える必要あり
    print("[3/9] soloAI tab (Ollama model) - same tab, different model")
    # モデルコンボボックスをクリックして変更は手動で行うため、同じ状態で撮影
    activate_and_screenshot(win, tabs[2][2])

    # 4. CloudAI設定
    print("[4/9] CloudAI設定 tab")
    click_tab(win, tabs[3][1], TAB_Y)
    activate_and_screenshot(win, tabs[3][2])

    # 5. Ollama設定
    print("[5/9] Ollama設定 tab")
    click_tab(win, tabs[4][1], TAB_Y)
    activate_and_screenshot(win, tabs[4][2])

    # 6. History
    print("[6/9] History tab")
    click_tab(win, tabs[5][1], TAB_Y)
    activate_and_screenshot(win, tabs[5][2])

    # 7. RAG
    print("[7/9] RAG tab")
    click_tab(win, tabs[6][1], TAB_Y)
    activate_and_screenshot(win, tabs[6][2])

    # 8. Virtual Desktop
    print("[8/9] Virtual Desktop tab")
    click_tab(win, tabs[7][1], TAB_Y)
    activate_and_screenshot(win, tabs[7][2])

    # 9. 一般設定
    print("[9/9] 一般設定 tab")
    click_tab(win, tabs[8][1], TAB_Y)
    activate_and_screenshot(win, tabs[8][2])

    print(f"\n=== Done! All screenshots saved to: {OUTPUT_DIR} ===")

    # 結果一覧
    files = list(OUTPUT_DIR.glob("readme_*.png"))
    files.sort()
    print(f"\nCaptured {len(files)} files:")
    for f in files:
        size = f.stat().st_size
        print(f"  {f.name}: {size:,} bytes")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helix AI Studio Demo Video Recording Script v3
pywinauto + clipboard approach (4K / 200% DPI 対応)

Usage:
  python scripts/record_demo_videos.py cloudai_jp
  python scripts/record_demo_videos.py all
  python scripts/record_demo_videos.py webui
"""

import subprocess
import time
import os
import sys
import win32clipboard
import pyautogui
from pywinauto import Application

# ── Constants ────────────────────────────────────────────────────────────────
CF_UNICODETEXT = 13
HELIX_DIR  = r"C:\Users\tomot\Desktop\開発環境\生成AIアプリ\Helix AI Studio"
OUTPUT_DIR = os.path.join(HELIX_DIR, r"docs\demo\20260301")
WINDOW     = "Helix AI Studio v11.9.4"
WEBUI_URL  = "http://localhost:8500"

# Known physical coordinates (UIA-confirmed, 4K 200% DPI)
# TabItem centers
TAB_CENTERS = {
    "mixAI":   (69, 61),
    "cloudAI": (216, 61),
    "localAI": (366, 61),
    "History": (511, 61),
    "RAG":     (654, 61),
}
# Language button centers
LANG_CENTERS = {
    "JP": (3683, 67),   # 日本語
    "EN": (3780, 67),   # English
}
# Send button center
SEND_BTN = (2478, 2014)

pyautogui.FAILSAFE = False  # 4K環境でフェイルセーフ無効

# ── Logging ──────────────────────────────────────────────────────────────────

def log(msg):
    """Safe print for Windows console (cp932)"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())

# ── pywinauto helpers ────────────────────────────────────────────────────────

def get_window():
    """pywinauto でアプリウィンドウを取得"""
    app = Application(backend='uia').connect(title_re='Helix AI Studio.*', timeout=10)
    return app.top_window()

def find_main_input(win):
    """メイン入力フィールドを返す (L<100, T>1500)"""
    for e in win.descendants(control_type='Edit'):
        try:
            r = e.rectangle()
            if r.left < 100 and r.top > 1500:
                return e
        except Exception:
            pass
    return None

def find_tab(win, tab_keyword):
    """TabItem を window_text で検索"""
    for t in win.descendants(control_type='TabItem'):
        try:
            if tab_keyword.lower() in t.window_text().lower():
                return t
        except Exception:
            pass
    return None

def find_button(win, keyword):
    """Button を window_text で部分検索"""
    for b in win.descendants(control_type='Button'):
        try:
            if keyword.lower() in b.window_text().lower():
                return b
        except Exception:
            pass
    return None

# ── Clipboard paste ──────────────────────────────────────────────────────────

def paste_to_input(win, text):
    """
    1. メイン入力Editを見つけてクリック
    2. Ctrl+A で全選択してDelete
    3. クリップボード経由でテキスト貼り付け
    """
    e = find_main_input(win)
    if not e:
        log("  [error] main input not found")
        return False

    e.click_input()
    time.sleep(0.4)

    # 既存テキストをクリア
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.press('delete')
    time.sleep(0.2)

    # クリップボードに書き込み
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(CF_UNICODETEXT,
                                    text.encode('utf-16-le') + b'\x00\x00')
    win32clipboard.CloseClipboard()
    time.sleep(0.3)

    # 貼り付け
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    return True

# ── Tab / language switching ─────────────────────────────────────────────────

def click_tab(win, tab_keyword):
    """タブをクリック (UIA TabItem または座標フォールバック)"""
    t = find_tab(win, tab_keyword)
    if t:
        try:
            t.click_input()
            time.sleep(1.2)
            log(f"  [tab] clicked '{tab_keyword}' via UIA")
            return True
        except Exception as ex:
            log(f"  [tab] UIA click failed: {ex}, trying coords")

    # 座標フォールバック
    for key, center in TAB_CENTERS.items():
        if tab_keyword.lower() in key.lower():
            pyautogui.click(*center)
            time.sleep(1.2)
            log(f"  [tab] clicked '{tab_keyword}' via coords {center}")
            return True

    log(f"  [warn] tab '{tab_keyword}' not found")
    return False

def set_language(win, lang):
    """言語ボタンをクリック (JP / EN)"""
    label = "日本語" if lang == "JP" else "English"
    btn = find_button(win, label)
    if btn:
        try:
            btn.click_input()
            time.sleep(0.8)
            log(f"  [lang] set to {lang} via UIA")
            return
        except Exception:
            pass

    center = LANG_CENTERS.get(lang)
    if center:
        pyautogui.click(*center)
        time.sleep(0.8)
        log(f"  [lang] set to {lang} via coords {center}")

# ── ffmpeg helpers ───────────────────────────────────────────────────────────

def start_ffmpeg(output_file, win_title=WINDOW):
    """ffmpeg ウィンドウキャプチャ開始 (非同期)"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    log_path = output_file + ".log"
    cmd = [
        "ffmpeg", "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-draw_mouse", "1",
        "-i", f"title={win_title}",
        "-vf", "scale=1920:1080:flags=lanczos",
        "-vcodec", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_file,
    ]
    log(f"  [ffmpeg] start -> {os.path.basename(output_file)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=open(log_path, "w"),
    )
    time.sleep(2.5)
    return proc

def stop_ffmpeg(proc):
    """ffmpeg に 'q' を送って終了"""
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=30)
        log("  [ffmpeg] stopped")
    except Exception:
        proc.kill()

# ── Desktop recording ─────────────────────────────────────────────────────────

def record_desktop(output_name, tab, lang, prompt, response_wait=90):
    """デスクトップ版: 1本録画"""
    out_path = os.path.join(OUTPUT_DIR, output_name)
    log("\n" + "=" * 60)
    log(f"Recording: {output_name}")
    log(f"  tab={tab}  lang={lang}  wait={response_wait}s")
    log("=" * 60)

    proc = start_ffmpeg(out_path)
    try:
        win = get_window()

        # 1. タブクリック
        click_tab(win, tab)

        # 2. 言語切替
        set_language(win, lang)
        time.sleep(0.5)

        # 3. テキスト入力 & 送信
        ok = paste_to_input(win, prompt)
        if not ok:
            log("  [error] paste failed, skipping")
            return
        time.sleep(0.5)

        log(f"  [send] Ctrl+Enter")
        pyautogui.hotkey('ctrl', 'enter')

        # 4. 回答を待つ
        log(f"  [wait] {response_wait}s for response...")
        time.sleep(response_wait)

        # 5. 少し余韻を持たせて終了
        time.sleep(4)

    finally:
        stop_ffmpeg(proc)

    if os.path.exists(out_path):
        size_mb = os.path.getsize(out_path) / 1_048_576
        log(f"  [OK] {out_path} ({size_mb:.1f} MB)")
    else:
        log(f"  [FAIL] file not found: {out_path}")

# ── Web UI recording ──────────────────────────────────────────────────────────

def pilot_browse(task: str, timeout: int = 360):
    """helix_pilot browse でブラウザ操作"""
    cmd = [
        "python", "scripts/helix_pilot.py",
        "--output-mode", "minimal",
        "browse", task,
        "--window", "Google Chrome",
    ]
    log(f"  [browse] task len={len(task)}")
    r = subprocess.run(cmd, cwd=HELIX_DIR, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    out = r.stdout.strip()
    log(f"  [browse] rc={r.returncode} out={out[:200]}")
    return r.returncode == 0

def record_webui(output_name, task, wait_after=8, timeout=300):
    """WebUI版: 1本録画"""
    out_path = os.path.join(OUTPUT_DIR, output_name)
    log("\n" + "=" * 60)
    log(f"WebUI Recording: {output_name}")
    log("=" * 60)

    proc = start_ffmpeg(out_path, win_title="Helix AI Studio - Google Chrome")
    try:
        ok = pilot_browse(task, timeout=timeout)
        if not ok:
            log("  [warn] browse returned non-zero, continuing...")
        time.sleep(wait_after)
    finally:
        stop_ffmpeg(proc)

    if os.path.exists(out_path):
        size_mb = os.path.getsize(out_path) / 1_048_576
        log(f"  [OK] {out_path} ({size_mb:.1f} MB)")
    else:
        log(f"  [FAIL] file not found: {out_path}")

# ── Desktop scenarios ────────────────────────────────────────────────────────
# (output_name, tab, lang, prompt, response_wait_sec)

DESKTOP_SCENARIOS = {
    "cloudai_jp": (
        "desktop_cloudai_jp.mp4",
        "cloudAI", "JP",
        "Pythonでバブルソートを実装してください。コードに日本語コメントを付けてください。",
        120,
    ),
    "cloudai_en": (
        "desktop_cloudai_en.mp4",
        "cloudAI", "EN",
        "Implement bubble sort in Python with comments explaining each step.",
        120,
    ),
    "localai_jp": (
        "desktop_localai_jp.mp4",
        "localAI", "JP",
        "機械学習とは何ですか？3つの代表的な手法と具体例を日本語で説明してください。",
        180,
    ),
    "localai_en": (
        "desktop_localai_en.mp4",
        "localAI", "EN",
        "What is machine learning? Explain the 3 main types with examples.",
        180,
    ),
    "mixai_jp": (
        "desktop_mixai_jp.mp4",
        "mixAI", "JP",
        "RESTful APIの設計ベストプラクティスを5つ教えてください。",
        600,
    ),
    "mixai_en": (
        "desktop_mixai_en.mp4",
        "mixAI", "EN",
        "List 5 RESTful API design best practices.",
        600,
    ),
    "rag_jp": (
        "desktop_rag_jp.mp4",
        "RAG", "JP",
        "Helix AI Studioの主な機能と使い方を教えてください。",
        120,
    ),
    "rag_en": (
        "desktop_rag_en.mp4",
        "RAG", "EN",
        "What are the main features of Helix AI Studio and how do I use it?",
        120,
    ),
}

# ── Web UI scenarios ─────────────────────────────────────────────────────────

WEBUI_SCENARIOS = {
    "webui_cloudai_jp": (
        "webui_cloudai_jp.mp4",
        (
            f"{WEBUI_URL} にアクセスし、cloudAIタブをクリックしてください。"
            "チャット入力欄に「Pythonでフィボナッチ数列を再帰とループの2通りで実装してください。」"
            "と入力して送信ボタンをクリックしてください。回答がすべて表示されるまで待ってください。"
        ),
        8, 300
    ),
    "webui_cloudai_en": (
        "webui_cloudai_en.mp4",
        (
            f"Go to {WEBUI_URL}, click the cloudAI tab."
            " Type: 'Implement Fibonacci sequence in Python using both recursion and iteration.'"
            " Click Send and wait for the complete response."
        ),
        8, 300
    ),
    "webui_localai_jp": (
        "webui_localai_jp.mp4",
        (
            f"{WEBUI_URL} にアクセスし、localAIタブをクリックしてください。"
            "チャット入力欄に「ニューラルネットワークの仕組みを初心者向けに日本語で説明してください。」"
            "と入力して送信してください。ローカルAIが完全に回答を生成するまで待ってください。"
        ),
        8, 360
    ),
    "webui_localai_en": (
        "webui_localai_en.mp4",
        (
            f"Go to {WEBUI_URL}, click the localAI tab."
            " Type: 'Explain how neural networks work for a beginner.'"
            " Click Send and wait for the local AI to finish generating."
        ),
        8, 360
    ),
    "webui_mixai_jp": (
        "webui_mixai_jp.mp4",
        (
            f"{WEBUI_URL} にアクセスし、mixAIタブをクリックしてください。"
            "チャット入力欄に「Dockerとは何か？主なメリットと基本コマンドを教えてください。」"
            "と入力して送信してください。すべてのフェーズが完了して最終回答が表示されるまで待ってください。"
        ),
        10, 900
    ),
    "webui_mixai_en": (
        "webui_mixai_en.mp4",
        (
            f"Go to {WEBUI_URL}, click the mixAI tab."
            " Type: 'What is Docker? Explain its benefits and show basic commands.'"
            " Click Send and wait for all pipeline phases to complete."
        ),
        10, 900
    ),
}

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    desktop_keys = list(DESKTOP_SCENARIOS.keys())
    webui_keys   = list(WEBUI_SCENARIOS.keys())

    if target == "all":
        run_desktop = desktop_keys
        run_webui   = webui_keys
    elif target == "webui":
        run_desktop = []
        run_webui   = webui_keys
    elif target in DESKTOP_SCENARIOS:
        run_desktop = [target]
        run_webui   = []
    elif target in WEBUI_SCENARIOS:
        run_desktop = []
        run_webui   = [target]
    else:
        log(f"Unknown target: {target}")
        log("Available: " + str(desktop_keys + ["webui", "all"]))
        sys.exit(1)

    for key in run_desktop:
        name, tab, lang, prompt, wait = DESKTOP_SCENARIOS[key]
        record_desktop(name, tab, lang, prompt, response_wait=wait)
        time.sleep(3)

    for key in run_webui:
        name, task, wait, ai_to = WEBUI_SCENARIOS[key]
        record_webui(name, task, wait_after=wait, timeout=ai_to)
        time.sleep(3)

    log("\n" + "=" * 60)
    log(f"All recordings done. Output: {OUTPUT_DIR}")
    log("=" * 60)


if __name__ == "__main__":
    main()

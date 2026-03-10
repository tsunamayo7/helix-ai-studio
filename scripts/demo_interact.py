"""
Helix AI Studio デモ撮影スクリプト v3
物理座標(mss 3840x2160 基準)を直接使用 + ffmpeg gdigrab 録画

HelixPilot scale_factor 方式が DPI 環境で誤差を生じるため、
mss fullscreen スクリーンショットで実測した物理座標を直接使う。

座標系: pyautogui / win32api / mss すべて物理 3840x2160 で一致確認済み
"""

import subprocess
import sys
import time
import os
import win32gui
import pyautogui
import mss
import numpy as np
import cv2

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
WINDOW_TITLE = "Helix AI Studio v12.8.0"

SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "demo", "20260303-1")
os.makedirs(SAVE_DIR, exist_ok=True)

SS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "helix_pilot_screenshots")

PILOT = os.path.join(os.path.dirname(__file__), "helix_pilot.py")

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2

# ─────────────────────────────────────────
# 実測済み物理座標 (mss 3840x2160 基準)
# ─────────────────────────────────────────
# メインタブバー (y≈68)
TAB_CLOUDAI        = (228,  68)
TAB_LOCALAI        = (368,  68)
TAB_VD             = (808,  68)   # Virtual Desktop
TAB_SETTINGS       = (976,  68)   # 一般設定

# サブタブ (y≈112)
SUBTAB_CHAT        = ( 88, 112)
SUBTAB_SETTINGS    = (236, 112)

# cloudAI モデルコンボ + ポップアップアイテム (実測済み)
COMBO_CLOUD        = (394, 168)   # コンボボックス本体クリック位置
POPUP_CLOUD = {
    "Claude Opus 4.6 [CLI]":    (470, 222),
    "GPT-5.3-codex [Codex]":    (470, 290),
    "Claude Sonnet 4.6 [CLI]":  (470, 350),
    "Gemini 3 Flash [Gemini]":  (470, 414),
}

# localAI モデルコンボ (実測済み: 2026-03-04)
# COMBO_LOCAL: click(542, 182) でポップアップ開くことを確認済み
# ポップアップ X 中心 ≈ 552、各アイテム Y は輝度解析で確定
COMBO_LOCAL        = (542, 182)
POPUP_LOCAL = {
    "qwen3.5:122b":          (552, 222),
    "gemma3:27b":            (552, 286),
    "translategemma:27b":    (552, 350),
    "qwen3-next:80b":        (552, 413),
    "ministral-3:8b":        (552, 476),
    "qwen3-embedding:4b":    (552, 539),
    "ministral-3:latest":    (552, 602),
}

# テキスト入力 + 送信ボタン
# cloudAI 入力欄 TOP: physical y=1684, localAI 入力欄 TOP: physical y=1744
# y=1810 は両タブの入力欄内に確実に収まる (実測 2026-03-04)
TEXT_INPUT         = (1264, 1810)  # メッセージ入力エリア中央 (両タブ共通)
# ▶ 送信ボタン: PRIMARY_BTN (#0ea5e9) 色検出で実測 (2026-03-04)
# img_rect=(2412,539,130,48) at top=1500 → physical center (2477, 2063)
SEND_BTN           = (2477, 2063)  # ▶ 送信ボタン (物理座標)

# ─────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────

def activate_window():
    """メインウィンドウをフォアグラウンドに"""
    def cb(hwnd, _):
        try:
            if WINDOW_TITLE in win32gui.GetWindowText(hwnd):
                win32gui.SetForegroundWindow(hwnd)
        except:
            pass
    win32gui.EnumWindows(cb, None)
    time.sleep(0.8)


def click_phys(x: int, y: int, delay: float = 0.3):
    """物理座標でクリック"""
    pyautogui.click(x, y)
    time.sleep(delay)


def take_ss(name: str) -> str:
    """HelixPilot でスクリーンショット保存"""
    subprocess.run(
        [sys.executable, PILOT, "screenshot", "--window", WINDOW_TITLE, "--name", name],
        capture_output=True, encoding="utf-8", timeout=30
    )
    return os.path.join(SS_DIR, f"{name}.png")


def take_mss_crop(name: str, top: int, left: int, height: int, width: int) -> str:
    """mss で特定領域を取得して保存"""
    with mss.mss() as sct:
        img = np.array(sct.grab({'left': left, 'top': top, 'width': width, 'height': height}))
        path = os.path.join(SS_DIR, f"{name}.png")
        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
    return path


def wait_stable(timeout: int = 300):
    """AI 応答完了まで画面安定待ち"""
    subprocess.run(
        [sys.executable, PILOT, "wait-stable", "--window", WINDOW_TITLE, "--timeout", str(timeout)],
        capture_output=True, encoding="utf-8", timeout=timeout + 30
    )


def send_message(message: str):
    """テキスト入力欄をクリック → メッセージ入力 → Ctrl+Enter 送信 (cloudAI用)"""
    click_phys(*TEXT_INPUT, delay=0.4)

    # 既存テキストをクリア
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.press("delete")
    time.sleep(0.2)

    # クリップボード経由で日本語テキストを貼り付け
    import pyperclip
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.6)

    # Ctrl+Enter で送信 (cloudAI は EnhancedChatInput でキーイベントを処理)
    pyautogui.hotkey("ctrl", "enter")
    time.sleep(0.5)
    print(f"  [send] {len(message)} chars sent")


def send_message_local(message: str):
    """テキスト入力欄をクリック → メッセージ入力 → 送信ボタン直接クリック (localAI用)

    localAI の input_field は plain QTextEdit のためキーボードショートカット不可。
    ▶ 送信ボタン (SEND_BTN) を直接クリックして送信する。
    """
    import pyperclip

    click_phys(*TEXT_INPUT, delay=0.5)

    # 既存テキストをクリア
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.press("delete")
    time.sleep(0.3)

    # クリップボード経由で日本語テキストを貼り付け
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.8)

    # 送信ボタンを直接クリック (plain QTextEdit はキーイベント非対応)
    click_phys(*SEND_BTN, delay=0.6)
    print(f"  [send_local] {len(message)} chars sent via button click at {SEND_BTN}")


def select_cloud_model(model_display: str):
    """
    cloudAI モデルコンボをクリック → ポップアップアイテムを直接クリックして選択。
    model_display: POPUP_CLOUD のキーと一致する表示名
    """
    popup_pos = POPUP_CLOUD.get(model_display)
    if popup_pos is None:
        print(f"  [WARN] Unknown model: {model_display}")
        return

    # コンボクリック（ポップアップ開く）
    pyautogui.click(*COMBO_CLOUD)
    time.sleep(0.20)   # ポップアップが描画されるまで待つ

    # アイテムをクリック
    pyautogui.click(*popup_pos)
    time.sleep(0.4)

    # 確認
    print(f"  [model] Cloud model selected: {model_display}")
    take_mss_crop(f"model_check_{model_display[:20].replace(' ', '_')}",
                  top=100, left=0, height=200, width=800)


def detect_localai_popup_positions():
    """
    localAI モデルポップアップの位置を実測して POPUP_LOCAL を更新する。
    """
    activate_window()
    click_phys(*TAB_LOCALAI, delay=0.5)
    click_phys(*SUBTAB_CHAT, delay=0.5)
    time.sleep(0.5)

    # コンボクリックして即座にフルスクリーン
    pyautogui.click(*COMBO_LOCAL)
    time.sleep(0.2)

    path = take_mss_crop("localai_popup", top=0, left=0, height=800, width=2000)

    # Escape でキャンセル
    pyautogui.press("escape")
    time.sleep(0.3)

    # 画像から Y 座標を取得（手動で更新が必要な場合は print で出力）
    print(f"  [detect] localAI popup screenshot saved: {path}")
    print("  [detect] Please read the screenshot and update POPUP_LOCAL coordinates.")
    return path


def select_local_model(model_name: str):
    """
    localAI モデルコンボをクリック → ポップアップアイテムをクリック。
    POPUP_LOCAL の座標が None の場合は自動検出を試みる。
    """
    popup_pos = POPUP_LOCAL.get(model_name)
    if popup_pos is None:
        print(f"  [WARN] localAI popup position unknown for {model_name}, using keyboard fallback")
        # キーボードフォールバック: Home → Down × N → Enter
        idx = list(POPUP_LOCAL.keys()).index(model_name) if model_name in POPUP_LOCAL else 0
        pyautogui.click(*COMBO_LOCAL)
        time.sleep(0.2)
        pyautogui.press("home")
        for _ in range(idx):
            pyautogui.press("down")
            time.sleep(0.15)
        pyautogui.press("enter")
        time.sleep(0.4)
    else:
        pyautogui.click(*COMBO_LOCAL)
        time.sleep(0.20)
        pyautogui.click(*popup_pos)
        time.sleep(0.4)

    print(f"  [model] Local model selected: {model_name}")


# ─────────────────────────────────────────
# ffmpeg 録画
# ─────────────────────────────────────────

def start_recording(output_name: str, fps: int = 10, duration: int = 300):
    """ffmpeg gdigrab でウィンドウ録画開始"""
    output_path = os.path.join(SAVE_DIR, f"{output_name}.mp4")
    cmd = (
        f'ffmpeg -y -f gdigrab -framerate {fps} -i "title={WINDOW_TITLE}" '
        f'-vf "scale=1920:1080" -vcodec libx264 -pix_fmt yuv420p '
        f'-preset fast -crf 23 -t {duration} "{output_path}"'
    )
    proc = subprocess.Popen(
        cmd, shell=True, stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2.0)
    print(f"  [rec] Recording started → {output_path}")
    return proc, output_path


def stop_recording(proc, output_path: str):
    """ffmpeg に q を送って録画終了"""
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.stdin.close()
        proc.wait(timeout=15)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    if os.path.exists(output_path):
        mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"  [rec] Saved: {output_path}  ({mb:.1f} MB)")
    else:
        print(f"  [rec] WARN: Not found: {output_path}")


# ─────────────────────────────────────────
# デモ実行
# ─────────────────────────────────────────

def demo_cloudai_chat(output_name: str, model_name: str, message: str,
                      wait_timeout: int = 240, rec_duration: int = 300):
    """cloudAI チャットデモ"""
    print(f"\n{'='*60}")
    print(f"[DEMO] {output_name}")
    print(f"  Model  : {model_name}")
    print(f"  Message: {message[:60]}...")
    print(f"{'='*60}")

    activate_window()
    proc, output_path = start_recording(output_name, duration=rec_duration)

    try:
        click_phys(*TAB_CLOUDAI, delay=0.5)
        click_phys(*SUBTAB_CHAT, delay=0.5)
        time.sleep(0.5)

        select_cloud_model(model_name)
        time.sleep(0.5)

        send_message(message)
        time.sleep(1.0)

        print("  [wait] Waiting for AI response...")
        wait_stable(timeout=wait_timeout)
        print("  [wait] Response complete.")

        take_ss(f"{output_name}_final")
        time.sleep(2.0)

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        stop_recording(proc, output_path)


def demo_localai_chat(output_name: str, model_name: str, message: str,
                      wait_timeout: int = 480, rec_duration: int = 600):
    """localAI チャットデモ"""
    print(f"\n{'='*60}")
    print(f"[DEMO] {output_name}")
    print(f"  Model  : {model_name}")
    print(f"  Message: {message[:60]}...")
    print(f"{'='*60}")

    activate_window()
    proc, output_path = start_recording(output_name, duration=rec_duration)

    try:
        click_phys(*TAB_LOCALAI, delay=0.5)
        click_phys(*SUBTAB_CHAT, delay=0.5)
        time.sleep(0.5)

        select_local_model(model_name)
        time.sleep(0.5)

        send_message_local(message)  # localAI は plain QTextEdit → ボタン直クリック
        time.sleep(1.0)

        print("  [wait] Waiting for local AI response...")
        wait_stable(timeout=wait_timeout)
        print("  [wait] Response complete.")

        take_ss(f"{output_name}_final")
        time.sleep(2.0)

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        stop_recording(proc, output_path)


def demo_cloudai_vd(output_name: str, model_name: str, message: str,
                    wait_timeout: int = 300, rec_duration: int = 480):
    """cloudAI チャット → Virtual Desktop タブデモ"""
    print(f"\n{'='*60}")
    print(f"[DEMO] {output_name}")
    print(f"{'='*60}")

    activate_window()
    proc, output_path = start_recording(output_name, duration=rec_duration)

    try:
        click_phys(*TAB_CLOUDAI, delay=0.5)
        click_phys(*SUBTAB_CHAT, delay=0.5)
        time.sleep(0.5)

        select_cloud_model(model_name)
        time.sleep(0.5)

        send_message(message)
        time.sleep(1.0)

        print("  [wait] Waiting for code response...")
        wait_stable(timeout=wait_timeout)
        print("  [wait] Response complete.")
        time.sleep(1.0)

        print("  [nav] → Virtual Desktop tab")
        click_phys(*TAB_VD, delay=1.0)
        time.sleep(2.0)

        take_ss(f"{output_name}_vd")
        time.sleep(2.0)

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        stop_recording(proc, output_path)


def demo_localai_vd(output_name: str, model_name: str, message: str,
                    wait_timeout: int = 480, rec_duration: int = 600):
    """localAI チャット → Virtual Desktop タブデモ"""
    print(f"\n{'='*60}")
    print(f"[DEMO] {output_name}")
    print(f"{'='*60}")

    activate_window()
    proc, output_path = start_recording(output_name, duration=rec_duration)

    try:
        click_phys(*TAB_LOCALAI, delay=0.5)
        click_phys(*SUBTAB_CHAT, delay=0.5)
        time.sleep(0.5)

        select_local_model(model_name)
        time.sleep(0.5)

        send_message_local(message)  # localAI は plain QTextEdit → ボタン直クリック
        time.sleep(1.0)

        print("  [wait] Waiting for local AI code response...")
        wait_stable(timeout=wait_timeout)
        print("  [wait] Response complete.")
        time.sleep(1.0)

        print("  [nav] → Virtual Desktop tab")
        click_phys(*TAB_VD, delay=1.0)
        time.sleep(2.0)

        take_ss(f"{output_name}_vd")
        time.sleep(2.0)

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        stop_recording(proc, output_path)


# ─────────────────────────────────────────
# 各デモ定義
# ─────────────────────────────────────────

def test_01_cloudai_gemini():
    demo_cloudai_chat(
        output_name="01_cloudai_gemini_api",
        model_name="Gemini 3 Flash [Gemini]",
        message="こんにちは！複数のAIを連携させるメリットを3点教えてください。",
        wait_timeout=180, rec_duration=240,
    )


def test_02_cloudai_claude():
    demo_cloudai_chat(
        output_name="02_cloudai_claude_cli",
        model_name="Claude Sonnet 4.6 [CLI]",
        message="AIオーケストレーションとは何ですか？一言で説明してください。",
        wait_timeout=180, rec_duration=240,
    )


def test_03_cloudai_gpt():
    demo_cloudai_chat(
        output_name="03_cloudai_gpt_cli",
        model_name="GPT-5.3-codex [Codex]",
        message="Pythonでフィボナッチ数列を表示する関数を書いてください。",
        wait_timeout=180, rec_duration=240,
    )


def test_04_localai_gemma():
    demo_localai_chat(
        output_name="04_localai_gemma3_27b",
        model_name="gemma3:27b",
        message="ローカルLLMを使う利点を3つ挙げてください。",
        wait_timeout=360, rec_duration=420,
    )


def test_05_localai_qwen():
    demo_localai_chat(
        output_name="05_localai_qwen35_122b",
        model_name="qwen3.5:122b",
        message="Pythonのリスト内包表記を初心者向けに説明してください。",
        wait_timeout=480, rec_duration=540,
    )


def test_06_cloudai_vd():
    demo_cloudai_vd(
        output_name="06_cloudai_virtualdesktop_app",
        model_name="Claude Sonnet 4.6 [CLI]",
        message=(
            "Virtual Desktopのサンドボックスで動かせる、"
            "シンプルなtkinter GUIアプリ（ボタンを押すとHello World!と表示）の"
            "Pythonコードを書いてください。ファイル名はhello_gui.pyとします。"
        ),
        wait_timeout=300, rec_duration=420,
    )


def test_07_localai_vd():
    demo_localai_vd(
        output_name="07_localai_virtualdesktop_app",
        model_name="qwen3.5:122b",
        message=(
            "Virtual Desktopのサンドボックスで動かせる、"
            "シンプルなtkinter GUIアプリ（ウィンドウタイトルをLocalAI Demoとする）の"
            "Pythonコードを書いてください。ファイル名はlocal_gui.pyとします。"
        ),
        wait_timeout=480, rec_duration=600,
    )


def cmd_detect_local():
    """localAI ポップアップ座標を自動検出"""
    path = detect_localai_popup_positions()
    print(f"  Screenshot: {path}")
    print("  After viewing the screenshot, update POPUP_LOCAL in this script.")


# ─────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────

TESTS = {
    "1":      ("cloudAI Gemini API",       test_01_cloudai_gemini),
    "2":      ("cloudAI Claude Sonnet CLI", test_02_cloudai_claude),
    "3":      ("cloudAI GPT CLI",          test_03_cloudai_gpt),
    "4":      ("localAI gemma3:27b",       test_04_localai_gemma),
    "5":      ("localAI qwen3.5:122b",     test_05_localai_qwen),
    "6":      ("cloudAI × VirtualDesktop", test_06_cloudai_vd),
    "7":      ("localAI × VirtualDesktop", test_07_localai_vd),
    "detect": ("Detect localAI popup",     cmd_detect_local),
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python demo_interact.py <test_number|detect|all>")
        print("Available tests:")
        for k, (name, _) in TESTS.items():
            print(f"  {k}: {name}")
        sys.exit(0)

    key = sys.argv[1]
    if key == "all":
        for k in ["1", "2", "3", "4", "5", "6", "7"]:
            name, fn = TESTS[k]
            print(f"\n>>> Running: {name}")
            fn()
            time.sleep(3.0)
    elif key in TESTS:
        name, fn = TESTS[key]
        print(f">>> Running: {name}")
        fn()
    else:
        print(f"Unknown: {key}. Valid: {list(TESTS.keys())}")
        sys.exit(1)

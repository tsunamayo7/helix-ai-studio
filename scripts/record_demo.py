"""
Helix AI Studio デモ動画撮影スクリプト
ffmpeg (gdigrab) でウィンドウを録画しながら helix_pilot.py auto で操作する。
"""
import subprocess
import sys
import time
import os

WINDOW = "Helix AI Studio v12.8.0"
PILOT = os.path.join(os.path.dirname(__file__), "helix_pilot.py")
SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "demo", "20260303-1")
os.makedirs(SAVE_DIR, exist_ok=True)


def pilot_auto(instruction: str, timeout: int = 600) -> dict:
    """helix_pilot.py auto を実行"""
    result = subprocess.run(
        [sys.executable, PILOT, "--compact", "auto", instruction, "--window", WINDOW],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )
    print("[auto]", result.stdout[:300])
    if result.returncode != 0:
        print("[auto ERROR]", result.stderr[:300])
    return result


def pilot_screenshot(name: str) -> None:
    subprocess.run(
        [sys.executable, PILOT, "screenshot", "--window", WINDOW, "--name", name],
        capture_output=True, encoding="utf-8"
    )


def record_and_operate(output_name: str, instruction: str,
                        duration: int = 240, fps: int = 10) -> None:
    """ffmpeg でウィンドウ録画しながら auto で操作を実行"""
    output_path = os.path.join(SAVE_DIR, f"{output_name}.mp4")
    print(f"\n{'='*60}")
    print(f"[REC START] {output_name}")
    print(f"  Output : {output_path}")
    print(f"  Task   : {instruction[:80]}")
    print(f"{'='*60}")

    # ffmpeg でウィンドウキャプチャ録画開始（shell=True で bash 経由 → gdigrab が GUI アクセスを取得できる）
    ffmpeg_cmd = (
        f'ffmpeg -y -f gdigrab -framerate {fps} -i "title={WINDOW}" '
        f'-vf "scale=1920:1080" -vcodec libx264 -pix_fmt yuv420p '
        f'-preset fast -crf 23 -t {duration} "{output_path}"'
    )
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2.0)  # ffmpeg 起動待ち

    # HelixPilot auto で操作実行
    try:
        pilot_auto(instruction, timeout=duration - 15)
    except subprocess.TimeoutExpired:
        print("[auto] Timeout — recording continues until ffmpeg ends")

    # ffmpeg を正常終了（'q' を stdin に送信 → bash 経由で ffmpeg に届く）
    print(f"[REC END] Sending 'q' to ffmpeg...")
    try:
        ffmpeg_proc.stdin.write(b"q")
        ffmpeg_proc.stdin.flush()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait(timeout=15)
    except Exception:
        ffmpeg_proc.terminate()
        try:
            ffmpeg_proc.wait(timeout=5)
        except Exception:
            pass

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[SAVED] {output_path}  ({size_mb:.1f} MB)")
    else:
        print(f"[WARN] File not found: {output_path}")
    print()


# ─────────────────────────────────────────
# テスト定義
# ─────────────────────────────────────────

def test_cloudai_gemini():
    record_and_operate(
        output_name="01_cloudai_gemini_api",
        instruction=(
            "cloudAIタブを開き、モデルセレクタードロップダウンから「Gemini 3 Flash」を選択し、"
            "テキスト入力欄に「こんにちは！複数のAIを連携させるメリットを3点教えてください。」と入力してSendボタンを押し、"
            "AIからの返答が完全に表示されるまで待つ"
        ),
        duration=180,
    )


def test_cloudai_claude_cli():
    record_and_operate(
        output_name="02_cloudai_claude_cli",
        instruction=(
            "cloudAIタブを開き、モデルセレクタードロップダウンから「Claude Sonnet 4.6」を選択し、"
            "テキスト入力欄に「AIオーケストレーションとは何ですか？一言で説明してください。」と入力してSendボタンを押し、"
            "AIからの返答が完全に表示されるまで待つ"
        ),
        duration=180,
    )


def test_cloudai_gpt_cli():
    record_and_operate(
        output_name="03_cloudai_gpt_cli",
        instruction=(
            "cloudAIタブを開き、モデルセレクタードロップダウンから「GPT-5.3-codex」を選択し、"
            "テキスト入力欄に「Pythonでフィボナッチ数列を表示する関数を書いてください。」と入力してSendボタンを押し、"
            "AIからの返答が完全に表示されるまで待つ"
        ),
        duration=180,
    )


def test_localai_model1():
    record_and_operate(
        output_name="04_localai_gemma3_27b",
        instruction=(
            "localAIタブを開き、モデルセレクタードロップダウンからgemma3:27bを選択し、"
            "テキスト入力欄に「ローカルLLMを使う利点を3つ挙げてください。」と入力してSendボタンを押し、"
            "AIからの返答が完全に表示されるまで待つ"
        ),
        duration=300,
    )


def test_localai_model2():
    record_and_operate(
        output_name="05_localai_qwen35_122b",
        instruction=(
            "localAIタブを開き、モデルセレクタードロップダウンからqwen3.5:122bを選択し、"
            "テキスト入力欄に「Pythonのリスト内包表記を初心者向けに説明してください。」と入力してSendボタンを押し、"
            "AIからの返答が完全に表示されるまで待つ（モデルが大きいため時間がかかります）"
        ),
        duration=480,
    )


def test_cloudai_virtual_desktop():
    record_and_operate(
        output_name="06_cloudai_virtualdesktop_app",
        instruction=(
            "cloudAIタブを開き、モデルセレクタードロップダウンから「Claude Sonnet 4.6」を選択し、"
            "テキスト入力欄に「Virtual Desktopのサンドボックスで動かせる、"
            "シンプルなtkinter GUIアプリ（ボタンを押すとHello World!と表示）のPythonコードを書いてください。"
            "ファイル名はhello_gui.pyとします。」と入力してSendボタンを押し、"
            "AIからのコードが完全に表示されたら、"
            "上部タブバーの「Virtual Desktop」タブをクリックして仮想デスクトップ画面が表示されることを確認する"
        ),
        duration=480,
    )


def test_localai_virtual_desktop():
    record_and_operate(
        output_name="07_localai_virtualdesktop_app",
        instruction=(
            "localAIタブを開き、モデルセレクタードロップダウンからqwen3.5:122bを選択し、"
            "テキスト入力欄に「Virtual Desktopのサンドボックスで動かせる、"
            "シンプルなtkinter GUIアプリ（ウィンドウタイトルをLocalAI Demoとする）のPythonコードを書いてください。"
            "ファイル名はlocal_gui.pyとします。」と入力してSendボタンを押し、"
            "AIからのコードが完全に表示されたら、"
            "上部タブバーの「Virtual Desktop」タブをクリックして仮想デスクトップ画面が表示されることを確認する"
        ),
        duration=600,
    )


if __name__ == "__main__":
    tests = {
        "1": ("cloudAI Gemini API", test_cloudai_gemini),
        "2": ("cloudAI Claude CLI", test_cloudai_claude_cli),
        "3": ("cloudAI GPT CLI", test_cloudai_gpt_cli),
        "4": ("localAI gemma3:4b", test_localai_model1),
        "5": ("localAI qwen3.5:122b", test_localai_model2),
        "6": ("cloudAI × VirtualDesktop", test_cloudai_virtual_desktop),
        "7": ("localAI × VirtualDesktop", test_localai_virtual_desktop),
    }

    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key in tests:
            name, fn = tests[key]
            print(f"Running test: {name}")
            fn()
        else:
            print(f"Unknown test: {key}. Valid: {list(tests.keys())}")
    else:
        print("Usage: python record_demo.py <test_number>")
        print("Available tests:")
        for k, (name, _) in tests.items():
            print(f"  {k}: {name}")

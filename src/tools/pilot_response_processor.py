"""
Pilot Response Processor — LLM応答中の <<PILOT:...>> マーカーを検出・実行・置換

OllamaToolExecutor (src/mcp/ollama_tools.py) と同じパターンで
<<PILOT:command:param=value:param2=value2>> 形式のマーカーを処理する。
"""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# <<PILOT:command:key=value:key2=value2>> パターン
PILOT_PATTERN = re.compile(r'<<PILOT:(\w[\w-]*)((?::\w[\w-]*=[^:>]*)*)\s*>>')


def get_system_prompt_addition(screen_context: str = "", lang: str = "ja") -> str:
    """
    LLM プロンプトに注入する Pilot ツール説明を生成

    Args:
        screen_context: describe コマンドの結果テキスト
        lang: "ja" or "en"

    Returns:
        str: システムプロンプトに追記するテキスト
    """
    if lang == "ja":
        prompt = (
            "\n\n【Helix Pilot — GUI自動操作ツール】\n"
            "以下のコマンドを使ってデスクトップGUIを操作できます。\n"
            "コマンドを使う場合は <<PILOT:コマンド名:パラメータ=値>> の形式で出力してください。\n\n"
            "利用可能なコマンド:\n"
            "- auto: 自律的に複数ステップのGUI操作を実行\n"
            "  <<PILOT:auto:instruction=タスクの説明:window=ウィンドウ名>>\n"
            "- browse: ブラウザを自律的に操作\n"
            "  <<PILOT:browse:instruction=タスクの説明:window=ブラウザ名>>\n"
            "- click: 指定座標をクリック\n"
            "  <<PILOT:click:x=100:y=200:window=ウィンドウ名>>\n"
            "- type: テキストを入力\n"
            "  <<PILOT:type:text=入力テキスト:window=ウィンドウ名>>\n"
            "- hotkey: ホットキーを送信\n"
            "  <<PILOT:hotkey:keys=ctrl+c:window=ウィンドウ名>>\n"
            "- scroll: スクロール\n"
            "  <<PILOT:scroll:amount=-3:window=ウィンドウ名>>\n"
            "- find: UI要素の座標を特定\n"
            "  <<PILOT:find:description=送信ボタン:window=ウィンドウ名>>\n"
            "- describe: 画面の現在の状態を説明\n"
            "  <<PILOT:describe:window=ウィンドウ名>>\n"
            "- verify: 操作結果を検証\n"
            "  <<PILOT:verify:expected=期待される状態:window=ウィンドウ名>>\n"
            "- screenshot: スクリーンショットを撮影\n"
            "  <<PILOT:screenshot:window=ウィンドウ名:name=shot1>>\n"
            "- wait-stable: 画面が安定するまで待機\n"
            "  <<PILOT:wait-stable:timeout=30:window=ウィンドウ名>>\n\n"
            "重要: コマンドを使用する場合は必ず <<PILOT:...>> の形式で出力してください。\n"
            "結果は自動的に表示されます。\n"
        )
    else:
        prompt = (
            "\n\n[Helix Pilot — GUI Automation Tool]\n"
            "You can use the following commands to control the desktop GUI.\n"
            "To use a command, output it in the format <<PILOT:command:param=value>>.\n\n"
            "Available commands:\n"
            "- auto: Autonomously execute multi-step GUI operations\n"
            "  <<PILOT:auto:instruction=task description:window=window name>>\n"
            "- browse: Autonomously control a browser\n"
            "  <<PILOT:browse:instruction=task description:window=browser name>>\n"
            "- click: Click at specified coordinates\n"
            "  <<PILOT:click:x=100:y=200:window=window name>>\n"
            "- type: Type text\n"
            "  <<PILOT:type:text=input text:window=window name>>\n"
            "- hotkey: Send a hotkey combination\n"
            "  <<PILOT:hotkey:keys=ctrl+c:window=window name>>\n"
            "- scroll: Scroll the window\n"
            "  <<PILOT:scroll:amount=-3:window=window name>>\n"
            "- find: Locate a UI element's coordinates\n"
            "  <<PILOT:find:description=send button:window=window name>>\n"
            "- describe: Describe the current screen state\n"
            "  <<PILOT:describe:window=window name>>\n"
            "- verify: Verify the result of an action\n"
            "  <<PILOT:verify:expected=expected state:window=window name>>\n"
            "- screenshot: Take a screenshot\n"
            "  <<PILOT:screenshot:window=window name:name=shot1>>\n"
            "- wait-stable: Wait until the screen stabilizes\n"
            "  <<PILOT:wait-stable:timeout=30:window=window name>>\n\n"
            "Important: Always use the <<PILOT:...>> format when invoking commands.\n"
            "Results will be displayed automatically.\n"
        )

    if screen_context:
        if lang == "ja":
            prompt += f"\n【現在の画面状態】\n{screen_context}\n"
        else:
            prompt += f"\n[Current Screen State]\n{screen_context}\n"

    return prompt


def parse_pilot_calls(response: str) -> List[Dict[str, Any]]:
    """
    応答テキストから <<PILOT:...>> マーカーをパース

    Args:
        response: LLM応答テキスト

    Returns:
        list: [{"command": str, "params": dict, "match": str}, ...]
    """
    calls = []

    for match in PILOT_PATTERN.finditer(response):
        command = match.group(1)
        params_str = match.group(2)

        # パラメータをパース (":key=value" 形式)
        params = {}
        if params_str:
            # 先頭の ":" を除去してから分割
            for segment in params_str.lstrip(":").split(":"):
                if "=" in segment:
                    key, value = segment.split("=", 1)
                    params[key.strip()] = value.strip()

        calls.append({
            "command": command,
            "params": params,
            "match": match.group(0),
        })

    return calls


def execute_and_replace(
    response: str,
    pilot_tool,
    max_iterations: int = 3,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    応答テキスト中の <<PILOT:...>> マーカーを実行し、結果で置換

    Args:
        response: LLM応答テキスト
        pilot_tool: HelixPilotTool インスタンス
        max_iterations: 最大反復回数

    Returns:
        (処理後テキスト, 実行結果リスト)
    """
    executed = []

    for _ in range(max_iterations):
        calls = parse_pilot_calls(response)
        if not calls:
            break

        for call in calls:
            command = call["command"]
            params = call["params"]

            result = pilot_tool.execute(command, params)
            executed.append({
                "command": command,
                "params": params,
                "ok": result.get("ok", False),
                "result": str(result.get("result", result.get("error", "")))[:500],
            })

            # マーカーを結果で置換
            ok = result.get("ok", False)
            if ok:
                replacement = (
                    f"\n\n[Pilot: {command}] {str(result.get('result', ''))[:500]}\n"
                )
            else:
                replacement = (
                    f"\n\n[Pilot: {command} ERROR] {result.get('error', 'unknown')}\n"
                )

            response = response.replace(call["match"], replacement, 1)

    return response, executed

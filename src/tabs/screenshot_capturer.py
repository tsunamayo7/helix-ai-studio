"""
Screenshot Capturer - 全UI画面のスクリーンショット取得機能
Phase 2.6: 全タブのスクリーンショットを一括取得・ZIP化
v1.8.2: Cortex内全サブタブ対応
v2.0.0: Thermal管理タブ, Knowledgeタブ追加対応
v2.1.0: Trinity Dashboardタブ追加対応

References:
- Qt 6 Screenshot Example: https://doc.qt.io/qt-6/qtwidgets-desktop-screenshot-example.html
- PyQt6 QWidget.grab(): https://doc.qt.io/qtforpython-6/examples/example_widgets_desktop_screenshot.html
- QTabWidget: https://doc.qt.io/qt-6/qtabwidget.html
"""

import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QTabWidget, QApplication


class ScreenshotCaptureThread(QThread):
    """
    全タブのスクリーンショットを非同期で取得するスレッド
    v1.8.2: Cortex内の全サブタブにも対応

    Signals:
        progress: (current_step, total_steps, message)
        completed: (success, result_dict_or_error_message)
    """

    progress = pyqtSignal(int, int, str)  # current, total, message
    completed = pyqtSignal(bool, str)  # success, message

    def __init__(
        self,
        tab_widget: QTabWidget,
        save_root: str,
        project_name: str,
        parent: Optional[QWidget] = None
    ):
        """
        初期化

        Args:
            tab_widget: メインのQTabWidget
            save_root: 保存先のルートディレクトリ
            project_name: プロジェクト名（サブフォルダに使用）
            parent: 親ウィジェット
        """
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.save_root = Path(save_root)
        self.project_name = project_name or "default_project"
        self.logger = self._setup_logger()

        # メインタブ名とフォルダ名のマッピング
        self.tab_mapping = {
            0: ("ClaudeCode", "Claude Code"),
            1: ("GeminiDesigner", "Gemini Designer"),
            2: ("AppManager", "App Manager"),
            3: ("Cortex", "Cortex"),
        }

        # Cortex (Settings) 内のサブタブマッピング (インデックス: (フォルダ名, 表示名))
        # v2.0.0: Thermal管理タブ, Knowledgeタブを追加
        # v2.1.0: Trinity Dashboardタブを追加
        # v2.2.0: Encyclopedia Panelタブを追加 (Phase F)
        self.cortex_subtab_mapping = {
            0: ("General", "一般設定"),
            1: ("AIModels", "AIモデル設定"),
            2: ("MCPServer", "MCPサーバー管理"),
            3: ("MCPPolicy", "MCPポリシー"),
            4: ("Memory", "ローカル記憶"),
            5: ("RoutingLog", "ルーティングログ"),
            6: ("Audit", "監査ビュー"),
            7: ("Budget", "予算管理"),
            8: ("LocalConnector", "Local接続"),
            9: ("Thermal", "Thermal管理"),
            10: ("Knowledge", "Knowledge Dashboard"),
            11: ("TrinityDashboard", "Trinity Dashboard"),
            12: ("Encyclopedia", "Encyclopedia Panel"),
        }

        self.captured_files: List[Path] = []
        self.zip_path: Optional[Path] = None

    def _setup_logger(self) -> logging.Logger:
        """ロガーをセットアップ"""
        logger = logging.getLogger("ScreenshotCapturer")
        logger.setLevel(logging.INFO)

        # ログディレクトリを作成
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # ファイルハンドラを追加（重複を避ける）
        if not logger.handlers:
            handler = logging.FileHandler(
                log_dir / "screenshot_app.log",
                encoding="utf-8"
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def run(self):
        """スレッド実行（キャプチャは別途呼び出し）"""
        # 注意: QWidget.grab() はメインスレッドでのみ使用可能
        # このスレッドはZIP生成のみを担当
        pass

    def capture_all_tabs(self) -> Dict[str, Any]:
        """
        全タブのスクリーンショットを取得（Cortex内サブタブ含む）

        注意: この関数はメインスレッドで呼び出す必要があります

        Returns:
            結果辞書 {"success": bool, "message": str, "files": list, "zip_path": str}
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 総ステップ数: メインタブ3つ + Cortexサブタブ数 + ZIP生成
        # Cortexメインタブはサブタブ個別でキャプチャするため除外
        total_steps = 3 + len(self.cortex_subtab_mapping) + 1

        try:
            # 保存先ディレクトリを作成
            base_dir = self.save_root / "Screenshots" / self.project_name
            base_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Starting screenshot capture to: {base_dir}")

            # 現在のタブインデックスを保存
            original_tab_index = self.tab_widget.currentIndex()
            self.captured_files = []
            current_step = 0

            # メインタブをキャプチャ（Cortex以外）
            for tab_index, (folder_name, display_name) in self.tab_mapping.items():
                if tab_index == 3:  # Cortexはサブタブ個別でキャプチャ
                    continue

                current_step += 1
                self.progress.emit(
                    current_step,
                    total_steps,
                    f"キャプチャ中: {display_name}"
                )

                try:
                    # タブのフォルダを作成
                    tab_dir = base_dir / folder_name
                    tab_dir.mkdir(exist_ok=True)

                    # タブを切り替え
                    self.tab_widget.setCurrentIndex(tab_index)
                    QApplication.processEvents()  # UIを更新

                    # 少し待機してUIを安定させる
                    QThread.msleep(100)

                    # タブウィジェットをキャプチャ
                    current_widget = self.tab_widget.widget(tab_index)
                    if current_widget:
                        pixmap = current_widget.grab()

                        # ファイル名を生成
                        filename = f"{folder_name}_{timestamp}.png"
                        filepath = tab_dir / filename

                        # 保存
                        if pixmap.save(str(filepath), "PNG"):
                            self.captured_files.append(filepath)
                            self.logger.info(f"Captured: {filepath}")
                        else:
                            self.logger.warning(f"Failed to save: {filepath}")

                except Exception as e:
                    self.logger.error(f"Error capturing {display_name}: {e}")

            # Cortex内のサブタブをキャプチャ
            cortex_files = self._capture_cortex_subtabs(base_dir, timestamp, current_step, total_steps)
            self.captured_files.extend(cortex_files)
            current_step += len(self.cortex_subtab_mapping)

            # 元のタブに戻す
            self.tab_widget.setCurrentIndex(original_tab_index)
            QApplication.processEvents()

            # ZIP生成
            self.progress.emit(total_steps, total_steps, "ZIP生成中...")

            zip_filename = f"AllTabs_{timestamp}.zip"
            self.zip_path = base_dir / zip_filename

            with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filepath in self.captured_files:
                    # 相対パスでZIPに追加（フォルダ構造を維持）
                    # base_dir からの相対パスを計算
                    rel_path = filepath.relative_to(base_dir)
                    zipf.write(filepath, str(rel_path))

            self.logger.info(f"ZIP created: {self.zip_path}")

            # routing_decisions.jsonl にログを記録
            self._log_to_routing_decisions(timestamp)

            result_message = (
                f"スクリーンショット取得完了\n\n"
                f"保存先: {base_dir}\n"
                f"ファイル数: {len(self.captured_files)}\n"
                f"(メインタブ: 3, Cortexサブタブ: {len(self.cortex_subtab_mapping)})\n"
                f"ZIP: {self.zip_path.name}"
            )

            self.completed.emit(True, result_message)

            return {
                "success": True,
                "message": result_message,
                "files": [str(f) for f in self.captured_files],
                "zip_path": str(self.zip_path),
                "base_dir": str(base_dir),
            }

        except Exception as e:
            error_message = f"スクリーンショット取得エラー: {str(e)}"
            self.logger.error(error_message)
            self.completed.emit(False, error_message)

            return {
                "success": False,
                "message": error_message,
                "files": [],
                "zip_path": None,
            }

    def _capture_cortex_subtabs(
        self,
        base_dir: Path,
        timestamp: str,
        start_step: int,
        total_steps: int
    ) -> List[Path]:
        """
        Cortex (Settings) タブ内の全サブタブをキャプチャ

        Args:
            base_dir: 保存先ベースディレクトリ
            timestamp: タイムスタンプ文字列
            start_step: 現在のステップ数
            total_steps: 総ステップ数

        Returns:
            キャプチャしたファイルのPathリスト
        """
        captured_files: List[Path] = []

        try:
            # Cortex タブに切り替え (インデックス=3)
            self.tab_widget.setCurrentIndex(3)
            QApplication.processEvents()
            QThread.msleep(100)

            # Cortex タブのウィジェットを取得
            cortex_widget = self.tab_widget.widget(3)
            if not cortex_widget:
                self.logger.warning("Cortex widget not found")
                return captured_files

            # Cortex内のQTabWidgetを探す
            cortex_tab_widget = self._find_child_tab_widget(cortex_widget)
            if not cortex_tab_widget:
                self.logger.warning("Cortex QTabWidget not found, falling back to main capture")
                # フォールバック: Cortex全体をキャプチャ
                cortex_dir = base_dir / "Cortex"
                cortex_dir.mkdir(exist_ok=True)
                pixmap = cortex_widget.grab()
                filepath = cortex_dir / f"Cortex_{timestamp}.png"
                if pixmap.save(str(filepath), "PNG"):
                    captured_files.append(filepath)
                    self.logger.info(f"Fallback captured: {filepath}")
                return captured_files

            # 元のサブタブインデックスを保存
            original_subtab_index = cortex_tab_widget.currentIndex()

            # Cortex フォルダを作成
            cortex_dir = base_dir / "Cortex"
            cortex_dir.mkdir(exist_ok=True)

            # 各サブタブをキャプチャ
            for subtab_index, (folder_name, display_name) in self.cortex_subtab_mapping.items():
                current_step = start_step + subtab_index + 1
                self.progress.emit(
                    current_step,
                    total_steps,
                    f"キャプチャ中: Cortex / {display_name}"
                )

                try:
                    # サブタブを切り替え
                    cortex_tab_widget.setCurrentIndex(subtab_index)
                    QApplication.processEvents()
                    QThread.msleep(150)  # サブタブ描画の安定化のため少し長め

                    # サブタブのウィジェットをキャプチャ
                    subtab_widget = cortex_tab_widget.widget(subtab_index)
                    if subtab_widget:
                        pixmap = subtab_widget.grab()

                        # ファイル名を生成
                        filename = f"Cortex_{folder_name}_{timestamp}.png"
                        filepath = cortex_dir / filename

                        # 保存
                        if pixmap.save(str(filepath), "PNG"):
                            captured_files.append(filepath)
                            self.logger.info(f"Captured Cortex subtab: {filepath}")
                        else:
                            self.logger.warning(f"Failed to save Cortex subtab: {filepath}")
                    else:
                        self.logger.warning(f"Subtab widget not found at index {subtab_index}")

                except Exception as e:
                    self.logger.error(f"Error capturing Cortex subtab {display_name}: {e}")

            # 元のサブタブに戻す
            cortex_tab_widget.setCurrentIndex(original_subtab_index)
            QApplication.processEvents()

        except Exception as e:
            self.logger.error(f"Error capturing Cortex subtabs: {e}")

        return captured_files

    def _find_child_tab_widget(self, parent_widget: QWidget) -> Optional[QTabWidget]:
        """
        親ウィジェットからQTabWidgetを探す

        Args:
            parent_widget: 親ウィジェット

        Returns:
            見つかったQTabWidget、見つからない場合はNone
        """
        # 直接の子としてQTabWidgetを探す
        for child in parent_widget.children():
            if isinstance(child, QTabWidget):
                return child

        # レイアウト内のウィジェットも探す
        layout = parent_widget.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, QTabWidget):
                        return widget
                    # 再帰的に探す
                    found = self._find_child_tab_widget(widget)
                    if found:
                        return found

        return None

    def _log_to_routing_decisions(self, timestamp: str):
        """
        routing_decisions.jsonl にイベントを記録

        Args:
            timestamp: タイムスタンプ文字列
        """
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "routing_decisions.jsonl"

            # メインタブ名リスト
            main_tabs = [name for idx, (_, name) in self.tab_mapping.items() if idx != 3]
            # Cortexサブタブ名リスト
            cortex_subtabs = [f"Cortex/{name}" for _, (_, name) in self.cortex_subtab_mapping.items()]

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": "all_ui_screenshot",
                "reason_code": "all_ui_screenshot",
                "project_name": self.project_name,
                "captured_tabs": main_tabs + cortex_subtabs,
                "main_tabs_count": len(main_tabs),
                "cortex_subtabs_count": len(cortex_subtabs),
                "files_count": len(self.captured_files),
                "zip_path": str(self.zip_path) if self.zip_path else None,
                "session_id": "",  # 後で取得
                "selected_backend": "N/A",
                "task_type": "SCREENSHOT",
                "final_status": "success",
                "error_message": "",
            }

            # セッションIDを取得
            try:
                from ..data.session_manager import get_session_manager
                session_manager = get_session_manager()
                log_entry["session_id"] = session_manager.get_current_session_id()
            except Exception:
                pass

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            self.logger.info(f"Logged to routing_decisions.jsonl")

        except Exception as e:
            self.logger.error(f"Failed to log to routing_decisions.jsonl: {e}")


def get_default_save_root() -> str:
    """
    デフォルトの保存先ルートを取得

    Returns:
        保存先ルートパス
    """
    # data ディレクトリをデフォルトとして使用
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return str(data_dir)


def get_current_project_name() -> str:
    """
    現在のプロジェクト名を取得

    Returns:
        プロジェクト名
    """
    try:
        from ..data.project_manager import get_project_manager
        project_manager = get_project_manager()
        name = project_manager.get_current_project_name()
        if name:
            return name
    except Exception:
        pass

    return "HelixAIStudio"

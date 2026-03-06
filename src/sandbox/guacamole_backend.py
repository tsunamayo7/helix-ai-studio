"""Helix AI Studio — GuacamoleManager

Apache Guacamole (clientless remote desktop gateway) との統合バックエンド。
RDP / VNC / SSH で接続された既存 VM をブラウザ経由でヘリックス内に埋め込む。

Docker に依存しないため、Hyper-V / VirtualBox / 別 PC 上の VM に接続できる。
QWebEngineView に Guacamole の Web クライアント URL を読み込むことで
VirtualDesktopTab の既存 UI をほぼそのまま流用できる。

参照: https://guacamole.apache.org/doc/gug/guacamole-rest.html
"""

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GuacamoleConnectionDef:
    """Guacamole 接続定義"""

    def __init__(
        self,
        name: str,
        protocol: str = "rdp",
        host: str = "localhost",
        port: int = 3389,
        username: str = "",
        password: str = "",
        extra: Optional[Dict] = None,
    ):
        self.name = name
        self.protocol = protocol  # rdp / vnc / ssh
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.extra = extra or {}

    def to_api_payload(self) -> dict:
        """Guacamole REST API 用の接続作成ペイロードを生成"""
        params = {
            "hostname": self.host,
            "port": str(self.port),
        }
        if self.username:
            params["username"] = self.username
        if self.password:
            params["password"] = self.password
        if self.protocol == "rdp":
            params.setdefault("security", "any")
            params.setdefault("ignore-cert", "true")
        params.update(self.extra)

        return {
            "name": self.name,
            "protocol": self.protocol,
            "parameters": params,
            "attributes": {"max-connections": "1"},
        }


class GuacamoleManager:
    """
    Apache Guacamole REST API ラッパー。

    VirtualDesktopTab から利用するための最小インタフェースを提供する。
    SandboxManager の代替として、`is_available()` / `get_client_url()` を中心に設計。

    使用フロー:
        mgr = GuacamoleManager(base_url="http://localhost:8080/guacamole")
        if mgr.is_available():
            token, ds = mgr.authenticate("guacadmin", "guacadmin")
            connections = mgr.list_connections(token, ds)
            url = mgr.get_client_url(connections[0]["identifier"], token, ds)
            # → QWebEngineView.setUrl(QUrl(url))
    """

    def __init__(self, base_url: str = "http://localhost:8080/guacamole"):
        # URL 末尾スラッシュを除去
        self._base_url = base_url.rstrip("/")
        self._timeout = 5  # 接続チェック用タイムアウト（秒）

    # ─── 可用性チェック ───

    def is_available(self) -> bool:
        """Guacamole サーバーが起動・応答しているか確認（例外を投げない）"""
        try:
            req = urllib.request.urlopen(
                f"{self._base_url}/", timeout=self._timeout
            )
            return req.status in (200, 302, 301)
        except urllib.error.HTTPError as e:
            # 302/401 等は「サーバーが起動している」ことを意味する
            return e.code in (200, 302, 301, 401, 403)
        except Exception as e:
            logger.debug(f"[GuacamoleManager] is_available check failed: {e}")
            return False

    def get_unavailable_reason(self) -> str:
        """利用不可の理由を返す"""
        try:
            urllib.request.urlopen(f"{self._base_url}/", timeout=self._timeout)
            return ""
        except urllib.error.URLError as e:
            if "Connection refused" in str(e):
                return (
                    f"Guacamole サーバー ({self._base_url}) に接続できません。\n"
                    "Docker で起動する場合:\n"
                    "  docker run -d -p 8080:8080 guacamole/guacamole\n"
                    "または guacd + guacamole コンテナを docker-compose で起動してください。"
                )
            return f"接続エラー: {e}"
        except Exception as e:
            return f"不明なエラー: {e}"

    # ─── 認証 ───

    def authenticate(self, username: str, password: str) -> tuple[str, str]:
        """
        Guacamole REST API でトークン認証。

        Returns:
            (auth_token, data_source) — 成功時
            ("", "") — 失敗時
        """
        try:
            data = urllib.parse.urlencode({
                "username": username,
                "password": password,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self._base_url}/api/tokens",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                token = body.get("authToken", "")
                ds = body.get("dataSource", "")
                if not ds and "availableDataSources" in body:
                    ds = body["availableDataSources"][0] if body["availableDataSources"] else ""
                logger.info(f"[GuacamoleManager] Authenticated: user={username}, dataSource={ds}")
                return token, ds
        except urllib.error.HTTPError as e:
            logger.warning(f"[GuacamoleManager] Auth failed (HTTP {e.code}): {e}")
            return "", ""
        except Exception as e:
            logger.warning(f"[GuacamoleManager] Auth failed: {e}")
            return "", ""

    # ─── 接続管理 ───

    def list_connections(self, token: str, data_source: str) -> List[Dict]:
        """
        利用可能な接続の一覧を返す。

        Returns:
            [{"identifier": "1", "name": "MyVM", "protocol": "rdp", ...}, ...]
        """
        try:
            url = (
                f"{self._base_url}/api/session/data/{data_source}/connections"
                f"?token={urllib.parse.quote(token)}"
            )
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                # API は {id: {name, protocol, ...}} の dict を返す
                result = []
                for conn_id, conn_info in raw.items():
                    conn_info["identifier"] = conn_id
                    result.append(conn_info)
                return result
        except Exception as e:
            logger.warning(f"[GuacamoleManager] list_connections failed: {e}")
            return []

    def create_connection(
        self,
        token: str,
        data_source: str,
        conn_def: GuacamoleConnectionDef,
    ) -> Optional[str]:
        """
        接続を新規作成する。

        Returns:
            作成された接続の identifier (str) or None
        """
        try:
            payload = json.dumps(conn_def.to_api_payload()).encode("utf-8")
            url = (
                f"{self._base_url}/api/session/data/{data_source}/connections"
                f"?token={urllib.parse.quote(token)}"
            )
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                conn_id = body.get("identifier")
                logger.info(
                    f"[GuacamoleManager] Connection created: "
                    f"name={conn_def.name}, id={conn_id}, protocol={conn_def.protocol}"
                )
                return str(conn_id) if conn_id else None
        except Exception as e:
            logger.error(f"[GuacamoleManager] create_connection failed: {e}")
            return None

    def delete_connection(self, token: str, data_source: str, connection_id: str) -> bool:
        """接続を削除する"""
        try:
            url = (
                f"{self._base_url}/api/session/data/{data_source}"
                f"/connections/{connection_id}"
                f"?token={urllib.parse.quote(token)}"
            )
            req = urllib.request.Request(url, method="DELETE")
            urllib.request.urlopen(req, timeout=self._timeout)
            logger.info(f"[GuacamoleManager] Connection deleted: id={connection_id}")
            return True
        except Exception as e:
            logger.warning(f"[GuacamoleManager] delete_connection failed: {e}")
            return False

    # ─── クライアント URL 生成 ───

    @staticmethod
    def _encode_connection_id(connection_id: str, data_source: str) -> str:
        """
        Guacamole の URL フラグメント用に接続 ID をエンコードする。

        Guacamole のフロントエンドは "{id}\\0c\\0{dataSource}" を base64 でエンコードした
        文字列を URL フラグメントの /client/{encoded} として使用する。
        """
        raw = f"{connection_id}\x00c\x00{data_source}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    def get_client_url(
        self,
        connection_id: str,
        token: str,
        data_source: str,
    ) -> str:
        """
        Guacamole Web クライアントの埋め込み URL を生成する。

        QWebEngineView.setUrl(QUrl(url)) にそのまま渡せる形式。
        認証トークン付きなので自動ログインされる。

        Args:
            connection_id: 接続の identifier
            token: 認証トークン
            data_source: データソース名

        Returns:
            http://localhost:8080/guacamole/#/client/{encoded}?token={token}
        """
        encoded = self._encode_connection_id(connection_id, data_source)
        return (
            f"{self._base_url}/#/client/{encoded}"
            f"?token={urllib.parse.quote(token)}"
        )

    def get_base_url(self) -> str:
        """Guacamole サーバーのベース URL（認証不要のトップページ）"""
        return f"{self._base_url}/"

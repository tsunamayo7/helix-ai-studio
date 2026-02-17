"""
Helix AI Studio - Web認証 (v9.0.0)
Tailscale IP制限 + PIN + JWT認証

セキュリティレイヤー:
  Layer 1: Tailscale VPN（ネットワークレベル）
  Layer 2: IP範囲チェック（100.64.0.0/10 = Tailscaleサブネット）
  Layer 3: PIN認証 → JWTトークン発行
  Layer 4: JWT Bearer認証（APIリクエスト毎）
"""

import ipaddress
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt  # PyJWT

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/web_config.json")
DEFAULT_JWT_EXPIRY_HOURS = 168  # 7日間


class WebAuthManager:
    """Web UI認証マネージャー"""

    def __init__(self):
        self._config = self._load_config()
        self._ensure_jwt_secret()

    def _load_config(self) -> dict:
        """設定読み込み"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f).get("web_server", {})
        return {}

    def _save_config(self, config: dict):
        """設定保存"""
        full_config = {"web_server": config}
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)

    def _ensure_jwt_secret(self):
        """JWTシークレットが未設定なら自動生成"""
        if not self._config.get("jwt_secret"):
            self._config["jwt_secret"] = secrets.token_hex(32)
            self._save_config(self._config)
            logger.info("JWT secret auto-generated and saved")

    @property
    def pin(self) -> str:
        return self._config.get("pin", "000000")

    @property
    def jwt_secret(self) -> str:
        return self._config["jwt_secret"]

    @property
    def jwt_expiry_hours(self) -> int:
        return self._config.get("jwt_expiry_hours", DEFAULT_JWT_EXPIRY_HOURS)

    @property
    def allowed_subnet(self) -> str:
        return self._config.get("allowed_tailscale_subnet", "100.64.0.0/10")

    def check_ip(self, client_ip: str) -> bool:
        """
        Tailscale IPサブネットチェック。
        ローカルホスト（127.0.0.1, ::1）は常に許可。
        """
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return True
        try:
            addr = ipaddress.ip_address(client_ip)
            network = ipaddress.ip_network(self.allowed_subnet, strict=False)
            return addr in network
        except ValueError:
            logger.warning(f"Invalid IP address: {client_ip}")
            return False

    def verify_pin(self, pin_input: str) -> bool:
        """PIN照合"""
        return secrets.compare_digest(pin_input, self.pin)

    def create_token(self, client_ip: str) -> str:
        """JWT発行"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "helix_web_user",
            "iat": now,
            "exp": now + timedelta(hours=self.jwt_expiry_hours),
            "ip": client_ip,
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_token(self, token: str) -> dict | None:
        """JWT検証。成功時にペイロードを返す。失敗時にNone。"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.info("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None

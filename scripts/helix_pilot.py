"""
helix_pilot.py - GUI Automation Pilot for Claude Code

External tool: Claude Code sends text commands via subprocess,
helix_pilot performs GUI operations (mouse, keyboard, screenshots),
local Vision LLM (Ollama) interprets screenshots,
results returned as JSON text to minimize context consumption.

Usage:
    python scripts/helix_pilot.py screenshot [--window "title"] [--name "shot1"]
    python scripts/helix_pilot.py click <x> <y> [--window "title"]
    python scripts/helix_pilot.py click-screenshot <x> <y> [--window "title"] [--delay 0.3]
    python scripts/helix_pilot.py type "text" [--window "title"]
    python scripts/helix_pilot.py hotkey ctrl+c [--window "title"]
    python scripts/helix_pilot.py scroll <amount> [--window "title"]
    python scripts/helix_pilot.py describe [--window "title"]
    python scripts/helix_pilot.py find "element description" [--window "title"] [--refine]
    python scripts/helix_pilot.py verify "expected outcome" [--window "title"]
    python scripts/helix_pilot.py status
    python scripts/helix_pilot.py wait-stable [--timeout 60]
    python scripts/helix_pilot.py run-scenario <json_file>
"""

import sys
import os
import json
import time
import base64
import logging
import argparse
import re
import signal
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import pyautogui
import pygetwindow as gw
from PIL import Image, ImageChops
import numpy as np

# Optional: pynput for user activity monitoring
try:
    from pynput import mouse as pynput_mouse, keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# Optional: httpx for Ollama API
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Optional: pyperclip for Unicode text input
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "helix_pilot.json"
VERSION = "1.0.0"

# Disable pyautogui pause for speed; safety is handled by SafetyGuard
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = False  # We implement our own emergency stop


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class PilotError(Exception):
    """Base exception for helix_pilot."""
    pass


class PilotEmergencyStop(PilotError):
    """Emergency stop triggered (mouse in corner)."""
    pass


class PilotSafetyError(PilotError):
    """Safety check failed."""
    pass


class PilotTimeoutError(PilotError):
    """Operation timed out."""
    pass


class PilotLockError(PilotError):
    """Lock acquisition failed."""
    pass


class PilotWindowNotFoundError(PilotError):
    """Target window not found."""
    pass


class PilotVisionError(PilotError):
    """Vision LLM communication error."""
    pass


# ---------------------------------------------------------------------------
# PilotConfig
# ---------------------------------------------------------------------------
class PilotConfig:
    """Configuration loader for helix_pilot."""

    DEFAULTS = {
        "ollama_endpoint": "http://localhost:11434",
        "vision_model": "llama3.2-vision:11b",
        "allowed_windows": [],
        "denied_windows": [
            "Windows Security", "Task Manager", "Administrator:",
            "Password", "Credential", "Windows Defender",
        ],
        "denied_input_patterns": [
            "password", "credential", "secret", "api_key", "token",
        ],
        "user_idle_seconds": 3,
        "operation_timeout": 30,
        "log_file": "logs/helix_pilot.log",
        "screenshot_dir": "data/helix_pilot_screenshots",
        "lock_file": "data/helix_pilot_lock.json",
        "emergency_stop_corner": "top-left",
        "emergency_stop_threshold_px": 5,
        "vision_timeout": 60,
        "safe_mode": True,
    }

    def __init__(self, config_path: Path = None):
        self._path = config_path or DEFAULT_CONFIG_PATH
        self._data = self._load()

    def _load(self) -> dict:
        data = dict(self.DEFAULTS)
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                data.update({k: v for k, v in user_data.items()
                             if not k.startswith("_")})
            except Exception:
                pass  # Fall back to defaults
        return data

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"PilotConfig has no attribute '{name}'")

    @property
    def screenshot_dir_path(self) -> Path:
        p = PROJECT_ROOT / self._data["screenshot_dir"]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def lock_file_path(self) -> Path:
        return PROJECT_ROOT / self._data["lock_file"]

    @property
    def log_file_path(self) -> Path:
        p = PROJECT_ROOT / self._data["log_file"]
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


# ---------------------------------------------------------------------------
# PilotLogger
# ---------------------------------------------------------------------------
class PilotLogger:
    """Timestamped operation logger."""

    def __init__(self, config: PilotConfig):
        self._logger = logging.getLogger("helix_pilot")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            fh = logging.FileHandler(
                str(config.log_file_path), encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"))
            self._logger.addHandler(fh)

    def log_operation(self, op: str, args: dict, result: dict):
        self._logger.info(f"OP:{op} args={json.dumps(args, ensure_ascii=False)} "
                          f"ok={result.get('ok')}")

    def log_safety(self, event: str, detail: str):
        self._logger.warning(f"SAFETY:{event} {detail}")

    def log_error(self, op: str, error: str):
        self._logger.error(f"ERROR:{op} {error}")

    def log_info(self, msg: str):
        self._logger.info(msg)


# ---------------------------------------------------------------------------
# LockManager
# ---------------------------------------------------------------------------
class LockManager:
    """Process-level lock to prevent concurrent helix_pilot instances."""

    def __init__(self, config: PilotConfig):
        self._lock_path = config.lock_file_path
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self, operation: str, timeout: int = 30) -> bool:
        """Acquire lock. Returns False if already locked by a live process."""
        existing = self._read()
        if existing.get("locked"):
            pid = existing.get("pid", 0)
            # Check if the locking process is still alive
            if pid and self._is_pid_alive(pid):
                # Check timeout
                timeout_at = existing.get("timeout_at", "")
                if timeout_at:
                    try:
                        dt = datetime.fromisoformat(timeout_at)
                        if datetime.now() > dt:
                            pass  # Expired, force acquire
                        else:
                            return False
                    except ValueError:
                        return False
                else:
                    return False
            # PID dead or expired — take over
        self._write(operation, timeout)
        return True

    def release(self):
        try:
            self._lock_path.write_text(
                '{"locked": false}', encoding="utf-8")
        except Exception:
            pass

    def is_locked(self) -> dict:
        return self._read()

    def _read(self) -> dict:
        try:
            if self._lock_path.exists():
                return json.loads(
                    self._lock_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"locked": False}

    def _write(self, operation: str, timeout: int):
        now = datetime.now()
        lock_data = {
            "locked": True,
            "pid": os.getpid(),
            "operation": operation,
            "started_at": now.isoformat(),
            "timeout_at": (now + timedelta(seconds=timeout)).isoformat(),
        }
        self._lock_path.write_text(
            json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


# ---------------------------------------------------------------------------
# SafetyGuard
# ---------------------------------------------------------------------------
class SafetyGuard:
    """Safety layer: window validation, emergency stop, user activity detection."""

    def __init__(self, config: PilotConfig, plogger: PilotLogger):
        self._config = config
        self._logger = plogger
        self._last_user_activity_time = 0.0
        self._user_monitoring_active = False
        self._mouse_listener = None
        self._keyboard_listener = None
        self._last_mouse_pos = None
        self._poll_thread = None

    # --- Window validation ---
    def validate_window(self, window_title: str) -> Tuple[bool, str]:
        """Check if a window title is allowed."""
        if not window_title:
            if self._config.safe_mode:
                return False, "safe_mode is on: --window argument required"
            return True, "ok"

        title_lower = window_title.lower()

        # Check denied list first
        for pattern in self._config.denied_windows:
            if pattern.lower() in title_lower:
                self._logger.log_safety(
                    "window_denied",
                    f"'{window_title}' matches denied pattern '{pattern}'")
                return False, f"Window '{window_title}' is denied (pattern: '{pattern}')"

        # Check allowed list (if non-empty)
        allowed = self._config.allowed_windows
        if allowed:
            for pattern in allowed:
                if pattern.lower() in title_lower:
                    return True, "ok"
            self._logger.log_safety(
                "window_not_allowed",
                f"'{window_title}' not in allowed list")
            return False, f"Window '{window_title}' not in allowed list"

        return True, "ok"

    def find_target_window(self, title_pattern: str = None):
        """Find and validate a window by title pattern."""
        if title_pattern is None:
            return None  # No window targeting

        wins = gw.getWindowsWithTitle(title_pattern)
        # Filter by size — skip tiny/hidden windows
        candidates = [w for w in wins if w.width > 100 and w.height > 100]
        if not candidates:
            # Try partial match
            all_wins = gw.getAllWindows()
            pattern_lower = title_pattern.lower()
            candidates = [w for w in all_wins
                          if pattern_lower in w.title.lower()
                          and w.width > 100 and w.height > 100]
        if not candidates:
            raise PilotWindowNotFoundError(
                f"Window not found: '{title_pattern}'")
        return candidates[0]

    # --- Emergency stop ---
    def check_emergency_stop(self):
        """Check if mouse is in the emergency stop corner."""
        pos = pyautogui.position()
        screen_w, screen_h = pyautogui.size()
        threshold = self._config.emergency_stop_threshold_px
        corner = self._config.emergency_stop_corner

        if corner == "top-left":
            if pos.x <= threshold and pos.y <= threshold:
                raise PilotEmergencyStop("Mouse in top-left corner")
        elif corner == "top-right":
            if pos.x >= screen_w - threshold and pos.y <= threshold:
                raise PilotEmergencyStop("Mouse in top-right corner")
        elif corner == "bottom-left":
            if pos.x <= threshold and pos.y >= screen_h - threshold:
                raise PilotEmergencyStop("Mouse in bottom-left corner")
        elif corner == "bottom-right":
            if pos.x >= screen_w - threshold and pos.y >= screen_h - threshold:
                raise PilotEmergencyStop("Mouse in bottom-right corner")

    # --- Input validation ---
    def validate_text_input(self, text: str) -> Tuple[bool, str]:
        """Check text against denied_input_patterns."""
        text_lower = text.lower()
        for pattern in self._config.denied_input_patterns:
            if pattern.lower() in text_lower:
                self._logger.log_safety(
                    "input_denied",
                    f"Text contains denied pattern '{pattern}'")
                return False, f"Text contains denied pattern: '{pattern}'"
        return True, "ok"

    # --- User activity monitoring ---
    def start_user_monitoring(self):
        """Start monitoring user activity."""
        if self._user_monitoring_active:
            return

        self._last_user_activity_time = time.time()

        if HAS_PYNPUT:
            self._start_pynput_monitoring()
        else:
            self._start_polling_monitoring()

        self._user_monitoring_active = True

    def stop_user_monitoring(self):
        """Stop monitoring user activity."""
        self._user_monitoring_active = False
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

    def _start_pynput_monitoring(self):
        def on_mouse_move(x, y):
            self._last_user_activity_time = time.time()

        def on_mouse_click(x, y, button, pressed):
            self._last_user_activity_time = time.time()

        def on_key_press(key):
            self._last_user_activity_time = time.time()

        self._mouse_listener = pynput_mouse.Listener(
            on_move=on_mouse_move, on_click=on_mouse_click)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

        self._keyboard_listener = pynput_keyboard.Listener(
            on_press=on_key_press)
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

    def _start_polling_monitoring(self):
        """Fallback: poll mouse position every 200ms."""
        self._last_mouse_pos = pyautogui.position()

        def poll_loop():
            while self._user_monitoring_active:
                try:
                    pos = pyautogui.position()
                    if self._last_mouse_pos:
                        dx = abs(pos.x - self._last_mouse_pos.x)
                        dy = abs(pos.y - self._last_mouse_pos.y)
                        if dx > 3 or dy > 3:
                            self._last_user_activity_time = time.time()
                    self._last_mouse_pos = pos
                except Exception:
                    pass
                time.sleep(0.2)

        self._poll_thread = threading.Thread(
            target=poll_loop, daemon=True)
        self._poll_thread.start()

    def wait_for_user_idle(self, max_wait: float = 30.0) -> bool:
        """Block until user has been idle for user_idle_seconds.
        Returns False if max_wait exceeded."""
        idle_required = self._config.user_idle_seconds
        start = time.time()

        while time.time() - start < max_wait:
            since_activity = time.time() - self._last_user_activity_time
            if since_activity >= idle_required:
                return True
            time.sleep(0.2)

        return False

    def is_user_active(self) -> bool:
        since = time.time() - self._last_user_activity_time
        return since < self._config.user_idle_seconds

    # --- Pre-operation combined check ---
    def pre_operation_check(self, window_title: str = None) -> Tuple[bool, str]:
        """Run all safety checks before an operation."""
        # Emergency stop
        self.check_emergency_stop()

        # Window validation
        ok, reason = self.validate_window(window_title)
        if not ok:
            return False, reason

        return True, "ok"


# ---------------------------------------------------------------------------
# VisionLLM
# ---------------------------------------------------------------------------
DESCRIBE_PROMPT = """You are a GUI assistant analyzing a screenshot of a computer screen.

Describe what you see in this screenshot in detail. Include:
1. The application name and window title if visible
2. The main UI elements (buttons, text fields, menus, tabs, etc.)
3. Any text content visible on screen
4. The current state of the application (e.g., loading, idle, showing dialog)
5. Any error messages or notifications visible

Respond in plain text, structured as a numbered list. Be concise but thorough.
Focus on information useful for programmatic interaction."""

FIND_PROMPT_TEMPLATE = """You are a precise GUI element locator analyzing a screenshot.

The screenshot is exactly {width} pixels wide and {height} pixels tall.
The coordinate system starts at (0,0) in the top-left corner.
The bottom-right corner is ({width},{height}).

TASK: Find the UI element described as: "{description}"

COORDINATE ESTIMATION RULES:
1. Divide the image width ({width}px) into a mental grid
2. The LEFT edge of the image is x=0, the RIGHT edge is x={width}
3. The TOP edge is y=0, the BOTTOM edge is y={height}
4. For a tab bar near the top with 6 tabs evenly spaced across ~350px starting at x~15:
   - 1st tab center ≈ x=35, 2nd ≈ x=85, 3rd ≈ x=140, etc.
5. Be very precise — even 20px error can cause a misclick

If you find the element, respond ONLY with this JSON (no other text):
{{"found": true, "x": <center_x_integer>, "y": <center_y_integer>, "confidence": "high|medium|low", "description": "<what you found>"}}

If you cannot find it, respond ONLY with:
{{"found": false, "x": 0, "y": 0, "confidence": "none", "description": "<why not found>"}}

IMPORTANT:
- x and y must be INTEGER pixel coordinates of the CENTER of the element
- Coordinates are relative to the screenshot (0,0 is top-left)
- Double-check your x coordinate: is it roughly the correct fraction of {width}?
- confidence: "high" = clearly visible and matches, "medium" = likely match, "low" = uncertain
- Only respond with the JSON object, no other text"""

VERIFY_PROMPT_TEMPLATE = """You are a GUI testing assistant analyzing a screenshot.

TASK: Verify if the following expected outcome is true based on what you see:
Expected: "{expected_outcome}"

Respond in this EXACT JSON format:
{{"success": true/false, "detail": "<explanation of what you actually see>"}}

Be precise. If the expected outcome is partially met, set success to false and explain."""


class VisionLLM:
    """Ollama Vision model interface for screenshot interpretation."""

    def __init__(self, config: PilotConfig, plogger: PilotLogger):
        self._endpoint = config.ollama_endpoint
        self._model = config.vision_model
        self._timeout = config.vision_timeout
        self._logger = plogger

    def check_availability(self) -> Tuple[bool, str]:
        """Check if Ollama is running and vision model is available."""
        if not HAS_HTTPX:
            return False, "httpx not installed"
        try:
            resp = httpx.get(
                f"{self._endpoint}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False, f"Ollama returned status {resp.status_code}"
            models = [m.get("name", "")
                      for m in resp.json().get("models", [])]
            # Check if our model exists (allow partial match without tag)
            model_base = self._model.split(":")[0]
            found = any(model_base in m for m in models)
            if not found:
                return False, f"Model '{self._model}' not found. Available: {models}"

            # Check vision capability
            show_resp = httpx.post(
                f"{self._endpoint}/api/show",
                json={"name": self._model}, timeout=3)
            if show_resp.status_code == 200:
                caps = show_resp.json().get("capabilities", [])
                if "vision" not in caps:
                    return False, (f"Model '{self._model}' does not have "
                                   f"vision capability. Caps: {caps}")
            return True, "ok"
        except httpx.ConnectError:
            return False, f"Cannot connect to Ollama at {self._endpoint}"
        except Exception as e:
            return False, str(e)

    def _encode_image(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _call_vision(self, prompt: str, image_path: Path) -> str:
        """Send image + prompt to Ollama Vision model."""
        if not HAS_HTTPX:
            raise PilotVisionError("httpx not installed")

        b64 = self._encode_image(image_path)
        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [b64],
            }],
            "stream": False,
        }

        try:
            resp = httpx.post(
                f"{self._endpoint}/api/chat",
                json=payload,
                timeout=self._timeout)
            if resp.status_code != 200:
                raise PilotVisionError(
                    f"Ollama returned status {resp.status_code}: "
                    f"{resp.text[:200]}")
            return resp.json().get("message", {}).get("content", "")
        except httpx.ConnectError:
            raise PilotVisionError(
                f"Cannot connect to Ollama at {self._endpoint}")

    def _parse_json_response(self, raw: str, fallback_key: str = "found") -> dict:
        """Extract JSON object from LLM response."""
        # Try direct parse
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting first {...} block
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Fallback
        return {fallback_key: False, "detail": raw[:500]}

    def describe(self, image_path: Path) -> str:
        """Describe what is visible on screen."""
        return self._call_vision(DESCRIBE_PROMPT, image_path)

    def find_element(self, image_path: Path, description: str) -> dict:
        """Find an element matching description."""
        img = Image.open(image_path)
        prompt = FIND_PROMPT_TEMPLATE.format(
            width=img.size[0], height=img.size[1],
            description=description)
        raw = self._call_vision(prompt, image_path)
        return self._parse_json_response(raw, "found")

    def verify_action(self, image_path: Path, expected_outcome: str) -> dict:
        """Verify if an action succeeded."""
        prompt = VERIFY_PROMPT_TEMPLATE.format(
            expected_outcome=expected_outcome)
        raw = self._call_vision(prompt, image_path)
        return self._parse_json_response(raw, "success")


# ---------------------------------------------------------------------------
# CoreOperations
# ---------------------------------------------------------------------------
class CoreOperations:
    """Core GUI operations: screenshot, click, type, hotkey, scroll."""

    def __init__(self, config: PilotConfig, safety: SafetyGuard,
                 plogger: PilotLogger):
        self._config = config
        self._safety = safety
        self._logger = plogger
        self._ss_dir = config.screenshot_dir_path

    def _activate_window(self, win) -> bool:
        """Bring window to foreground."""
        if win is None:
            return True
        try:
            if win.isMinimized:
                win.restore()
                time.sleep(0.3)
            win.activate()
            time.sleep(0.3)
            return True
        except Exception:
            return False

    def screenshot(self, window_title: str = None,
                   name: str = None, activate: bool = True) -> dict:
        """Take screenshot.

        Args:
            activate: If False, skip window activation (useful after click
                      to preserve popups/dropdowns that close on focus change).
        """
        win = None
        if window_title:
            win = self._safety.find_target_window(window_title)
            if activate:
                self._activate_window(win)

        if name is None:
            name = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if win:
            region = (win.left, win.top, win.width, win.height)
            img = pyautogui.screenshot(region=region)
        else:
            img = pyautogui.screenshot()

        # Track original size and logical window size for coordinate scaling.
        # pyautogui.screenshot() captures at PHYSICAL pixel resolution,
        # but pyautogui.click() uses LOGICAL (DPI-scaled) coordinates.
        # We need logical_width / screenshot_width as the scale factor.
        original_size = list(img.size)
        logical_size = None
        if win:
            logical_size = [win.width, win.height]

        # Resize if too large (for Vision LLM and Claude API ≤2000px limit)
        resized = False
        max_dim = 1920
        if img.size[0] > max_dim or img.size[1] > max_dim:
            ratio = min(max_dim / img.size[0], max_dim / img.size[1])
            new_w = int(img.size[0] * ratio)
            new_h = int(img.size[1] * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            resized = True

        # Scale factor: screenshot coords -> logical (click) coords
        if logical_size:
            scale_factor = logical_size[0] / img.size[0]
        elif resized:
            scale_factor = original_size[0] / img.size[0]
        else:
            scale_factor = 1.0

        path = self._ss_dir / f"{name}.png"
        img.save(str(path))
        return {
            "ok": True,
            "path": str(path),
            "size": list(img.size),
            "original_size": original_size,
            "logical_size": logical_size,
            "scale_factor": round(scale_factor, 4),
            "window": window_title,
        }

    def click(self, x: int, y: int, window_title: str = None,
              button: str = "left", clicks: int = 1) -> dict:
        """Click at coordinates (relative to window if specified)."""
        abs_x, abs_y = x, y
        if window_title:
            win = self._safety.find_target_window(window_title)
            self._activate_window(win)
            abs_x = win.left + x
            abs_y = win.top + y

        pyautogui.click(abs_x, abs_y, button=button, clicks=clicks)
        time.sleep(0.1)
        return {
            "ok": True,
            "clicked_at": [abs_x, abs_y],
            "window": window_title,
            "button": button,
        }

    def type_text(self, text: str, window_title: str = None,
                  interval: float = 0.03) -> dict:
        """Type text. Uses clipboard paste for non-ASCII."""
        if window_title:
            win = self._safety.find_target_window(window_title)
            self._activate_window(win)

        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            self._type_unicode(text)

        time.sleep(0.1)
        return {
            "ok": True,
            "typed_length": len(text),
            "window": window_title,
        }

    @staticmethod
    def _type_unicode(text: str):
        """Type unicode text via clipboard paste."""
        if not HAS_PYPERCLIP:
            # Fallback: use pyautogui.write (may not work for all chars)
            pyautogui.write(text)
            return
        old_clip = pyperclip.paste()
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        pyperclip.copy(old_clip)

    def hotkey(self, keys: str) -> dict:
        """Press hotkey combo like 'ctrl+c', 'alt+tab'."""
        parts = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*parts)
        time.sleep(0.15)
        return {"ok": True, "keys": keys}

    def scroll(self, amount: int, window_title: str = None) -> dict:
        """Scroll mouse wheel. Positive = up, negative = down."""
        if window_title:
            win = self._safety.find_target_window(window_title)
            self._activate_window(win)
            center_x = win.left + win.width // 2
            center_y = win.top + win.height // 2
            pyautogui.moveTo(center_x, center_y)
            time.sleep(0.1)

        pyautogui.scroll(amount)
        time.sleep(0.1)
        return {"ok": True, "amount": amount, "window": window_title}

    def wait_stable(self, timeout: int = 60, window_title: str = None,
                    stability_checks: int = 3,
                    interval: float = 1.5) -> dict:
        """Wait until screen stops changing."""
        win = None
        if window_title:
            win = self._safety.find_target_window(window_title)

        start = time.time()
        prev_img = None
        stable_count = 0

        while time.time() - start < timeout:
            if win:
                region = (win.left, win.top, win.width, win.height)
                current = pyautogui.screenshot(region=region)
            else:
                current = pyautogui.screenshot()

            if prev_img is not None:
                diff = ImageChops.difference(
                    prev_img.convert("L"), current.convert("L"))
                diff_arr = np.array(diff)
                total = diff_arr.size
                changed = np.count_nonzero(diff_arr > 10)
                ratio = changed / total if total else 0

                if ratio < 0.001:  # < 0.1%
                    stable_count += 1
                    if stable_count >= stability_checks:
                        elapsed = time.time() - start
                        return {
                            "ok": True,
                            "stable": True,
                            "elapsed": round(elapsed, 1),
                        }
                else:
                    stable_count = 0

            prev_img = current
            time.sleep(interval)

        elapsed = time.time() - start
        return {
            "ok": True,
            "stable": False,
            "elapsed": round(elapsed, 1),
        }

    def record(self, window_title: str = None, duration: int = 10,
               fps: int = 5, name: str = None,
               output_format: str = "gif") -> dict:
        """Record screen as GIF or MP4.

        Captures frames at `fps` for `duration` seconds, then encodes.
        output_format: "gif", "mp4", or "both".
        """
        win = None
        if window_title:
            win = self._safety.find_target_window(window_title)
            self._activate_window(win)

        if name is None:
            name = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        frames = []
        interval = 1.0 / fps
        start = time.time()

        while time.time() - start < duration:
            t0 = time.time()
            if win:
                region = (win.left, win.top, win.width, win.height)
                img = pyautogui.screenshot(region=region)
            else:
                img = pyautogui.screenshot()
            frames.append(img)
            elapsed_frame = time.time() - t0
            if elapsed_frame < interval:
                time.sleep(interval - elapsed_frame)

        if not frames:
            return {"ok": False, "error": "No frames captured"}

        # Resize for output
        target_w = min(frames[0].size[0], 1280)
        scale = target_w / frames[0].size[0]
        target_h = int(frames[0].size[1] * scale)
        # Ensure even dimensions for mp4
        target_w = target_w if target_w % 2 == 0 else target_w - 1
        target_h = target_h if target_h % 2 == 0 else target_h - 1
        resized = [f.resize((target_w, target_h), Image.LANCZOS)
                   for f in frames]

        outputs = {}
        duration_ms = int(1000 / fps)

        if output_format in ("gif", "both"):
            gif_path = self._ss_dir / f"{name}.gif"
            resized[0].save(
                str(gif_path), save_all=True,
                append_images=resized[1:],
                duration=duration_ms, loop=0, optimize=True)
            gif_kb = gif_path.stat().st_size / 1024
            outputs["gif_path"] = str(gif_path)
            outputs["gif_size_kb"] = round(gif_kb, 1)

        if output_format in ("mp4", "both"):
            try:
                import cv2
                mp4_path = self._ss_dir / f"{name}.mp4"
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(
                    str(mp4_path), fourcc, fps, (target_w, target_h))
                for r in resized:
                    frame_bgr = cv2.cvtColor(
                        np.array(r), cv2.COLOR_RGB2BGR)
                    out.write(frame_bgr)
                out.release()
                mp4_kb = mp4_path.stat().st_size / 1024
                outputs["mp4_path"] = str(mp4_path)
                outputs["mp4_size_kb"] = round(mp4_kb, 1)
            except ImportError:
                outputs["mp4_error"] = "opencv-python (cv2) not installed"

        return {
            "ok": True,
            "frames": len(frames),
            "duration": duration,
            "fps": fps,
            "resolution": [target_w, target_h],
            "window": window_title,
            **outputs,
        }


# ---------------------------------------------------------------------------
# PilotIndicator — On-screen activity overlay (subprocess-based)
# ---------------------------------------------------------------------------

# Inline script for the indicator subprocess (avoids tkinter thread issues)
_INDICATOR_SCRIPT = r'''
import tkinter as tk, sys, os
command = sys.argv[1] if len(sys.argv) > 1 else ""
text = f"  Helix Pilot: {command}...  " if command else "  Helix Pilot 動作中...  "
root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-alpha", 0.85)
root.configure(bg="#1a1a2e")
tk.Label(root, text=text, font=("Yu Gothic UI", 11, "bold"),
         fg="#00e5ff", bg="#1a1a2e", padx=12, pady=6).pack()
root.update_idletasks()
w, h = root.winfo_reqwidth(), root.winfo_reqheight()
sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{w}x{h}+{sx - w - 20}+{sy - h - 60}")
root.mainloop()
'''


class PilotIndicator:
    """Small overlay window shown while Helix Pilot is operating.

    Spawns a tiny subprocess that displays a semi-transparent label
    at the bottom-right of the screen. Killed on hide().
    Subprocess approach avoids tkinter-in-thread segfault issues.
    """

    def __init__(self):
        self._proc = None

    def show(self, command: str = ""):
        """Show the indicator by spawning a subprocess."""
        self.hide()  # Clean up any previous
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-c", _INDICATOR_SCRIPT, command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            self._proc = None

    def hide(self):
        """Kill the indicator subprocess."""
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None


# ---------------------------------------------------------------------------
# HelixPilot — Main Orchestrator
# ---------------------------------------------------------------------------
class HelixPilot:
    """Main helix_pilot orchestrator tying all components together."""

    def __init__(self, config_path: Path = None):
        self.config = PilotConfig(config_path)
        self.plogger = PilotLogger(self.config)
        self.safety = SafetyGuard(self.config, self.plogger)
        self.lock = LockManager(self.config)
        self.vision = VisionLLM(self.config, self.plogger)
        self.ops = CoreOperations(self.config, self.safety, self.plogger)
        self.indicator = PilotIndicator()

        # Start user activity monitoring
        self.safety.start_user_monitoring()

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="milliseconds")

    def _with_lock(self, command: str, fn, **kwargs) -> dict:
        """Wrap an operation with lock + safety checks + indicator."""
        window_title = kwargs.get("window_title") or kwargs.get("window")

        if not self.lock.acquire(command, self.config.operation_timeout):
            return {
                "ok": False, "command": command,
                "timestamp": self._now(),
                "error": "Another helix_pilot instance is running",
                "error_type": "PilotLockError",
            }

        # Show on-screen indicator
        self.indicator.show(command)

        try:
            # Safety pre-check
            ok, reason = self.safety.pre_operation_check(window_title)
            if not ok:
                return {
                    "ok": False, "command": command,
                    "timestamp": self._now(),
                    "error": reason,
                    "error_type": "PilotSafetyError",
                }

            # Wait for user idle
            if not self.safety.wait_for_user_idle(max_wait=15.0):
                return {
                    "ok": False, "command": command,
                    "timestamp": self._now(),
                    "error": "User activity detected, operation postponed",
                    "error_type": "PilotTimeoutError",
                }

            # Execute
            result = fn(**kwargs)
            result["command"] = command
            result["timestamp"] = self._now()
            self.plogger.log_operation(command, kwargs, result)
            return result

        except PilotEmergencyStop as e:
            self.plogger.log_safety("emergency_stop", str(e))
            return {
                "ok": False, "command": command,
                "timestamp": self._now(),
                "error": str(e),
                "error_type": "PilotEmergencyStop",
            }
        except PilotWindowNotFoundError as e:
            return {
                "ok": False, "command": command,
                "timestamp": self._now(),
                "error": str(e),
                "error_type": "PilotWindowNotFoundError",
            }
        except PilotVisionError as e:
            self.plogger.log_error(command, str(e))
            return {
                "ok": False, "command": command,
                "timestamp": self._now(),
                "error": str(e),
                "error_type": "PilotVisionError",
            }
        except Exception as e:
            self.plogger.log_error(command, str(e))
            return {
                "ok": False, "command": command,
                "timestamp": self._now(),
                "error": str(e),
                "error_type": type(e).__name__,
            }
        finally:
            self.indicator.hide()
            self.lock.release()

    # --- Commands ---

    def cmd_screenshot(self, window: str = None,
                       name: str = None) -> dict:
        return self._with_lock(
            "screenshot",
            lambda **kw: self.ops.screenshot(kw.get("window"), kw.get("name")),
            window=window, name=name)

    def cmd_click(self, x: int, y: int, window: str = None,
                  button: str = "left", double: bool = False) -> dict:
        clicks = 2 if double else 1

        def _do(window=None, **_kw):
            # Validate window before click
            return self.ops.click(x, y, window, button, clicks)

        return self._with_lock("click", _do, window=window)

    def cmd_type(self, text: str, window: str = None) -> dict:
        def _do(window=None, **_kw):
            ok, reason = self.safety.validate_text_input(text)
            if not ok:
                return {"ok": False, "error": reason,
                        "error_type": "PilotSafetyError"}
            return self.ops.type_text(text, window)

        return self._with_lock("type", _do, window=window)

    def cmd_hotkey(self, keys: str, window: str = None) -> dict:
        def _do(window=None, **_kw):
            # Activate target window before sending hotkey
            if window:
                win = self.safety.find_target_window(window)
                self.ops._activate_window(win)
            return self.ops.hotkey(keys)

        return self._with_lock("hotkey", _do, window=window)

    def cmd_scroll(self, amount: int, window: str = None) -> dict:
        return self._with_lock(
            "scroll",
            lambda window=None, **_kw: self.ops.scroll(amount, window),
            window=window)

    def cmd_click_screenshot(self, x: int, y: int, window: str = None,
                             button: str = "left", double: bool = False,
                             name: str = None, delay: float = 0.3) -> dict:
        """Click then immediately screenshot WITHOUT re-activating the window.

        Designed for QComboBox dropdowns and other popups that close on focus
        change. The screenshot is taken in the same lock context as the click,
        preserving UI state (popups, menus, etc.).
        """
        clicks = 2 if double else 1

        def _do(window=None, **_kw):
            click_result = self.ops.click(x, y, window, button, clicks)
            if not click_result.get("ok"):
                return click_result
            time.sleep(delay)
            # Screenshot WITHOUT activation to preserve popups
            ss_name = name or f"click_ss_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ss = self.ops.screenshot(window, ss_name, activate=False)
            return {
                "ok": True,
                "clicked_at": click_result["clicked_at"],
                "button": button,
                "screenshot_path": ss.get("path"),
                "screenshot_size": ss.get("size"),
                "scale_factor": ss.get("scale_factor"),
                "window": window,
            }

        return self._with_lock("click-screenshot", _do, window=window)

    def cmd_describe(self, window: str = None) -> dict:
        def _do(window=None, **_kw):
            ss = self.ops.screenshot(window, "describe_temp")
            if not ss.get("ok"):
                return ss
            t0 = time.time()
            desc = self.vision.describe(Path(ss["path"]))
            elapsed = round(time.time() - t0, 1)
            return {
                "ok": True,
                "screenshot_path": ss["path"],
                "description": desc,
                "vision_model": self.config.vision_model,
                "vision_elapsed": elapsed,
            }

        return self._with_lock("describe", _do, window=window)

    def cmd_find(self, description: str, window: str = None,
                 refine: bool = False) -> dict:
        def _do(window=None, **_kw):
            ss = self.ops.screenshot(window, "find_temp")
            if not ss.get("ok"):
                return ss
            t0 = time.time()
            result = self.vision.find_element(
                Path(ss["path"]), description)

            # Vision LLM returns coords in screenshot (resized) space.
            # Scale back to original window-relative coordinates.
            scale = ss.get("scale_factor", 1.0)
            raw_x = result.get("x", 0)
            raw_y = result.get("y", 0)

            # Optional refinement: crop around initial estimate, re-query
            refined = False
            if refine and result.get("found"):
                refine_result = self._refine_find(
                    Path(ss["path"]), description, raw_x, raw_y)
                if refine_result and refine_result.get("found"):
                    raw_x = refine_result["x"]
                    raw_y = refine_result["y"]
                    refined = True

            win_x = int(raw_x * scale)
            win_y = int(raw_y * scale)
            elapsed = round(time.time() - t0, 1)

            return {
                "ok": True,
                "screenshot_path": ss["path"],
                "found": result.get("found", False),
                "x": win_x,
                "y": win_y,
                "screenshot_x": raw_x,
                "screenshot_y": raw_y,
                "scale_factor": scale,
                "confidence": result.get("confidence", "none"),
                "element_description": result.get("description", ""),
                "vision_model": self.config.vision_model,
                "vision_elapsed": elapsed,
                "refined": refined,
            }

        return self._with_lock("find", _do, window=window)

    def _refine_find(self, image_path: Path, description: str,
                     est_x: int, est_y: int) -> Optional[dict]:
        """Refine find by cropping around the initial estimate and re-querying.

        Crops a 400x300 region around (est_x, est_y) from the original
        screenshot, then asks Vision LLM for precise coordinates within
        that crop. Maps back to full-screenshot coordinates.
        """
        try:
            img = Image.open(image_path)
            w, h = img.size

            # Crop region: 200px left/right, 150px top/bottom of estimate
            margin_x, margin_y = 200, 150
            crop_left = max(0, est_x - margin_x)
            crop_top = max(0, est_y - margin_y)
            crop_right = min(w, est_x + margin_x)
            crop_bottom = min(h, est_y + margin_y)

            crop = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            crop_path = image_path.parent / "find_refine_crop.png"
            crop.save(str(crop_path))

            result = self.vision.find_element(crop_path, description)
            if result.get("found"):
                # Map crop coordinates back to full screenshot coords
                result["x"] = result.get("x", 0) + crop_left
                result["y"] = result.get("y", 0) + crop_top
            return result
        except Exception:
            return None

    def cmd_verify(self, expected: str, window: str = None) -> dict:
        def _do(window=None, **_kw):
            ss = self.ops.screenshot(window, "verify_temp")
            if not ss.get("ok"):
                return ss
            t0 = time.time()
            result = self.vision.verify_action(
                Path(ss["path"]), expected)
            elapsed = round(time.time() - t0, 1)
            return {
                "ok": True,
                "screenshot_path": ss["path"],
                "success": result.get("success", False),
                "detail": result.get("detail", ""),
                "vision_model": self.config.vision_model,
                "vision_elapsed": elapsed,
            }

        return self._with_lock("verify", _do, window=window)

    def cmd_status(self) -> dict:
        """System status (no lock needed)."""
        # Ollama check
        ollama_ok, ollama_msg = self.vision.check_availability()

        # Visible windows
        try:
            all_wins = gw.getAllWindows()
            visible = []
            for w in all_wins:
                try:
                    title = w.title
                    if title.strip() and w.width > 100 and w.height > 100:
                        # Sanitize for JSON serialization on cp932 systems
                        visible.append(
                            title.encode("utf-8", errors="replace").decode("utf-8"))
                except Exception:
                    pass
        except Exception:
            visible = []

        screen_w, screen_h = pyautogui.size()

        return {
            "ok": True,
            "command": "status",
            "timestamp": self._now(),
            "helix_pilot_version": VERSION,
            "lock": self.lock.is_locked(),
            "ollama": {
                "available": ollama_ok,
                "endpoint": self.config.ollama_endpoint,
                "message": ollama_msg,
            },
            "vision_model": {
                "name": self.config.vision_model,
                "available": ollama_ok,
            },
            "visible_windows": visible[:20],
            "screen_size": [screen_w, screen_h],
            "user_monitoring": "pynput" if HAS_PYNPUT else "polling",
            "emergency_stop_corner": self.config.emergency_stop_corner,
            "safe_mode": self.config.safe_mode,
        }

    def cmd_wait_stable(self, timeout: int = 60,
                        window: str = None) -> dict:
        return self._with_lock(
            "wait-stable",
            lambda window=None, **_kw: self.ops.wait_stable(
                timeout, window),
            window=window)

    def cmd_record(self, window: str = None, duration: int = 10,
                   fps: int = 5, name: str = None,
                   output_format: str = "gif") -> dict:
        """Record screen as GIF/MP4. Lock timeout extended for duration."""
        orig_timeout = self.config.operation_timeout

        def _do(window=None, **_kw):
            return self.ops.record(window, duration, fps, name,
                                   output_format)

        # Temporarily extend lock timeout to cover recording duration
        result = {
            "ok": False, "command": "record",
            "timestamp": self._now(),
        }
        lock_timeout = duration + 30
        if not self.lock.acquire("record", lock_timeout):
            result["error"] = "Another helix_pilot instance is running"
            return result
        self.indicator.show("record")
        try:
            ok, reason = self.safety.pre_operation_check(window)
            if not ok:
                result["error"] = reason
                return result
            if not self.safety.wait_for_user_idle(max_wait=15.0):
                result["error"] = "User activity detected"
                return result
            result = _do(window=window)
            result["command"] = "record"
            result["timestamp"] = self._now()
            self.plogger.log_operation("record", {"window": window,
                "duration": duration, "fps": fps, "format": output_format}, result)
            return result
        except PilotEmergencyStop as e:
            return {"ok": False, "command": "record",
                    "timestamp": self._now(), "error": str(e)}
        except Exception as e:
            return {"ok": False, "command": "record",
                    "timestamp": self._now(), "error": str(e)}
        finally:
            self.indicator.hide()
            self.lock.release()

    def cmd_run_scenario(self, scenario_path: str) -> dict:
        """Execute a JSON scenario file."""
        spath = Path(scenario_path)
        if not spath.is_absolute():
            spath = PROJECT_ROOT / spath

        if not spath.exists():
            return {
                "ok": False, "command": "run-scenario",
                "timestamp": self._now(),
                "error": f"Scenario file not found: {spath}",
            }

        try:
            with open(spath, "r", encoding="utf-8") as f:
                scenario = json.load(f)
        except json.JSONDecodeError as e:
            return {
                "ok": False, "command": "run-scenario",
                "timestamp": self._now(),
                "error": f"Invalid JSON: {e}",
            }

        steps = scenario.get("steps", scenario if isinstance(scenario, list) else [])
        results = []
        scenario_name = scenario.get("name", spath.stem)

        dispatch = {
            "screenshot": lambda a: self.cmd_screenshot(
                a.get("window"), a.get("name")),
            "click": lambda a: self.cmd_click(
                a.get("x", 0), a.get("y", 0), a.get("window"),
                a.get("button", "left"), a.get("double", False)),
            "type": lambda a: self.cmd_type(
                a.get("text", ""), a.get("window")),
            "hotkey": lambda a: self.cmd_hotkey(
                a.get("keys", ""), a.get("window")),
            "click-screenshot": lambda a: self.cmd_click_screenshot(
                a.get("x", 0), a.get("y", 0), a.get("window"),
                a.get("button", "left"), a.get("double", False),
                a.get("name"), a.get("delay", 0.3)),
            "scroll": lambda a: self.cmd_scroll(
                a.get("amount", 0), a.get("window")),
            "describe": lambda a: self.cmd_describe(a.get("window")),
            "find": lambda a: self.cmd_find(
                a.get("description", ""), a.get("window")),
            "verify": lambda a: self.cmd_verify(
                a.get("expected", ""), a.get("window")),
            "wait-stable": lambda a: self.cmd_wait_stable(
                a.get("timeout", 60), a.get("window")),
            "record": lambda a: self.cmd_record(
                a.get("window"), a.get("duration", 10),
                a.get("fps", 5), a.get("name"),
                a.get("format", "gif")),
            "status": lambda a: self.cmd_status(),
        }

        for i, step in enumerate(steps):
            cmd = step.get("command", "")
            args = step.get("args", {})
            delay = step.get("delay_after", 0)
            on_fail = step.get("on_fail", "continue")

            fn = dispatch.get(cmd)
            if fn is None:
                results.append({
                    "step": i + 1, "command": cmd,
                    "ok": False, "error": f"Unknown command: {cmd}",
                })
                if on_fail == "abort":
                    break
                continue

            result = fn(args)
            result["step"] = i + 1
            results.append(result)

            if not result.get("ok", False):
                if on_fail == "abort":
                    break
                elif on_fail.startswith("retry:"):
                    max_retries = int(on_fail.split(":")[1])
                    for retry in range(max_retries):
                        time.sleep(1)
                        result = fn(args)
                        result["step"] = i + 1
                        result["retry"] = retry + 1
                        results[-1] = result
                        if result.get("ok", False):
                            break

            if delay > 0:
                time.sleep(delay)

        all_ok = all(r.get("ok", False) for r in results)
        return {
            "ok": all_ok,
            "command": "run-scenario",
            "timestamp": self._now(),
            "scenario": scenario_name,
            "total_steps": len(steps),
            "executed_steps": len(results),
            "results": results,
        }

    def shutdown(self):
        """Clean shutdown."""
        self.safety.stop_user_monitoring()
        self.lock.release()


# ---------------------------------------------------------------------------
# CLI Parser
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="helix_pilot",
        description="GUI Automation Pilot for Claude Code (v{})".format(VERSION))
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to helix_pilot.json config file")

    sub = parser.add_subparsers(dest="command", required=True)

    # screenshot
    p = sub.add_parser("screenshot", help="Take a screenshot")
    p.add_argument("--window", "-w", type=str, default=None)
    p.add_argument("--name", "-n", type=str, default=None)

    # click
    p = sub.add_parser("click", help="Click at coordinates")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--window", "-w", type=str, default=None)
    p.add_argument("--button", "-b", type=str, default="left",
                   choices=["left", "right", "middle"])
    p.add_argument("--double", action="store_true")

    # type
    p = sub.add_parser("type", help="Type text")
    p.add_argument("text", type=str)
    p.add_argument("--window", "-w", type=str, default=None)

    # hotkey
    p = sub.add_parser("hotkey", help="Press hotkey combination")
    p.add_argument("keys", type=str, help="e.g. ctrl+c, alt+tab")
    p.add_argument("--window", "-w", type=str, default=None)

    # scroll
    p = sub.add_parser("scroll", help="Scroll mouse wheel")
    p.add_argument("amount", type=int,
                   help="Positive=up, negative=down")
    p.add_argument("--window", "-w", type=str, default=None)

    # click-screenshot (combined: click then screenshot without re-activation)
    p = sub.add_parser("click-screenshot",
                       help="Click then screenshot (preserves popups)")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--window", "-w", type=str, default=None)
    p.add_argument("--button", "-b", type=str, default="left",
                   choices=["left", "right", "middle"])
    p.add_argument("--double", action="store_true")
    p.add_argument("--name", "-n", type=str, default=None)
    p.add_argument("--delay", type=float, default=0.3,
                   help="Seconds to wait between click and screenshot (default: 0.3)")

    # describe
    p = sub.add_parser("describe",
                       help="Screenshot + Vision LLM description")
    p.add_argument("--window", "-w", type=str, default=None)

    # find
    p = sub.add_parser("find", help="Find UI element via Vision LLM")
    p.add_argument("description", type=str)
    p.add_argument("--window", "-w", type=str, default=None)
    p.add_argument("--refine", action="store_true",
                   help="Crop around initial estimate and re-query for precision")

    # verify
    p = sub.add_parser("verify",
                       help="Verify action outcome via Vision LLM")
    p.add_argument("expected", type=str)
    p.add_argument("--window", "-w", type=str, default=None)

    # status
    sub.add_parser("status", help="Show system status")

    # wait-stable
    p = sub.add_parser("wait-stable",
                       help="Wait for screen stability")
    p.add_argument("--timeout", "-t", type=int, default=60)
    p.add_argument("--window", "-w", type=str, default=None)

    # record
    p = sub.add_parser("record",
                       help="Record screen as GIF/MP4")
    p.add_argument("--window", "-w", type=str, default=None)
    p.add_argument("--duration", "-d", type=int, default=10,
                   help="Recording duration in seconds (default: 10)")
    p.add_argument("--fps", type=int, default=5,
                   help="Frames per second (default: 5)")
    p.add_argument("--name", "-n", type=str, default=None)
    p.add_argument("--format", "-f", type=str, default="gif",
                   choices=["gif", "mp4", "both"],
                   help="Output format (default: gif)")

    # run-scenario
    p = sub.add_parser("run-scenario", help="Run JSON scenario file")
    p.add_argument("scenario_file", type=str)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Force UTF-8 stdout on Windows (avoid cp932 encoding errors)
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    pilot = HelixPilot(config_path)

    # Register clean shutdown on SIGINT
    def _sigint_handler(sig, frame):
        pilot.shutdown()
        result = {
            "ok": False, "command": args.command,
            "timestamp": pilot._now(),
            "error": "Interrupted by user (Ctrl+C)",
            "error_type": "KeyboardInterrupt",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        dispatch = {
            "screenshot": lambda: pilot.cmd_screenshot(
                getattr(args, "window", None),
                getattr(args, "name", None)),
            "click": lambda: pilot.cmd_click(
                args.x, args.y,
                getattr(args, "window", None),
                getattr(args, "button", "left"),
                getattr(args, "double", False)),
            "type": lambda: pilot.cmd_type(
                args.text,
                getattr(args, "window", None)),
            "hotkey": lambda: pilot.cmd_hotkey(
                args.keys,
                getattr(args, "window", None)),
            "click-screenshot": lambda: pilot.cmd_click_screenshot(
                args.x, args.y,
                getattr(args, "window", None),
                getattr(args, "button", "left"),
                getattr(args, "double", False),
                getattr(args, "name", None),
                getattr(args, "delay", 0.3)),
            "scroll": lambda: pilot.cmd_scroll(
                args.amount,
                getattr(args, "window", None)),
            "describe": lambda: pilot.cmd_describe(
                getattr(args, "window", None)),
            "find": lambda: pilot.cmd_find(
                args.description,
                getattr(args, "window", None),
                getattr(args, "refine", False)),
            "verify": lambda: pilot.cmd_verify(
                args.expected,
                getattr(args, "window", None)),
            "status": lambda: pilot.cmd_status(),
            "wait-stable": lambda: pilot.cmd_wait_stable(
                getattr(args, "timeout", 60),
                getattr(args, "window", None)),
            "record": lambda: pilot.cmd_record(
                getattr(args, "window", None),
                getattr(args, "duration", 10),
                getattr(args, "fps", 5),
                getattr(args, "name", None),
                getattr(args, "format", "gif")),
            "run-scenario": lambda: pilot.cmd_run_scenario(
                args.scenario_file),
        }

        result = dispatch[args.command]()
        print(json.dumps(result, ensure_ascii=False, indent=2))

        exit_code = 0
        if not result.get("ok", False):
            if result.get("error_type") == "PilotEmergencyStop":
                exit_code = 3
            else:
                exit_code = 1

        pilot.shutdown()
        sys.exit(exit_code)

    except Exception as e:
        pilot.shutdown()
        error_result = {
            "ok": False,
            "command": args.command,
            "timestamp": pilot._now(),
            "error": str(e),
            "error_type": type(e).__name__,
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket
import requests

logger = logging.getLogger("lineup.notifier")

# Helper to read from .env if present
def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass

load_env_file()


class ConnectionManager:
    """Manages active WebSockets for Real-Time synchronization across TV, Staff, and Mobile."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast payload to all connected clients."""
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)
        for dead_conn in disconnected:
            self.disconnect(dead_conn)


manager = ConnectionManager()


class TelegramNotifier:
    """Sends queue notifications to Telegram if configured."""
    def __init__(self, bot_token: Optional[str] = None):
        self._bot_token = bot_token
        self._bot_info: Optional[Dict[str, Any]] = None
        self._username_cache: Dict[str, str] = {}  # username.lower() -> chat_id

    def resolve_chat_id(self, target: str) -> Optional[str]:
        """Resolves target string. If it's a number, returns it. If it's a username (e.g. @Lida279), looks up chat_id from bot updates."""
        clean = str(target or "").strip().lstrip("@")
        if not clean:
            return None

        # If it is numeric (e.g. 1748081463 or negative for group -10012345), return directly
        if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
            return clean

        # Check memory cache
        low = clean.lower()
        if low in self._username_cache:
            return self._username_cache[low]

        # Fetch recent bot updates to resolve username -> chat_id
        token = self.get_token()
        if not token:
            return None

        try:
            resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                for item in reversed(data.get("result", [])):
                    msg = item.get("message") or item.get("callback_query", {}).get("message")
                    if msg:
                        frm = msg.get("from") or {}
                        uname = frm.get("username") or ""
                        cid = str(frm.get("id") or "")
                        if uname and cid:
                            self._username_cache[uname.lower()] = cid
                            if uname.lower() == low:
                                logger.info(f"Resolved Telegram username @{uname} -> Chat ID {cid}")
                                return cid
        except Exception as e:
            logger.warning(f"Error resolving username {target}: {e}")

        return None

    def get_token(self) -> Optional[str]:
        """Resolves bot token from memory, env var (.env), or database setting."""
        if self._bot_token and self._bot_token.strip():
            return self._bot_token.strip()

        # Check environment variable (.env)
        env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if env_token and env_token.strip():
            return env_token.strip()

        # Check database settings
        try:
            from app.database import SessionLocal
            from app.models import SystemSetting
            db = SessionLocal()
            try:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "telegram_bot_token").first()
                if setting and setting.value and setting.value.strip():
                    return setting.value.strip()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not load token from db: {e}")

        return None

    def set_token(self, token: str):
        self._bot_token = token.strip() if token else None
        self._bot_info = None

    def get_bot_info(self) -> Dict[str, Any]:
        """Validates token with Telegram API and returns bot details."""
        token = self.get_token()
        if not token:
            return {"configured": False, "message": "Bot token not configured"}

        try:
            resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=6)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                self._bot_info = data.get("result", {})
                return {
                    "configured": True,
                    "valid": True,
                    "bot_name": self._bot_info.get("first_name"),
                    "bot_username": self._bot_info.get("username"),
                    "bot_id": self._bot_info.get("id")
                }
            else:
                return {
                    "configured": True,
                    "valid": False,
                    "error": data.get("description", "Invalid bot token")
                }
        except Exception as e:
            return {"configured": True, "valid": False, "error": str(e)}

    def send_message(self, chat_id: str, text: str) -> bool:
        token = self.get_token()
        raw_target = str(chat_id or "").strip()

        if not token:
            logger.warning(
                f"⚠️ [Telegram Alert Skipped]: TELEGRAM_BOT_TOKEN is not set! "
                f"Could not send message to {raw_target}. "
                f"Please configure TELEGRAM_BOT_TOKEN in .env or via Admin Panel."
            )
            return False

        if not raw_target:
            logger.warning("⚠️ [Telegram Alert Skipped]: No chat_id provided.")
            return False

        # Smart Resolver: auto-resolves usernames (e.g. @Lida279) to numerical Chat ID (1748081463)
        resolved_chat_id = self.resolve_chat_id(raw_target)
        if not resolved_chat_id:
            logger.error(
                f"❌ [Telegram Error] Could not resolve Chat ID for target '{raw_target}'. "
                f"If you provided a username (@{raw_target.lstrip('@')}), please ensure you clicked /start in the bot (@Ltyybot) first, "
                f"or provide your numerical Chat ID (e.g. 1748081463)."
            )
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": resolved_chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, json=payload, timeout=7)
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            if resp.status_code == 200 and data.get("ok"):
                logger.info(f"✅ [Telegram Success] Message delivered to {raw_target} (ID: {resolved_chat_id})")
                return True
            else:
                desc = data.get("description", resp.text)
                logger.error(
                    f"❌ [Telegram Error {resp.status_code}] Failed to send to {raw_target} (ID: {resolved_chat_id}): {desc}. "
                    f"(Note: User must tap /start in the Telegram bot first for the bot to message them)"
                )
                return False
        except Exception as e:
            logger.error(f"❌ [Telegram Connection Error] Could not connect to Telegram: {e}")
            return False

    def notify_ticket_created(self, chat_id: str, ticket_no: str, service_name: str, ahead: int, eta: int):
        msg = (
            f"🎟 <b>LineUp System - សំបុត្រជួរឌីជីថល</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎫 លេខសំបុត្រ: <b>{ticket_no}</b>\n"
            f"🏢 សេវាកម្ម: {service_name}\n"
            f"👥 អ្នកនៅខាងមុខ: <b>{ahead} នាក់</b>\n"
            f"⏳ ម៉ោងប៉ាន់ស្មាន (ETA): <b>~{eta} នាទី</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ប្រព័ន្ធនឹងជូនដំណឹងនៅពេលជិតដល់វេនរបស់អ្នក!"
        )
        return self.send_message(chat_id, msg)

    def notify_almost_turn(self, chat_id: str, ticket_no: str, ahead: int):
        msg = (
            f"⚠️ <b>ការដាស់តឿន: ជិតដល់វេនហើយ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎫 លេខសំបុត្រ: <b>{ticket_no}</b>\n"
            f"👥 នៅសល់តែ <b>{ahead} នាក់ទៀតប៉ុណ្ណោះ</b>!\n"
            f"👉 សូមត្រៀមខ្លួននៅក្បែរបញ្ជរបម្រើសេវា។"
        )
        return self.send_message(chat_id, msg)

    def notify_called(self, chat_id: str, ticket_no: str, counter_number: int):
        msg = (
            f"🔔 <b>ដល់វេនរបស់អ្នកហើយ! (YOUR TURN)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎫 លេខសំបុត្រ: <b>{ticket_no}</b>\n"
            f"👉 សូមអញ្ជើញទៅកាន់: <b>បញ្ជរលេខ {counter_number}</b>\n"
            f"សូមរួសរាន់មកបង្ហាញខ្លួនដើម្បីកុំឱ្យខកខានវេន។"
        )
        return self.send_message(chat_id, msg)

    def notify_completed(self, chat_id: str, ticket_no: str):
        msg = (
            f"✅ <b>LineUp System - សេវាកម្មបានបញ្ចប់</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎫 លេខសំបុត្រ: <b>{ticket_no}</b>\n"
            f"✨ សេវាកម្មបានបញ្ចប់ លែងមានលេខរៀងទៀត។\n"
            f"សូមអរគុណដែលបានប្រើប្រាស់សេវាកម្មរបស់យើងខ្ញុំ! 🙏"
        )
        return self.send_message(chat_id, msg)


# Singleton notifier
telegram_notifier = TelegramNotifier()

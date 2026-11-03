import os
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("lineup.sms")


class SMSNotifier:
    """Dispatches direct SMS notifications to customer phone numbers.
    Supports Twilio, Plasgate/Generic SMS HTTP Gateways, and Demo Simulation Mode.
    """

    def __init__(self):
        self._provider: str = "mock"  # "mock", "twilio", "generic"
        self._twilio_sid: Optional[str] = None
        self._twilio_token: Optional[str] = None
        self._twilio_from: Optional[str] = None
        self._generic_url: Optional[str] = None
        self._generic_key: Optional[str] = None
        self._sender_name: str = "LineUp"
        self._enabled: bool = True
        self.load_settings()

    def load_settings(self):
        """Loads configuration from environment variables or SQLite SystemSetting."""
        self._provider = os.environ.get("SMS_PROVIDER", "mock").lower()
        self._twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self._twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self._twilio_from = os.environ.get("TWILIO_FROM_PHONE")
        self._generic_url = os.environ.get("SMS_GATEWAY_URL")
        self._generic_key = os.environ.get("SMS_GATEWAY_KEY")
        self._sender_name = os.environ.get("SMS_SENDER_NAME", "LineUp")

        try:
            from app.database import SessionLocal
            from app.models import SystemSetting
            db = SessionLocal()
            try:
                settings = db.query(SystemSetting).filter(
                    SystemSetting.key.in_([
                        "sms_enabled", "sms_provider", "twilio_sid",
                        "twilio_token", "twilio_from", "sms_gateway_url",
                        "sms_gateway_key", "sms_sender_name"
                    ])
                ).all()
                for s in settings:
                    if s.key == "sms_enabled":
                        self._enabled = s.value == "true"
                    elif s.key == "sms_provider" and s.value:
                        self._provider = s.value.lower()
                    elif s.key == "twilio_sid":
                        self._twilio_sid = s.value
                    elif s.key == "twilio_token":
                        self._twilio_token = s.value
                    elif s.key == "twilio_from":
                        self._twilio_from = s.value
                    elif s.key == "sms_gateway_url":
                        self._generic_url = s.value
                    elif s.key == "sms_gateway_key":
                        self._generic_key = s.value
                    elif s.key == "sms_sender_name" and s.value:
                        self._sender_name = s.value
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not load SMS settings from DB: {e}")

    def format_phone_international(self, phone: str) -> str:
        """Formats local Cambodian phone numbers (e.g. 012 345 678 -> +85512345678)."""
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits.startswith("0") and len(digits) in [9, 10]:
            return "+855" + digits[1:]
        elif digits.startswith("855"):
            return "+" + digits
        elif not digits.startswith("+"):
            return "+" + digits
        return phone.strip()

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Dispatches SMS to recipient phone number."""
        clean_phone = (to_phone or "").strip()
        if not clean_phone:
            return {"success": False, "error": "No phone number provided"}

        formatted_phone = self.format_phone_international(clean_phone)

        # 1. Twilio Provider
        if self._provider == "twilio" and self._twilio_sid and self._twilio_token:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self._twilio_sid}/Messages.json"
            data = {
                "From": self._twilio_from or self._sender_name,
                "To": formatted_phone,
                "Body": message
            }
            try:
                resp = requests.post(url, data=data, auth=(self._twilio_sid, self._twilio_token), timeout=8)
                if resp.status_code in [200, 201]:
                    logger.info(f"✅ [Twilio SMS Delivered] to {formatted_phone}")
                    return {"success": True, "provider": "twilio", "data": resp.json()}
                else:
                    logger.error(f"❌ [Twilio SMS Error {resp.status_code}]: {resp.text}")
                    return {"success": False, "provider": "twilio", "error": resp.text}
            except Exception as e:
                logger.error(f"❌ [Twilio Connection Error]: {e}")
                return {"success": False, "provider": "twilio", "error": str(e)}

        # 2. Generic HTTP SMS Gateway (Plasgate, MekongSMS, etc.)
        elif self._provider == "generic" and self._generic_url:
            headers = {"Content-Type": "application/json"}
            if self._generic_key:
                headers["Authorization"] = f"Bearer {self._generic_key}"
            payload = {
                "to": formatted_phone,
                "sender": self._sender_name,
                "content": message
            }
            try:
                resp = requests.post(self._generic_url, json=payload, headers=headers, timeout=8)
                if resp.status_code in [200, 201]:
                    logger.info(f"✅ [Gateway SMS Delivered] to {formatted_phone}")
                    return {"success": True, "provider": "generic", "data": resp.text}
                else:
                    logger.error(f"❌ [Gateway SMS Error {resp.status_code}]: {resp.text}")
                    return {"success": False, "provider": "generic", "error": resp.text}
            except Exception as e:
                logger.error(f"❌ [Gateway Connection Error]: {e}")
                return {"success": False, "provider": "generic", "error": str(e)}

        # 3. Simulation / Demo Mode (Logs nicely in console without needing paid gateway)
        else:
            logger.info(
                f"📱 [Simulated SMS to {clean_phone} ({formatted_phone})]:\n"
                f"   \"{message}\""
            )
            return {
                "success": True,
                "provider": "mock",
                "phone": clean_phone,
                "formatted_phone": formatted_phone,
                "message": message,
                "notice": "Simulated SMS (No paid SMS Gateway configured. Real SMS will be sent when Twilio or Plasgate is connected)."
            }

    # High-level queue notifications
    def notify_ticket_created(self, phone: str, ticket_no: str, service_name: str, ahead: int, eta: int):
        text = f"LineUp: សំបុត្រ {ticket_no} ({service_name}) ទទួលបានជោគជ័យ! នៅខាងមុខ {ahead} នាក់, ម៉ោងប៉ាន់ស្មាន ~{eta} នាទី។"
        return self.send_sms(phone, text)

    def notify_almost_turn(self, phone: str, ticket_no: str, ahead: int):
        text = f"LineUp [ជិតដល់វេន]: សំបុត្រ {ticket_no} នៅសល់តែ {ahead} នាក់ទៀតប៉ុណ្ណោះ! សូមត្រៀមខ្លួននៅក្បែរបញ្ជរ។"
        return self.send_sms(phone, text)

    def notify_called(self, phone: str, ticket_no: str, counter_number: int):
        text = f"LineUp [ដល់វេនហើយ!]: សំបុត្រ {ticket_no} សូមអញ្ជើញទៅកាន់ បញ្ជរលេខ {counter_number}។"
        return self.send_sms(phone, text)

    def notify_completed(self, phone: str, ticket_no: str):
        text = f"LineUp [រួចរាល់]: សំបុត្រ {ticket_no} បានបញ្ចប់សេវា។ លែងមានលេខរៀងទៀត។ សូមអរគុណ!"
        return self.send_sms(phone, text)


# Singleton
sms_notifier = SMSNotifier()

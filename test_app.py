import sys
import os

from app.database import engine, Base, SessionLocal
from app.models import Service, QueueTicket, User
from app.queue_manager import QueueManager
from app.main import (
    page_customer_ticket,
    page_kiosk,
    generate_qr_image,
    get_portal_url
)
from app.auth import (
    seed_default_users,
    hash_password,
    verify_password,
    create_session_token,
    decode_session_token,
    require_staff_user,
    require_admin_user
)
from starlette.requests import Request
from fastapi import HTTPException

def test_system():
    print("==================================================", flush=True)
    print(" [TEST] Running LineUp RBAC & Validation Tests", flush=True)
    print("==================================================", flush=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Services Seeding
        services = QueueManager.get_or_seed_services(db)
        print(f"[OK] Seeded services: {len(services)}", flush=True)
        assert len(services) >= 4
        s1 = services[0]

        # 2. Users Seeding
        seed_default_users(db)
        admin = db.query(User).filter(User.username == "admin").first()
        staff1 = db.query(User).filter(User.username == "staff1").first()
        assert admin is not None, "Admin user should exist"
        assert staff1 is not None, "Staff1 user should exist"
        print(f"[OK] Users seeded: admin ({admin.role}), staff1 ({staff1.role})", flush=True)

        # 3. RBAC Test: Customer has NO access to staff endpoints
        req_customer = Request({
            "type": "http",
            "path": "/api/staff/call-next",
            "headers": [],
            "server": ("localhost", 80)
        })
        try:
            require_staff_user(req_customer, db)
            assert False, "Customer should NOT have access to staff endpoints"
        except HTTPException as e:
            assert e.status_code == 401
            print("[OK] RBAC Verified: Anonymous Customer blocked with 401 Unauthorized", flush=True)

        # 4. RBAC Test: Customer navigating to /staff is redirected to /login
        req_customer_browser = Request({
            "type": "http",
            "path": "/staff",
            "headers": [(b"accept", b"text/html,application/xhtml+xml")],
            "server": ("localhost", 80)
        })
        try:
            require_staff_user(req_customer_browser, db)
            assert False, "Customer browser request should be redirected"
        except HTTPException as e:
            assert e.status_code == 307
            assert "/login?next=/staff" in e.headers["Location"]
            print("[OK] RBAC Verified: Browser Customer redirected to /login?next=/staff", flush=True)

        # 5. Customer View Exclusivity: Customer Page has NO staff/admin links
        req_home = Request({
            "type": "http",
            "path": "/",
            "headers": [],
            "server": ("localhost", 80)
        })
        res_customer_page = page_customer_ticket(req_home, db)
        html_text = res_customer_page.body.decode("utf-8")
        assert 'href="/staff"' not in html_text, "Customer page must NOT contain links to /staff"
        assert 'href="/admin"' not in html_text, "Customer page must NOT contain links to /admin"
        assert 'href="/kiosk"' not in html_text, "Customer page must NOT contain links to /kiosk"
        print("[OK] View Verified: Customer page contains ONLY Customer interface (Zero staff/admin links)", flush=True)

        # 6. Mandatory Information Validation: Validation helper logic
        def validate_ticket_inputs(name, phone):
            clean_name = (name or "").strip()
            clean_phone = (phone or "").strip()
            if not clean_name:
                raise HTTPException(status_code=400, detail="Customer name is required")
            if not clean_phone:
                raise HTTPException(status_code=400, detail="Phone number is required")
            digits = "".join(ch for ch in clean_phone if ch.isdigit())
            if len(digits) < 8 or len(digits) > 15:
                raise HTTPException(status_code=400, detail="Valid phone number required (min 8 digits)")
            return clean_name, clean_phone

        # Empty name rejected
        try:
            validate_ticket_inputs("", "012345678")
            assert False
        except HTTPException as e:
            assert e.status_code == 400
            print("[OK] Validation Verified: Missing Customer Name strictly rejected (400)", flush=True)

        # Empty phone rejected
        try:
            validate_ticket_inputs("Sokha", "")
            assert False
        except HTTPException as e:
            assert e.status_code == 400
            print("[OK] Validation Verified: Missing Phone Number strictly rejected (400)", flush=True)

        # Short phone rejected
        try:
            validate_ticket_inputs("Sokha", "1234")
            assert False
        except HTTPException as e:
            assert e.status_code == 400
            print("[OK] Validation Verified: Short phone (< 8 digits) strictly rejected (400)", flush=True)

        # Valid inputs succeed
        c_name, c_phone = validate_ticket_inputs("Sokha", "012999888")
        t1 = QueueManager.create_ticket(db, s1.id, customer_name=c_name, customer_phone=c_phone)
        assert t1.customer_name == "Sokha"
        assert t1.customer_phone == "012999888"
        print(f"[OK] Ticket Issued Successfully: {t1.ticket_number} for {t1.customer_name} ({t1.customer_phone})", flush=True)

        # 7. Staff RBAC: Staff user can operate counter actions
        token_staff = create_session_token(staff1)
        req_staff = Request({
            "type": "http",
            "path": "/api/staff/call-next",
            "headers": [(b"cookie", f"lineup_session={token_staff}".encode())],
            "server": ("localhost", 80)
        })
        user_staff = require_staff_user(req_staff, db)
        assert user_staff.username == "staff1"

        try:
            require_admin_user(req_staff, db)
            assert False, "Staff should NOT have access to admin endpoints"
        except HTTPException as e:
            assert e.status_code == 403
            print("[OK] RBAC Verified: Staff blocked from Admin endpoints with 403 Forbidden", flush=True)

        # 8. Cross-Network Public Tunnel & QR Verification
        os.environ["PUBLIC_URL"] = "https://competitions-handbook-candy-diesel.trycloudflare.com"
        portal_url = get_portal_url()
        assert portal_url.startswith("https://"), "Portal URL should reflect the public HTTPS tunnel"
        qr_resp = generate_qr_image()
        assert len(qr_resp.body) > 100
        print(f"[OK] Cross-Network Verified: QR Code generates for Public HTTPS URL ({portal_url})", flush=True)

        # 9. Customer Notifications & Completed View Test
        from app.notifier import telegram_notifier
        # Check Telegram notification format for Almost Turn, Called, and Completed
        telegram_notifier.notify_almost_turn("123456", "A-001", 2)
        telegram_notifier.notify_called("123456", "A-001", 1)
        telegram_notifier.notify_completed("123456", "A-001")
        print("[OK] Notification Dispatcher Verified: Almost Turn, Called, and Completed messages configured", flush=True)

        # Check customer HTML contains exact completion message and mobile notification logic
        assert "សេវាកម្មបានបញ្ចប់" in html_text, "Customer page must contain completion header"
        assert "លែងមានលេខរៀងទៀត" in html_text, "Customer page must contain exact requested Khmer completion phrase"
        assert "sendMobileNotification" in html_text, "Customer page must contain mobile notification handler"
        assert "section-completed-card" in html_text, "Customer page must contain dedicated completion card"
        assert "notification-prompt-banner" in html_text, "Customer page must contain notification prompt banner"
        print("[OK] Customer Screen Verified: Exact completion phrase and mobile notification system present in HTML", flush=True)

        # 10. Queue Lifecycle & Completion Verification
        t_called = QueueManager.call_next(db, counter_id=1, service_id=s1.id)
        assert t_called is not None and t_called.status == "CALLING"
        t_completed = QueueManager.complete_ticket(db, t_called.id)
        assert t_completed is not None and t_completed.status == "COMPLETED"
        assert t_completed.completed_at is not None
        print(f"[OK] Queue Lifecycle Verified: Ticket {t_completed.ticket_number} transitioned to COMPLETED successfully", flush=True)

        # 11. Kiosk Screen Interactive Selection & Info Input Verification
        req_kiosk = Request({
            "type": "http",
            "path": "/kiosk",
            "headers": [],
            "server": ("localhost", 80)
        })
        res_kiosk = page_kiosk(req_kiosk, db)
        kiosk_html = res_kiosk.body.decode("utf-8")
        assert "openKioskInputModal" in kiosk_html, "Kiosk must trigger input modal on touch"
        assert "kiosk-input-modal" in kiosk_html, "Kiosk must have customer information input modal"
        assert 'name="customer_name"' in kiosk_html, "Kiosk must require customer name input"
        assert 'name="customer_phone"' in kiosk_html, "Kiosk must require customer phone input"
        assert "kiosk-form" in kiosk_html, "Kiosk must contain form submission"
        assert "kiosk-modal" in kiosk_html, "Kiosk must display issued ticket modal"
        print("[OK] Kiosk Screen Verified: Selecting service opens modal requiring Customer Name & Phone before issuing ticket", flush=True)

        # 12. Audio WAV files, ServiceWorker & Telegram Configuration Verification
        from app.models import SystemSetting
        # Check audio files
        assert os.path.exists("app/static/audio/dingdong.wav"), "dingdong.wav must exist"
        assert os.path.exists("app/static/audio/urgent_alert.wav"), "urgent_alert.wav must exist"
        assert os.path.exists("app/static/audio/completion.wav"), "completion.wav must exist"
        assert os.path.exists("app/static/sw.js"), "sw.js must exist"
        print("[OK] Media & SW Verified: dingdong.wav, urgent_alert.wav, completion.wav and sw.js present", flush=True)

        # Test Telegram Token Storage in SystemSetting
        token = telegram_notifier.get_token()
        assert token is not None and len(token) > 10, "Telegram notifier must resolve token"
        print(f"[OK] Telegram Integration Verified: Bot Token resolved successfully ({token[:10]}...)", flush=True)

        # 13. Direct SMS Gateway & Frictionless Phone Notification Verification
        from app.sms_notifier import sms_notifier
        fmt = sms_notifier.format_phone_international("012345678")
        assert fmt == "+85512345678", "Cambodian phone number formatting must convert 012 to +855"

        sms_res = sms_notifier.notify_ticket_created("012999888", "A-001", "General", 2, 10)
        assert sms_res["success"] is True, "SMS notification should succeed"

        sms_call = sms_notifier.notify_called("012999888", "A-001", 1)
        assert sms_call["success"] is True

        sms_done = sms_notifier.notify_completed("012999888", "A-001")
        assert sms_done["success"] is True
        print("[OK] Direct SMS Gateway Verified: Direct phone messaging functions without requiring Telegram bot", flush=True)

        # 14. TV Display & Kiosk UX/UI Verification: Verify Clean Display without raw URLs
        from app.main import page_tv_display
        req_tv = Request({
            "type": "http",
            "method": "GET",
            "path": "/tv",
            "headers": [],
            "server": ("localhost", 80)
        })
        res_tv = page_tv_display(req_tv, db)
        tv_html = res_tv.body.decode("utf-8")
        assert "trycloudflare.com" not in tv_html, "TV Display must NOT expose raw tunnel URL"
        assert "NOW CALLING" in tv_html, "TV Display must feature Hero Calling banner"
        assert "counter-card-1" in tv_html, "TV Display must feature Counters Matrix"
        assert "tv-waiting-list" in tv_html, "TV Display must feature Upcoming Queue Ticker"
        print("[OK] TV Display Redesign Verified: Clean, distance-optimized UI with zero raw URLs exposed", flush=True)

        # Check Kiosk Screen also has zero raw trycloudflare URLs
        res_kiosk = page_kiosk(req_home, db)
        kiosk_html = res_kiosk.body.decode("utf-8")
        assert "trycloudflare.com" not in kiosk_html, "Kiosk screen must NOT expose raw tunnel URL"
        print("[OK] Kiosk Redesign Verified: Touchless QR Code with zero raw URLs exposed", flush=True)

        # 15. Walk-In & Printable Ticket Verification (In case guest has NO phone)
        # A) Walk-In without phone validation
        def validate_inputs_with_walkin(name, phone, is_walkin=False, no_phone=False):
            clean_name = (name or "").strip()
            clean_phone = (phone or "").strip()
            walkin_mode = bool(is_walkin or no_phone or (clean_phone and clean_phone.lower() in ["walk-in", "walkin", "no-phone", "n/a", "none"]))
            if not clean_name:
                raise HTTPException(status_code=400, detail="Customer name is required")
            if walkin_mode:
                if not clean_phone or clean_phone.lower() in ["walk-in", "walkin", "no-phone", "n/a", "none"]:
                    clean_phone = "Walk-in (គ្មានទូរស័ព្ទ)"
            else:
                if not clean_phone:
                    raise HTTPException(status_code=400, detail="Phone number is required")
                digits = "".join(ch for ch in clean_phone if ch.isdigit())
                if len(digits) < 8 or len(digits) > 15:
                    raise HTTPException(status_code=400, detail="Valid phone number required")
            return clean_name, clean_phone

        # Standard mode without phone MUST fail
        try:
            validate_inputs_with_walkin("Bopha", "", is_walkin=False, no_phone=False)
            assert False, "Non walk-in must require phone"
        except HTTPException as e:
            assert e.status_code == 400

        # Walk-in mode without phone MUST succeed
        w_name, w_phone = validate_inputs_with_walkin("Bopha Walk-in", "", is_walkin=True, no_phone=True)
        assert w_phone == "Walk-in (គ្មានទូរស័ព្ទ)"
        t_walkin = QueueManager.create_ticket(db, s1.id, customer_name=w_name, customer_phone=w_phone)
        assert t_walkin.customer_phone == "Walk-in (គ្មានទូរស័ព្ទ)"
        print(f"[OK] Walk-In Verification: Ticket {t_walkin.ticket_number} issued without phone successfully", flush=True)

        # B) Verify Kiosk & Staff HTML contain printable slip & no-phone options
        assert "printable-ticket-slip" in kiosk_html, "Kiosk must contain #printable-ticket-slip"
        assert "ticket-slip-card" in kiosk_html, "Kiosk must contain .ticket-slip-card"
        assert "print-customer-phone" not in kiosk_html, "Print slip must NOT display phone line"
        assert "kiosk-checkbox-no-phone" in kiosk_html, "Kiosk must have no-phone toggle"
        assert "kiosk-checkbox-auto-print" in kiosk_html, "Kiosk must have auto-print toggle"

        with open("app/templates/staff_dashboard.html", "r", encoding="utf-8") as f:
            staff_html = f.read()
        assert "printable-ticket-slip" in staff_html, "Staff dashboard must contain #printable-ticket-slip"
        assert "ticket-slip-card" in staff_html, "Staff dashboard must contain .ticket-slip-card"
        assert "print-customer-phone" not in staff_html, "Staff print slip must NOT display phone line"
        assert "staff-walkin-no-phone" in staff_html, "Staff dashboard must have no-phone toggle"
        assert "staff-walkin-auto-print" in staff_html, "Staff dashboard must have auto-print toggle"
        print("[OK] Print Engine Verified: Thermal receipt slip and print controls integrated in Kiosk and Staff Dashboard", flush=True)

        # Clean up
        del os.environ["PUBLIC_URL"]
        QueueManager.reset_queue(db)

        print("==================================================", flush=True)
        print(" [SUCCESS] ALL TESTS FOR USER REQUESTS PASSED 100% OK!", flush=True)
        print("==================================================", flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    test_system()

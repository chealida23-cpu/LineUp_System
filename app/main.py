import os
import io
import socket
import asyncio
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import qrcode

from app.database import engine, Base, get_db, SessionLocal
from app.models import QueueTicket, Service, User, SystemSetting
from app.schemas import TicketCreate, CallNextRequest, TicketAction
from app.queue_manager import QueueManager
from app.notifier import manager, telegram_notifier
from app.sms_notifier import sms_notifier
from app.auth import (
    seed_default_users,
    require_staff_user,
    require_admin_user,
    get_current_user_optional,
    verify_password,
    create_session_token,
    COOKIE_NAME,
    SESSION_MAX_AGE,
    hash_password
)

# Helper to find LAN IP for local WiFi presentation (cached)
_CACHED_LOCAL_IP = None

def get_local_ip() -> str:
    global _CACHED_LOCAL_IP
    if _CACHED_LOCAL_IP:
        return _CACHED_LOCAL_IP

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.2)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    
    _CACHED_LOCAL_IP = IP
    return IP

def get_portal_url() -> str:
    """Returns Public Internet URL (for cross-network scanning) or LAN IP."""
    pub = os.environ.get("PUBLIC_URL")
    if pub:
        return pub.rstrip("/") + "/"
    return f"http://{get_local_ip()}:8000/"

AUTO_NOSHOW_TIMEOUT_SECONDS = 180  # 3 minutes

async def auto_noshow_background_worker():
    """Background task running every 15s to auto mark unattended calls as NO_SHOW."""
    while True:
        try:
            await asyncio.sleep(15)
            db = SessionLocal()
            try:
                expired = QueueManager.auto_check_no_show(db, timeout_seconds=AUTO_NOSHOW_TIMEOUT_SECONDS)
                if expired:
                    await manager.broadcast({
                        "event": "TICKETS_EXPIRED_NOSHOW",
                        "ticket_ids": [t.id for t in expired],
                        "tv_state": QueueManager.get_public_tv_state(db),
                        "stats": QueueManager.get_statistics(db)
                    })
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database Schema
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        QueueManager.get_or_seed_services(db)
        seed_default_users(db)
    finally:
        db.close()
    
    # Start auto no-show background worker
    worker_task = asyncio.create_task(auto_noshow_background_worker())
    yield
    worker_task.cancel()

app = FastAPI(title="LineUp System - Smart Virtual Queue", lifespan=lifespan)

# Mount static and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ==============================================================================
# Web Interface Pages & Authentication
# ==============================================================================

@app.get("/login", response_class=HTMLResponse)
def page_login(request: Request, next: Optional[str] = "/staff", db: Session = Depends(get_db)):
    """Login portal for Staff and Admin."""
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url=next or "/staff")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"current_user": None, "next_url": next}
    )

@app.post("/api/login")
def api_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate staff or admin, issue session cookie."""
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវ / Invalid username or password"
        )

    token = create_session_token(user)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax"
    )
    return {"status": "success", "user": user.to_dict()}

@app.get("/logout")
def page_logout():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login")
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/api/auth/me")
def api_auth_me(request: Request, db: Session = Depends(get_db)):
    """Return currently logged-in user profile, or anonymous customer."""
    user = get_current_user_optional(request, db)
    if not user:
        return {"authenticated": False, "role": "customer"}
    return {"authenticated": True, "user": user.to_dict()}

@app.get("/", response_class=HTMLResponse)
def page_customer_ticket(request: Request, db: Session = Depends(get_db)):
    """Customer Mobile Web Portal to get a digital ticket or check ongoing queue (Public)."""
    services = db.query(Service).filter(Service.is_active == True).all()
    current_user = get_current_user_optional(request, db)
    local_ip = get_local_ip()
    portal_url = get_portal_url()
    is_public = bool(os.environ.get("PUBLIC_URL"))
    return templates.TemplateResponse(
        request=request,
        name="customer_ticket.html",
        context={
            "services": services,
            "local_ip": local_ip,
            "portal_url": portal_url,
            "is_public": is_public,
            "current_user": current_user
        }
    )

@app.get("/staff", response_class=HTMLResponse)
def page_staff_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    """Staff & Admin Operational Dashboard (Staff / Admin Protected)."""
    services = db.query(Service).filter(Service.is_active == True).all()
    stats = QueueManager.get_statistics(db)
    local_ip = get_local_ip()
    portal_url = get_portal_url()
    is_public = bool(os.environ.get("PUBLIC_URL"))
    return templates.TemplateResponse(
        request=request,
        name="staff_dashboard.html",
        context={
            "services": services,
            "stats": stats,
            "local_ip": local_ip,
            "portal_url": portal_url,
            "is_public": is_public,
            "current_user": current_user
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def page_admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """System Administration Panel (Admin Only)."""
    services = db.query(Service).all()
    users = db.query(User).all()
    local_ip = get_local_ip()
    portal_url = get_portal_url()
    is_public = bool(os.environ.get("PUBLIC_URL"))
    return templates.TemplateResponse(
        request=request,
        name="admin_panel.html",
        context={
            "services": services,
            "users": users,
            "local_ip": local_ip,
            "portal_url": portal_url,
            "is_public": is_public,
            "current_user": admin_user
        }
    )

@app.get("/tv", response_class=HTMLResponse)
def page_tv_display(request: Request, db: Session = Depends(get_db)):
    """Public TV Display Screen with Sound and Voice Announcement (Public)."""
    current_user = get_current_user_optional(request, db)
    local_ip = get_local_ip()
    portal_url = get_portal_url()
    is_public = bool(os.environ.get("PUBLIC_URL"))
    return templates.TemplateResponse(
        request=request,
        name="tv_display.html",
        context={
            "local_ip": local_ip,
            "portal_url": portal_url,
            "is_public": is_public,
            "current_user": current_user
        }
    )

@app.get("/kiosk", response_class=HTMLResponse)
def page_kiosk(request: Request, db: Session = Depends(get_db)):
    """Walk-up QR Kiosk Display for physical venue entrance (Public)."""
    services = db.query(Service).filter(Service.is_active == True).all()
    current_user = get_current_user_optional(request, db)
    local_ip = get_local_ip()
    portal_url = get_portal_url()
    is_public = bool(os.environ.get("PUBLIC_URL"))
    return templates.TemplateResponse(
        request=request,
        name="kiosk.html",
        context={
            "services": services,
            "local_ip": local_ip,
            "portal_url": portal_url,
            "is_public": is_public,
            "current_user": current_user
        }
    )


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.get("/api/services")
def list_services(db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.is_active == True).all()
    return [s.to_dict() for s in services]

@app.post("/api/ticket/generate")
async def generate_ticket(
    service_id: int = Form(...),
    customer_name: str = Form(...),
    customer_phone: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    is_walkin: Optional[bool] = Form(False),
    no_phone: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """Customer gets a new virtual ticket (Name is mandatory; Phone mandatory unless Walk-in / No Phone)."""
    clean_name = (customer_name or "").strip() if isinstance(customer_name, str) else ""
    clean_phone = (customer_phone or "").strip() if isinstance(customer_phone, str) else ""
    clean_telegram = telegram_chat_id.strip() if isinstance(telegram_chat_id, str) else None

    walkin_mode = bool(is_walkin or no_phone or (clean_phone and clean_phone.lower() in ["walk-in", "walkin", "no-phone", "n/a", "none"]))

    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="សូមបញ្ចូលឈ្មោះរបស់អ្នក! / Customer name is required."
        )

    if walkin_mode:
        # Walk-in ticket mode (for guests without a smartphone/phone)
        if not clean_phone or clean_phone.lower() in ["walk-in", "walkin", "no-phone", "n/a", "none"]:
            clean_phone = "Walk-in (គ្មានទូរស័ព្ទ)"
    else:
        # Standard customer online ticket requires a valid phone number
        if not clean_phone:
            raise HTTPException(
                status_code=400,
                detail="សូមបញ្ចូលលេខទូរស័ព្ទរបស់អ្នក! / Phone number is required."
            )

        # Validate phone digits (min 8 digits)
        phone_digits = "".join(ch for ch in clean_phone if ch.isdigit())
        if len(phone_digits) < 8 or len(phone_digits) > 15:
            raise HTTPException(
                status_code=400,
                detail="លេខទូរស័ព្ទមិនត្រឹមត្រូវ! ត្រូវមានយ៉ាងតិច ៨ ខ្ទង់ / Valid phone number required (min 8 digits)."
            )

    ticket = QueueManager.create_ticket(
        db=db,
        service_id=service_id,
        customer_name=clean_name,
        customer_phone=clean_phone,
        telegram_chat_id=clean_telegram
    )

    eta_data = QueueManager.calculate_eta_and_ahead(db, ticket)
    ticket_dict = ticket.to_dict()
    ticket_dict.update(eta_data)

    # Direct SMS Notification to Customer Phone Number (if valid phone provided)
    phone_digits = "".join(ch for ch in clean_phone if ch.isdigit())
    if len(phone_digits) >= 8:
        sms_notifier.notify_ticket_created(
            phone=clean_phone,
            ticket_no=ticket.ticket_number,
            service_name=ticket.service.name if ticket.service else "Service",
            ahead=eta_data["ahead_count"],
            eta=eta_data["estimated_wait_minutes"]
        )

    # Optional Telegram Notification (if provided)
    if clean_telegram:
        telegram_notifier.notify_ticket_created(
            chat_id=clean_telegram,
            ticket_no=ticket.ticket_number,
            service_name=ticket.service.name if ticket.service else "Service",
            ahead=eta_data["ahead_count"],
            eta=eta_data["estimated_wait_minutes"]
        )

    # Broadcast event to WebSockets
    await manager.broadcast({
        "event": "TICKET_CREATED",
        "ticket": ticket_dict,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })

    return {"status": "success", "ticket": ticket_dict}

@app.get("/api/ticket/{ticket_id}/status")
def get_ticket_status(ticket_id: int, db: Session = Depends(get_db)):
    """Customer polls or verifies current ticket progress."""
    ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    eta_data = QueueManager.calculate_eta_and_ahead(db, ticket)
    ticket_dict = ticket.to_dict()
    ticket_dict.update(eta_data)
    return ticket_dict

@app.post("/api/ticket/{ticket_id}/cancel")
async def cancel_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = QueueManager.cancel_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await manager.broadcast({
        "event": "TICKET_CANCELLED",
        "ticket_id": ticket_id,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "message": "Ticket cancelled"}


# --- Staff Operations (Staff or Admin Protected) ---

@app.post("/api/staff/call-next")
async def call_next_customer(
    counter_id: int = Form(1),
    service_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    """Picks next customer waiting in queue, updates status to CALLING, triggers TV Chime & Speech."""
    ticket = QueueManager.call_next(db, counter_id=counter_id, service_id=service_id)
    if not ticket:
        return {"status": "empty", "message": "មិនមានអតិថិជនរង់ចាំទេ / No customers in queue"}

    ticket_dict = ticket.to_dict()

    # Direct SMS Notification to Called Customer
    if ticket.customer_phone:
        sms_notifier.notify_called(
            phone=ticket.customer_phone,
            ticket_no=ticket.ticket_number,
            counter_number=counter_id
        )

    # Alert the called customer via Telegram if registered
    if ticket.telegram_chat_id:
        telegram_notifier.notify_called(
            chat_id=ticket.telegram_chat_id,
            ticket_no=ticket.ticket_number,
            counter_number=counter_id
        )

    # Broadcast event to WebSockets
    await manager.broadcast({
        "event": "TICKET_CALLED",
        "ticket": ticket_dict,
        "counter": counter_id,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })

    # Alert the next 2 customers that their turn is coming up!
    waiting_next = db.query(QueueTicket).filter(
        QueueTicket.status == "WAITING",
        QueueTicket.service_id == ticket.service_id
    ).order_by(QueueTicket.created_at.asc()).limit(2).all()

    for idx, w_ticket in enumerate(waiting_next, start=1):
        if w_ticket.customer_phone:
            sms_notifier.notify_almost_turn(w_ticket.customer_phone, w_ticket.ticket_number, idx)
        if w_ticket.telegram_chat_id:
            telegram_notifier.notify_almost_turn(w_ticket.telegram_chat_id, w_ticket.ticket_number, idx)

    return {"status": "success", "ticket": ticket_dict}

@app.post("/api/staff/recall")
async def recall_customer(
    ticket_id: int = Form(...),
    counter_id: int = Form(1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    ticket = QueueManager.recall_ticket(db, ticket_id=ticket_id, counter_id=counter_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_dict = ticket.to_dict()

    # Direct SMS Notification on Recall
    if ticket.customer_phone:
        sms_notifier.notify_called(
            phone=ticket.customer_phone,
            ticket_no=ticket.ticket_number,
            counter_number=counter_id
        )

    await manager.broadcast({
        "event": "TICKET_RECALLED",
        "ticket": ticket_dict,
        "counter": counter_id,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "ticket": ticket_dict}

@app.post("/api/staff/serve")
async def start_serve_customer(
    ticket_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    ticket = QueueManager.start_serving(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_dict = ticket.to_dict()
    await manager.broadcast({
        "event": "TICKET_SERVED",
        "ticket": ticket_dict,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "ticket": ticket_dict}

@app.post("/api/staff/complete")
async def complete_customer(
    ticket_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    ticket = QueueManager.complete_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_dict = ticket.to_dict()

    # Send completion notification via Direct SMS
    if ticket.customer_phone:
        sms_notifier.notify_completed(
            phone=ticket.customer_phone,
            ticket_no=ticket.ticket_number
        )

    # Send completion notification via Telegram if registered
    if ticket.telegram_chat_id:
        telegram_notifier.notify_completed(
            chat_id=ticket.telegram_chat_id,
            ticket_no=ticket.ticket_number
        )

    await manager.broadcast({
        "event": "TICKET_COMPLETED",
        "ticket": ticket_dict,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "ticket": ticket_dict}

@app.post("/api/staff/no-show")
async def mark_no_show_customer(
    ticket_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    ticket = QueueManager.mark_no_show(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_dict = ticket.to_dict()
    await manager.broadcast({
        "event": "TICKET_NOSHOW",
        "ticket": ticket_dict,
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "ticket": ticket_dict}

@app.get("/api/staff/queue-data")
def get_staff_queue_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_user)
):
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    all_tickets = db.query(QueueTicket).filter(
        QueueTicket.created_at >= today_start
    ).order_by(QueueTicket.created_at.asc()).all()

    waiting = [t.to_dict() for t in all_tickets if t.status == "WAITING"]
    calling_or_serving = [t.to_dict() for t in all_tickets if t.status in ["CALLING", "SERVING"]]
    history = [t.to_dict() for t in all_tickets if t.status in ["COMPLETED", "NO_SHOW", "CANCELLED"]]
    history.reverse()

    return {
        "waiting": waiting,
        "calling_or_serving": calling_or_serving,
        "history": history,
        "stats": QueueManager.get_statistics(db)
    }


# --- Admin Operations (Admin Only Protected) ---

@app.post("/api/staff/reset-queue")
async def reset_queue_action(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """Admin-only reset of the entire queue."""
    QueueManager.reset_queue(db)
    await manager.broadcast({
        "event": "QUEUE_RESET",
        "tv_state": QueueManager.get_public_tv_state(db),
        "stats": QueueManager.get_statistics(db)
    })
    return {"status": "success", "message": "Queue has been reset by Admin"}

@app.post("/api/admin/services/update")
def admin_update_service(
    service_id: int = Form(...),
    avg_service_time: int = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    service.avg_service_time = max(1, avg_service_time)
    db.commit()
    return {"status": "success", "service": service.to_dict()}

@app.post("/api/admin/users/create")
def admin_create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("staff"),
    counter_number: int = Form(1),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    clean_user = username.strip().lower()
    existing = db.query(User).filter(User.username == clean_user).first()
    if existing:
        raise HTTPException(status_code=400, detail="ឈ្មោះគណនីនេះមានរួចហើយ / Username already exists")

    new_user = User(
        username=clean_user,
        password_hash=hash_password(password),
        role=role if role in ["staff", "admin"] else "staff",
        counter_number=counter_number
    )
    db.add(new_user)
    db.commit()
    return {"status": "success", "user": new_user.to_dict()}

@app.get("/api/admin/users")
def admin_list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    users = db.query(User).all()
    return [u.to_dict() for u in users]

@app.get("/api/tv/state")
def get_tv_state(db: Session = Depends(get_db)):
    return QueueManager.get_public_tv_state(db)

@app.get("/api/qr")
def generate_qr_image(url: Optional[str] = None, request: Request = None):
    """Generates PNG QR code for mobile scanning (uses Public URL if tunnel active, else LAN IP)."""
    if not url:
        url = get_portal_url()

    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/sw.js")
def get_service_worker():
    """Serves the Service Worker script from root scope for Mobile Web Notifications & Vibration."""
    sw_file = os.path.join(os.path.dirname(__file__), "static", "sw.js")
    if os.path.exists(sw_file):
        return FileResponse(sw_file, media_type="application/javascript")
    return Response(content="// sw empty", media_type="application/javascript")


@app.get("/api/telegram/status")
def get_telegram_status():
    """Returns Telegram bot connection status & username."""
    return telegram_notifier.get_bot_info()


@app.post("/api/admin/telegram/config")
def set_telegram_config(
    bot_token: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """Admin configures the Telegram Bot Token."""
    clean_token = bot_token.strip()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "telegram_bot_token").first()
    if not setting:
        setting = SystemSetting(key="telegram_bot_token", value=clean_token)
        db.add(setting)
    else:
        setting.value = clean_token
    db.commit()
    telegram_notifier.set_token(clean_token)
    info = telegram_notifier.get_bot_info()
    return {"status": "success", "info": info}


@app.post("/api/admin/telegram/test")
def test_telegram_message(
    chat_id: str = Form(...),
    admin_user: User = Depends(require_admin_user)
):
    """Admin sends a test message to verify Telegram Bot connectivity."""
    clean_chat_id = chat_id.strip()
    success = telegram_notifier.send_message(
        chat_id=clean_chat_id,
        text="👋 <b>LineUp System - សារតេស្តប្រព័ន្ធ</b>\n\n🎉 សូមអបអរសាទរ! Telegram Bot របស់អ្នកត្រូវបានភ្ជាប់ដោយជោគជ័យជាមួយប្រព័ន្ធ LineUp ហើយ។"
    )
    if success:
        return {"status": "success", "message": f"សារតេស្តត្រូវបានផ្ញើទៅ {clean_chat_id} រួចរាល់!"}
    else:
        info = telegram_notifier.get_bot_info()
        return {
            "status": "error",
            "message": "មិនអាចផ្ញើសារបានទេ។ សូមប្រាកដថា Token ត្រឹមត្រូវ ហើយអ្នកបានចុច /start នៅក្នុង Telegram Bot រួចហើយ។",
            "info": info
        }


# ==============================================================================
# Admin SMS Gateway Configuration & Test Endpoints
# ==============================================================================

@app.get("/api/admin/sms/status")
def get_sms_status(admin_user: User = Depends(require_admin_user)):
    """Returns current SMS configuration and provider status."""
    return {
        "enabled": sms_notifier._enabled,
        "provider": sms_notifier._provider,
        "sender_name": sms_notifier._sender_name,
        "twilio_configured": bool(sms_notifier._twilio_sid and sms_notifier._twilio_token),
        "generic_configured": bool(sms_notifier._generic_url)
    }


@app.post("/api/admin/sms/config")
def set_sms_config(
    provider: str = Form("mock"),
    sender_name: str = Form("LineUp"),
    twilio_sid: Optional[str] = Form(None),
    twilio_token: Optional[str] = Form(None),
    twilio_from: Optional[str] = Form(None),
    gateway_url: Optional[str] = Form(None),
    gateway_key: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """Admin updates SMS Gateway configuration."""
    def update_setting(key: str, val: Optional[str]):
        s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not s:
            s = SystemSetting(key=key, value=(val or "").strip())
            db.add(s)
        else:
            s.value = (val or "").strip()

    update_setting("sms_provider", provider)
    update_setting("sms_sender_name", sender_name)
    update_setting("twilio_sid", twilio_sid)
    update_setting("twilio_token", twilio_token)
    update_setting("twilio_from", twilio_from)
    update_setting("sms_gateway_url", gateway_url)
    update_setting("sms_gateway_key", gateway_key)
    db.commit()

    sms_notifier.load_settings()
    return {"status": "success", "message": "SMS configuration updated successfully!"}


@app.post("/api/admin/sms/test")
def test_sms_message(
    phone: str = Form(...),
    admin_user: User = Depends(require_admin_user)
):
    """Admin sends a test SMS to any phone number."""
    res = sms_notifier.send_sms(
        to_phone=phone,
        message="LineUp System: សារតេស្តផ្ញើផ្ទាល់ទៅកាន់លេខទូរស័ព្ទជោគជ័យ! (Direct SMS Gateway Test OK)"
    )
    return res


# ==============================================================================
# WebSocket Endpoint
# ==============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping / pong heartbeats
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

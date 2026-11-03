from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models import QueueTicket, Service, User

class QueueManager:
    """Core Queue Engine handling ticket sequencing, ETA computation, state transitions and analytics."""

    @staticmethod
    def get_or_seed_services(db: Session) -> List[Service]:
        """Ensure default services exist."""
        services = db.query(Service).all()
        if not services:
            default_services = [
                Service(
                    name="ទូទៅ / General Consultation",
                    prefix="A",
                    avg_service_time=5,
                    color_badge="blue",
                    description="ការប្រឹក្សាយោបល់ និងសេវាទូទៅ"
                ),
                Service(
                    name="បង់ប្រាក់ / Cashier & Payment",
                    prefix="B",
                    avg_service_time=3,
                    color_badge="emerald",
                    description="បង់ប្រាក់ និងដកប្រាក់"
                ),
                Service(
                    name="សេវាអតិថិជន / Customer Support",
                    prefix="C",
                    avg_service_time=7,
                    color_badge="purple",
                    description="ដោះស្រាយបញ្ហា និងព័ត៌មានលម្អិត"
                ),
                Service(
                    name="អាទិភាព / VIP & Priority",
                    prefix="V",
                    avg_service_time=4,
                    color_badge="amber",
                    description="អតិថិជនពិសេស និងមនុស្សចាស់"
                ),
            ]
            for s in default_services:
                db.add(s)
            db.commit()
            services = db.query(Service).all()
        return services

    @staticmethod
    def create_ticket(
        db: Session,
        service_id: int,
        customer_name: Optional[str] = "Customer",
        customer_phone: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ) -> QueueTicket:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise ValueError(f"Service with id {service_id} not found")

        # Today's tickets count for this service to generate sequential sequence number
        today_start = datetime.combine(date.today(), datetime.min.time())
        count_today = db.query(QueueTicket).filter(
            QueueTicket.service_id == service_id,
            QueueTicket.created_at >= today_start
        ).count()

        sequence = count_today + 1
        ticket_number = f"{service.prefix}-{sequence:03d}"

        new_ticket = QueueTicket(
            ticket_number=ticket_number,
            service_id=service_id,
            customer_name=customer_name or "Walk-in Guest",
            customer_phone=customer_phone,
            telegram_chat_id=telegram_chat_id,
            status="WAITING",
            created_at=datetime.utcnow()
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        return new_ticket

    @staticmethod
    def calculate_eta_and_ahead(db: Session, ticket: QueueTicket) -> Dict[str, Any]:
        """Calculates how many people are ahead and the estimated wait time (in minutes)."""
        if ticket.status != "WAITING":
            return {
                "ahead_count": 0,
                "estimated_wait_minutes": 0,
                "current_serving_ticket": None
            }

        # People waiting ahead of this ticket (same service or overall waiting)
        ahead_count = db.query(QueueTicket).filter(
            QueueTicket.service_id == ticket.service_id,
            QueueTicket.status == "WAITING",
            QueueTicket.created_at < ticket.created_at
        ).count()

        avg_time = ticket.service.avg_service_time if ticket.service else 5
        estimated_wait_minutes = ahead_count * avg_time

        # Currently calling/serving ticket for this service
        current_ticket = db.query(QueueTicket).filter(
            QueueTicket.service_id == ticket.service_id,
            QueueTicket.status.in_(["CALLING", "SERVING"])
        ).order_by(QueueTicket.called_at.desc()).first()

        return {
            "ahead_count": ahead_count,
            "estimated_wait_minutes": estimated_wait_minutes,
            "current_serving_ticket": current_ticket.ticket_number if current_ticket else None
        }

    @staticmethod
    def call_next(db: Session, counter_id: int = 1, service_id: Optional[int] = None) -> Optional[QueueTicket]:
        """Picks the next WAITING customer and transitions to CALLING."""
        query = db.query(QueueTicket).filter(QueueTicket.status == "WAITING")
        if service_id:
            query = query.filter(QueueTicket.service_id == service_id)
        
        next_ticket = query.order_by(QueueTicket.created_at.asc()).first()
        if not next_ticket:
            return None

        # Also complete or move previous ticket if staff was serving
        prev_ticket = db.query(QueueTicket).filter(
            QueueTicket.counter_id == counter_id,
            QueueTicket.status.in_(["CALLING", "SERVING"])
        ).first()
        if prev_ticket:
            # Auto complete previous ticket if still active on this counter
            prev_ticket.status = "COMPLETED"
            prev_ticket.completed_at = datetime.utcnow()

        next_ticket.status = "CALLING"
        next_ticket.counter_id = counter_id
        next_ticket.called_at = datetime.utcnow()
        next_ticket.call_count = (next_ticket.call_count or 0) + 1

        db.commit()
        db.refresh(next_ticket)
        return next_ticket

    @staticmethod
    def recall_ticket(db: Session, ticket_id: int, counter_id: int = 1) -> Optional[QueueTicket]:
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
        if not ticket:
            return None

        ticket.status = "CALLING"
        ticket.counter_id = counter_id
        ticket.called_at = datetime.utcnow()
        ticket.call_count = (ticket.call_count or 0) + 1
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def start_serving(db: Session, ticket_id: int) -> Optional[QueueTicket]:
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
        if not ticket:
            return None

        ticket.status = "SERVING"
        ticket.served_at = datetime.utcnow()
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def complete_ticket(db: Session, ticket_id: int) -> Optional[QueueTicket]:
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
        if not ticket:
            return None

        ticket.status = "COMPLETED"
        ticket.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def mark_no_show(db: Session, ticket_id: int) -> Optional[QueueTicket]:
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
        if not ticket:
            return None

        ticket.status = "NO_SHOW"
        ticket.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def cancel_ticket(db: Session, ticket_id: int) -> Optional[QueueTicket]:
        ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
        if not ticket:
            return None

        ticket.status = "CANCELLED"
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def auto_check_no_show(db: Session, timeout_seconds: int = 180) -> List[QueueTicket]:
        """Detect tickets in CALLING state that have exceeded timeout without arriving."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        expired_tickets = db.query(QueueTicket).filter(
            QueueTicket.status == "CALLING",
            QueueTicket.called_at < cutoff_time
        ).all()

        updated = []
        for t in expired_tickets:
            t.status = "NO_SHOW"
            t.completed_at = datetime.utcnow()
            updated.append(t)
        if updated:
            db.commit()
        return updated

    @staticmethod
    def get_public_tv_state(db: Session) -> Dict[str, Any]:
        """Provides data needed for the Public TV Display Board."""
        today_start = datetime.combine(date.today(), datetime.min.time())

        # Current active calling or serving tickets for counters 1 to 6
        active_counters = {}
        for counter_num in range(1, 7):
            active_ticket = db.query(QueueTicket).filter(
                QueueTicket.counter_id == counter_num,
                QueueTicket.status.in_(["CALLING", "SERVING"]),
                QueueTicket.created_at >= today_start
            ).order_by(QueueTicket.called_at.desc()).first()

            if active_ticket:
                active_counters[str(counter_num)] = active_ticket.to_dict()
            else:
                active_counters[str(counter_num)] = None

        # Most recently called ticket (hero spotlight)
        last_called = db.query(QueueTicket).filter(
            QueueTicket.status.in_(["CALLING", "SERVING"]),
            QueueTicket.created_at >= today_start
        ).order_by(QueueTicket.called_at.desc()).first()

        # Next waiting tickets
        waiting_list = db.query(QueueTicket).filter(
            QueueTicket.status == "WAITING",
            QueueTicket.created_at >= today_start
        ).order_by(QueueTicket.created_at.asc()).limit(8).all()

        return {
            "active_counters": active_counters,
            "last_called": last_called.to_dict() if last_called else None,
            "waiting_list": [t.to_dict() for t in waiting_list]
        }

    @staticmethod
    def get_statistics(db: Session) -> Dict[str, Any]:
        """Computes daily queue analytics: throughput, averages, no-show rate."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_tickets = db.query(QueueTicket).filter(
            QueueTicket.created_at >= today_start
        ).all()

        total = len(today_tickets)
        waiting = sum(1 for t in today_tickets if t.status == "WAITING")
        calling = sum(1 for t in today_tickets if t.status == "CALLING")
        serving = sum(1 for t in today_tickets if t.status == "SERVING")
        completed = sum(1 for t in today_tickets if t.status == "COMPLETED")
        no_show = sum(1 for t in today_tickets if t.status == "NO_SHOW")
        cancelled = sum(1 for t in today_tickets if t.status == "CANCELLED")

        # Calculate average wait time (created_at to called_at in minutes)
        wait_times = []
        for t in today_tickets:
            if t.called_at and t.created_at:
                diff = (t.called_at - t.created_at).total_seconds() / 60.0
                if diff >= 0:
                    wait_times.append(diff)
        avg_wait = round(sum(wait_times) / len(wait_times), 1) if wait_times else 0.0

        # Calculate average service time (served_at or called_at to completed_at in minutes)
        service_times = []
        for t in today_tickets:
            start_t = t.served_at or t.called_at
            if t.completed_at and start_t:
                diff = (t.completed_at - start_t).total_seconds() / 60.0
                if diff >= 0:
                    service_times.append(diff)
        avg_service = round(sum(service_times) / len(service_times), 1) if service_times else 0.0

        return {
            "total_today": total,
            "waiting": waiting,
            "calling": calling,
            "serving": serving,
            "completed": completed,
            "no_show": no_show,
            "cancelled": cancelled,
            "avg_wait_minutes": avg_wait,
            "avg_service_minutes": avg_service
        }

    @staticmethod
    def reset_queue(db: Session):
        """Clears or resets today's active tickets (useful for demo/testing)."""
        db.query(QueueTicket).delete()
        db.commit()

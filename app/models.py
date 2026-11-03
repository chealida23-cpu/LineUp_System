from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    prefix = Column(String(5), nullable=False, unique=True)
    avg_service_time = Column(Integer, default=5)  # minutes
    color_badge = Column(String(30), default="blue")  # blue, emerald, amber, purple
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    tickets = relationship("QueueTicket", back_populates="service")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "avg_service_time": self.avg_service_time,
            "color_badge": self.color_badge,
            "description": self.description,
            "is_active": self.is_active
        }


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="staff")  # "admin", "staff"
    counter_number = Column(Integer, default=1)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "counter_number": self.counter_number
        }


class QueueTicket(Base):
    __tablename__ = "queue_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(10), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True)
    
    # Statuses: 'WAITING', 'CALLING', 'SERVING', 'COMPLETED', 'NO_SHOW', 'CANCELLED'
    status = Column(String(20), default="WAITING", index=True)
    counter_id = Column(Integer, nullable=True)
    call_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    called_at = Column(DateTime, nullable=True)
    served_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    service = relationship("Service", back_populates="tickets")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "service_id": self.service_id,
            "service_name": self.service.name if self.service else "General",
            "service_prefix": self.service.prefix if self.service else "A",
            "avg_service_time": self.service.avg_service_time if self.service else 5,
            "color_badge": self.service.color_badge if self.service else "blue",
            "customer_name": self.customer_name or "Walk-in Guest",
            "customer_phone": self.customer_phone or "",
            "telegram_chat_id": self.telegram_chat_id or "",
            "status": self.status,
            "counter_id": self.counter_id,
            "call_count": self.call_count,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "called_at": self.called_at.strftime("%Y-%m-%d %H:%M:%S") if self.called_at else None,
            "served_at": self.served_at.strftime("%Y-%m-%d %H:%M:%S") if self.served_at else None,
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else None,
            "created_time": self.created_at.strftime("%H:%M") if self.created_at else "",
            "called_time": self.called_at.strftime("%H:%M") if self.called_at else "",
            "notes": self.notes or ""
        }


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value
        }


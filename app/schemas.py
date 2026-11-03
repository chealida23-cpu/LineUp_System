from typing import Optional, List
from pydantic import BaseModel, Field

class ServiceBase(BaseModel):
    name: str
    prefix: str
    avg_service_time: int = 5
    color_badge: str = "blue"
    description: Optional[str] = None

class ServiceCreate(ServiceBase):
    pass

class ServiceResponse(ServiceBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    service_id: int
    customer_name: Optional[str] = "Customer"
    customer_phone: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class TicketAction(BaseModel):
    ticket_id: int
    counter_id: Optional[int] = 1


class CallNextRequest(BaseModel):
    counter_id: int = 1
    service_id: Optional[int] = None  # None means any service


class TicketStatusResponse(BaseModel):
    id: int
    ticket_number: str
    service_id: int
    service_name: str
    service_prefix: str
    customer_name: str
    customer_phone: Optional[str] = None
    status: str
    counter_id: Optional[int] = None
    ahead_count: int = 0
    estimated_wait_minutes: int = 0
    current_serving_ticket: Optional[str] = None
    created_at: Optional[str] = None
    called_at: Optional[str] = None
    served_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class QueueStats(BaseModel):
    total_today: int
    waiting: int
    calling: int
    serving: int
    completed: int
    no_show: int
    cancelled: int
    avg_wait_minutes: float
    avg_service_minutes: float

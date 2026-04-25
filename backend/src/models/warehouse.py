"""
Warehouse model for multi-warehouse inventory tracking.
"""
import enum
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class WarehouseStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="US")
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity: Mapped[int] = mapped_column(nullable=False, default=10000)
    status: Mapped[WarehouseStatus] = mapped_column(
        Enum(WarehouseStatus), nullable=False, default=WarehouseStatus.ACTIVE
    )
    manager_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    manager_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    inventory_items: Mapped[List["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="warehouse", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, name={self.name}, code={self.code})>"

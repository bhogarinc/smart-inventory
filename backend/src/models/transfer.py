"""
Transfer models for multi-warehouse stock transfers.
"""
import enum
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class TransferStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    transfer_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    source_warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    destination_warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus), nullable=False, default=TransferStatus.DRAFT
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    shipped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    source_warehouse = relationship(
        "Warehouse", foreign_keys=[source_warehouse_id], lazy="selectin"
    )
    destination_warehouse = relationship(
        "Warehouse", foreign_keys=[destination_warehouse_id], lazy="selectin"
    )
    items: Mapped[List["TransferItem"]] = relationship(
        "TransferItem", back_populates="transfer", lazy="selectin", cascade="all, delete-orphan"
    )
    requester = relationship(
        "User", foreign_keys=[requested_by], lazy="selectin"
    )
    approver = relationship(
        "User", foreign_keys=[approved_by], lazy="selectin"
    )

    @property
    def total_items(self) -> int:
        return len(self.items) if self.items else 0

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items) if self.items else 0

    def __repr__(self) -> str:
        return f"<Transfer(id={self.id}, number={self.transfer_number}, status={self.status})>"


class TransferItem(Base):
    __tablename__ = "transfer_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    transfer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    transfer: Mapped["Transfer"] = relationship(
        "Transfer", back_populates="items", lazy="selectin"
    )
    product = relationship("Product", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TransferItem(transfer_id={self.transfer_id}, product_id={self.product_id}, qty={self.quantity})>"

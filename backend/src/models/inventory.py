"""
Inventory models for tracking stock levels and movements.
"""
import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class MovementType(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGED = "damaged"
    EXPIRED = "expired"


class InventoryItem(Base):
    """Tracks current stock level of a product in a specific warehouse."""
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_product_warehouse"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_incoming: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bin_location: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_counted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    product = relationship("Product", back_populates="inventory_items", lazy="selectin")
    warehouse = relationship("Warehouse", back_populates="inventory_items", lazy="selectin")

    @property
    def quantity_available(self) -> int:
        """Available quantity = on_hand - reserved."""
        return self.quantity_on_hand - self.quantity_reserved

    def __repr__(self) -> str:
        return (
            f"<InventoryItem(product_id={self.product_id}, "
            f"warehouse_id={self.warehouse_id}, qty={self.quantity_on_hand})>"
        )


class InventoryMovement(Base):
    """Tracks all inventory movements for audit trail."""
    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    inventory_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    inventory_item = relationship("InventoryItem", lazy="selectin")
    user = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement(id={self.id}, type={self.movement_type}, "
            f"qty={self.quantity})>"
        )

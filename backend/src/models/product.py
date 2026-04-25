"""
Product and ProductCategory models with SKU and barcode support.
"""
import enum
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category", lazy="selectin"
    )
    children: Mapped[List["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="parent", lazy="selectin"
    )
    parent: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="children", remote_side=[id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ProductCategory(id={self.id}, name={self.name})>"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    sku: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_unit: Mapped[str] = mapped_column(String(10), default="kg", nullable=False)
    dimensions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    min_stock_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_stock_level: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), nullable=False, default=ProductStatus.ACTIVE
    )
    is_serialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    category: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="products", lazy="selectin"
    )
    inventory_items: Mapped[List["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="product", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name})>"

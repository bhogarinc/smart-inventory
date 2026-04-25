"""
Inventory schemas for stock management operations.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.inventory import MovementType


class InventoryItemBase(BaseModel):
    product_id: str
    warehouse_id: str
    quantity_on_hand: int = Field(default=0, ge=0)
    bin_location: Optional[str] = Field(None, max_length=50)
    lot_number: Optional[str] = Field(None, max_length=100)
    unit_cost: float = Field(default=0.0, ge=0)


class InventoryItemCreate(InventoryItemBase):
    expiry_date: Optional[datetime] = None


class InventoryItemUpdate(BaseModel):
    quantity_on_hand: Optional[int] = Field(None, ge=0)
    quantity_reserved: Optional[int] = Field(None, ge=0)
    quantity_incoming: Optional[int] = Field(None, ge=0)
    bin_location: Optional[str] = Field(None, max_length=50)
    lot_number: Optional[str] = Field(None, max_length=100)
    unit_cost: Optional[float] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None


class InventoryItemResponse(InventoryItemBase):
    id: str
    quantity_reserved: int
    quantity_incoming: int
    quantity_available: int
    expiry_date: Optional[datetime] = None
    last_counted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    warehouse_name: Optional[str] = None

    model_config = {"from_attributes": True}


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StockAdjustmentRequest(BaseModel):
    inventory_item_id: str
    adjustment_quantity: int
    movement_type: MovementType
    notes: Optional[str] = None


class StockReceiveRequest(BaseModel):
    product_id: str
    warehouse_id: str
    quantity: int = Field(..., gt=0)
    unit_cost: Optional[float] = Field(None, ge=0)
    lot_number: Optional[str] = None
    bin_location: Optional[str] = None
    notes: Optional[str] = None


class InventoryMovementResponse(BaseModel):
    id: str
    inventory_item_id: str
    movement_type: MovementType
    quantity: int
    quantity_before: int
    quantity_after: int
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    performed_by: Optional[str] = None
    performer_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryMovementListResponse(BaseModel):
    items: list[InventoryMovementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StockLevelSummary(BaseModel):
    product_id: str
    product_name: str
    sku: str
    total_on_hand: int
    total_reserved: int
    total_available: int
    total_incoming: int
    warehouse_breakdown: list[dict]
    status: str  # in_stock, low_stock, out_of_stock

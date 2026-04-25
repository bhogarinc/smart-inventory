"""
Transfer schemas for multi-warehouse transfer management.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.transfer import TransferStatus


class TransferItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None


class TransferItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity: int
    quantity_received: int
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class TransferCreate(BaseModel):
    source_warehouse_id: str
    destination_warehouse_id: str
    items: list[TransferItemCreate] = Field(..., min_length=1)
    notes: Optional[str] = None


class TransferUpdate(BaseModel):
    status: Optional[TransferStatus] = None
    notes: Optional[str] = None


class TransferReceiveItem(BaseModel):
    transfer_item_id: str
    quantity_received: int = Field(..., ge=0)


class TransferReceiveRequest(BaseModel):
    items: list[TransferReceiveItem] = Field(..., min_length=1)


class TransferResponse(BaseModel):
    id: str
    transfer_number: str
    source_warehouse_id: str
    source_warehouse_name: Optional[str] = None
    destination_warehouse_id: str
    destination_warehouse_name: Optional[str] = None
    status: TransferStatus
    notes: Optional[str] = None
    requested_by: Optional[str] = None
    requester_name: Optional[str] = None
    approved_by: Optional[str] = None
    approver_name: Optional[str] = None
    items: list[TransferItemResponse] = []
    total_items: int
    total_quantity: int
    shipped_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransferListResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    page: int
    page_size: int
    pages: int

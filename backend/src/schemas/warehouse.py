"""
Warehouse schemas for CRUD operations.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.warehouse import WarehouseStatus


class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=20)
    address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    country: str = Field(default="US", max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=20)
    capacity: int = Field(default=10000, ge=1)
    manager_name: Optional[str] = Field(None, max_length=200)
    manager_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class WarehouseCreate(WarehouseBase):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_primary: bool = False


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    zip_code: Optional[str] = Field(None, max_length=20)
    capacity: Optional[int] = Field(None, ge=1)
    status: Optional[WarehouseStatus] = None
    manager_name: Optional[str] = Field(None, max_length=200)
    manager_email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class WarehouseResponse(WarehouseBase):
    id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: WarehouseStatus
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WarehouseListResponse(BaseModel):
    items: list[WarehouseResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WarehouseStockSummary(BaseModel):
    warehouse_id: str
    warehouse_name: str
    total_products: int
    total_quantity: int
    low_stock_count: int
    out_of_stock_count: int
    capacity_used_percent: float

"""
Product schemas for CRUD operations.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.product import ProductStatus


class ProductCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[str] = None


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryResponse(ProductCategoryBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    category_id: Optional[str] = None
    unit_price: float = Field(default=0.0, ge=0)
    cost_price: float = Field(default=0.0, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    weight_unit: str = Field(default="kg", max_length=10)
    dimensions: Optional[str] = Field(None, max_length=100)
    min_stock_level: int = Field(default=10, ge=0)
    max_stock_level: int = Field(default=1000, ge=1)
    reorder_point: int = Field(default=25, ge=0)
    reorder_quantity: int = Field(default=100, ge=1)
    lead_time_days: int = Field(default=7, ge=0)
    supplier_name: Optional[str] = Field(None, max_length=200)
    supplier_sku: Optional[str] = Field(None, max_length=100)


class ProductCreate(ProductBase):
    barcode: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=500)
    is_serialized: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    category_id: Optional[str] = None
    unit_price: Optional[float] = Field(None, ge=0)
    cost_price: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    weight_unit: Optional[str] = Field(None, max_length=10)
    dimensions: Optional[str] = Field(None, max_length=100)
    min_stock_level: Optional[int] = Field(None, ge=0)
    max_stock_level: Optional[int] = Field(None, ge=1)
    reorder_point: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=1)
    lead_time_days: Optional[int] = Field(None, ge=0)
    supplier_name: Optional[str] = Field(None, max_length=200)
    supplier_sku: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=500)
    status: Optional[ProductStatus] = None
    barcode: Optional[str] = Field(None, max_length=100)


class ProductResponse(ProductBase):
    id: str
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    status: ProductStatus
    is_serialized: bool
    created_at: datetime
    updated_at: datetime
    category: Optional[ProductCategoryResponse] = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BarcodeGenerateRequest(BaseModel):
    product_id: str
    barcode_type: str = Field(default="code128", pattern="^(code128|ean13|upc)$")


class BarcodeResponse(BaseModel):
    product_id: str
    sku: str
    barcode: str
    barcode_image_base64: str

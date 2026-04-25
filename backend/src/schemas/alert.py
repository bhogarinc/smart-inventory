"""
Alert schemas for inventory alert management.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.alert import AlertSeverity, AlertStatus, AlertType


class AlertResponse(BaseModel):
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    warehouse_id: Optional[str] = None
    warehouse_name: Optional[str] = None
    current_quantity: Optional[int] = None
    threshold_quantity: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AlertAcknowledgeRequest(BaseModel):
    alert_ids: list[str] = Field(..., min_length=1)


class AlertDismissRequest(BaseModel):
    alert_ids: list[str] = Field(..., min_length=1)


class ReorderRuleCreate(BaseModel):
    product_id: str
    warehouse_id: Optional[str] = None
    reorder_point: int = Field(..., ge=0)
    reorder_quantity: int = Field(..., ge=1)
    max_stock_level: int = Field(default=1000, ge=1)
    auto_reorder: bool = False


class ReorderRuleUpdate(BaseModel):
    reorder_point: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=1)
    max_stock_level: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    auto_reorder: Optional[bool] = None


class ReorderRuleResponse(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    warehouse_name: Optional[str] = None
    reorder_point: int
    reorder_quantity: int
    max_stock_level: int
    is_active: bool
    auto_reorder: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReorderRuleListResponse(BaseModel):
    items: list[ReorderRuleResponse]
    total: int
    page: int
    page_size: int
    pages: int

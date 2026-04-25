"""
Report schemas for inventory reporting and forecasting.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DailyStockReportItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
    warehouse_id: str
    warehouse_name: str
    opening_stock: int
    received: int
    shipped: int
    adjusted: int
    closing_stock: int
    stock_value: float


class DailyStockReport(BaseModel):
    report_date: date
    generated_at: datetime
    items: list[DailyStockReportItem]
    summary: dict


class MovementHistoryRequest(BaseModel):
    start_date: date
    end_date: date
    product_id: Optional[str] = None
    warehouse_id: Optional[str] = None
    movement_type: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class ForecastRequest(BaseModel):
    product_id: str
    warehouse_id: Optional[str] = None
    forecast_days: int = Field(default=30, ge=7, le=365)


class ForecastPoint(BaseModel):
    date: date
    predicted_quantity: int
    lower_bound: int
    upper_bound: int


class ForecastResponse(BaseModel):
    product_id: str
    product_name: str
    sku: str
    current_stock: int
    forecast_days: int
    predicted_stockout_date: Optional[date] = None
    recommended_reorder_date: Optional[date] = None
    recommended_reorder_quantity: int
    forecast_data: list[ForecastPoint]
    confidence_score: float


class InventoryValuationReport(BaseModel):
    report_date: date
    total_value: float
    total_units: int
    warehouse_breakdown: list[dict]
    category_breakdown: list[dict]
    top_value_products: list[dict]

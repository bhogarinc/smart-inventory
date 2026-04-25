"""
Dashboard schemas for aggregated data views.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_products: int
    total_warehouses: int
    total_stock_value: float
    total_units_in_stock: int
    low_stock_alerts: int
    out_of_stock_count: int
    pending_transfers: int
    active_alerts: int


class StockTrendPoint(BaseModel):
    date: str
    quantity: int
    value: float


class WarehouseUtilization(BaseModel):
    warehouse_id: str
    warehouse_name: str
    total_capacity: int
    current_stock: int
    utilization_percent: float


class TopProduct(BaseModel):
    product_id: str
    product_name: str
    sku: str
    total_movements: int
    total_quantity_moved: int


class RecentMovement(BaseModel):
    id: str
    product_name: str
    warehouse_name: str
    movement_type: str
    quantity: int
    performed_by_name: Optional[str] = None
    created_at: datetime


class DashboardResponse(BaseModel):
    stats: DashboardStats
    stock_trends: list[StockTrendPoint]
    warehouse_utilization: list[WarehouseUtilization]
    top_moving_products: list[TopProduct]
    recent_movements: list[RecentMovement]
    recent_alerts: list[dict]

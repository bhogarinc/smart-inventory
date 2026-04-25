"""
Report routes for daily stock reports, movement history, and forecasting.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.schemas.report import (
    DailyStockReport,
    ForecastRequest,
    ForecastResponse,
    InventoryValuationReport,
)
from src.services.auth_service import get_current_user
from src.services.report_service import ReportService

router = APIRouter()


@router.get("/daily-stock", response_model=DailyStockReport)
async def get_daily_stock_report(
    report_date: Optional[date] = None,
    warehouse_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate daily stock report."""
    if not report_date:
        report_date = date.today()

    service = ReportService(db)
    return await service.generate_daily_stock_report(report_date, warehouse_id)


@router.post("/forecast", response_model=ForecastResponse)
async def get_demand_forecast(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate demand forecast for a product."""
    service = ReportService(db)
    try:
        return await service.generate_forecast(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            forecast_days=request.forecast_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/valuation", response_model=InventoryValuationReport)
async def get_valuation_report(
    report_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate inventory valuation report."""
    service = ReportService(db)
    return await service.generate_valuation_report(report_date)

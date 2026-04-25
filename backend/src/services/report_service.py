"""
Report service for generating inventory reports and demand forecasting.
"""
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.inventory import InventoryItem, InventoryMovement, MovementType
from src.models.product import Product, ProductCategory
from src.models.warehouse import Warehouse
from src.schemas.report import (
    DailyStockReport,
    DailyStockReportItem,
    ForecastPoint,
    ForecastResponse,
    InventoryValuationReport,
)

logger = structlog.get_logger()


class ReportService:
    """Service for generating inventory reports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_daily_stock_report(
        self, report_date: date, warehouse_id: Optional[str] = None
    ) -> DailyStockReport:
        """Generate a daily stock report showing opening/closing stock and movements."""
        start_of_day = datetime.combine(report_date, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        end_of_day = datetime.combine(report_date, datetime.max.time()).replace(
            tzinfo=timezone.utc
        )

        query = (
            select(InventoryItem)
            .join(Product)
            .join(Warehouse)
        )
        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)

        result = await self.db.execute(query)
        items = result.scalars().all()

        report_items = []
        total_value = 0.0
        total_units = 0

        for item in items:
            # Get movements for the day
            movements_result = await self.db.execute(
                select(InventoryMovement).where(
                    and_(
                        InventoryMovement.inventory_item_id == item.id,
                        InventoryMovement.created_at >= start_of_day,
                        InventoryMovement.created_at <= end_of_day,
                    )
                )
            )
            movements = movements_result.scalars().all()

            received = sum(
                m.quantity
                for m in movements
                if m.movement_type in [MovementType.INBOUND, MovementType.TRANSFER_IN, MovementType.RETURN]
            )
            shipped = abs(sum(
                m.quantity
                for m in movements
                if m.movement_type in [MovementType.OUTBOUND, MovementType.TRANSFER_OUT]
            ))
            adjusted = sum(
                m.quantity
                for m in movements
                if m.movement_type in [MovementType.ADJUSTMENT, MovementType.DAMAGED, MovementType.EXPIRED]
            )

            closing_stock = item.quantity_on_hand
            opening_stock = closing_stock - received + shipped - adjusted
            stock_value = closing_stock * item.unit_cost

            report_items.append(
                DailyStockReportItem(
                    product_id=item.product_id,
                    product_name=item.product.name if item.product else "Unknown",
                    sku=item.product.sku if item.product else "N/A",
                    warehouse_id=item.warehouse_id,
                    warehouse_name=item.warehouse.name if item.warehouse else "Unknown",
                    opening_stock=max(0, opening_stock),
                    received=received,
                    shipped=shipped,
                    adjusted=adjusted,
                    closing_stock=closing_stock,
                    stock_value=round(stock_value, 2),
                )
            )
            total_value += stock_value
            total_units += closing_stock

        return DailyStockReport(
            report_date=report_date,
            generated_at=datetime.now(timezone.utc),
            items=report_items,
            summary={
                "total_items": len(report_items),
                "total_units": total_units,
                "total_value": round(total_value, 2),
            },
        )

    async def generate_forecast(
        self,
        product_id: str,
        warehouse_id: Optional[str] = None,
        forecast_days: int = 30,
    ) -> ForecastResponse:
        """Generate demand forecast using simple moving average with trend analysis."""
        product_result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Get historical outbound movements (last 90 days)
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
        
        query = (
            select(InventoryMovement)
            .join(InventoryItem)
            .where(
                and_(
                    InventoryItem.product_id == product_id,
                    InventoryMovement.movement_type == MovementType.OUTBOUND,
                    InventoryMovement.created_at >= ninety_days_ago,
                )
            )
        )
        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)

        result = await self.db.execute(query)
        movements = result.scalars().all()

        # Aggregate daily demand
        daily_demand = {}
        for m in movements:
            day = m.created_at.date()
            daily_demand[day] = daily_demand.get(day, 0) + abs(m.quantity)

        # Fill in zero-demand days
        all_days = []
        demand_values = []
        current = ninety_days_ago.date()
        today = date.today()
        while current <= today:
            all_days.append(current)
            demand_values.append(daily_demand.get(current, 0))
            current += timedelta(days=1)

        if not demand_values or sum(demand_values) == 0:
            # No historical data - return flat forecast
            forecast_data = [
                ForecastPoint(
                    date=today + timedelta(days=i),
                    predicted_quantity=0,
                    lower_bound=0,
                    upper_bound=0,
                )
                for i in range(1, forecast_days + 1)
            ]
            return ForecastResponse(
                product_id=product_id,
                product_name=product.name,
                sku=product.sku,
                current_stock=0,
                forecast_days=forecast_days,
                predicted_stockout_date=None,
                recommended_reorder_date=None,
                recommended_reorder_quantity=product.reorder_quantity,
                forecast_data=forecast_data,
                confidence_score=0.0,
            )

        demand_array = np.array(demand_values, dtype=float)
        
        # Simple moving average (7-day window)
        window = min(7, len(demand_array))
        weights = np.ones(window) / window
        sma = np.convolve(demand_array, weights, mode='valid')
        
        avg_daily_demand = float(np.mean(sma[-14:])) if len(sma) >= 14 else float(np.mean(sma))
        std_daily_demand = float(np.std(sma[-14:])) if len(sma) >= 14 else float(np.std(sma))

        # Get current stock
        stock_query = select(func.sum(InventoryItem.quantity_on_hand)).where(
            InventoryItem.product_id == product_id
        )
        if warehouse_id:
            stock_query = stock_query.where(InventoryItem.warehouse_id == warehouse_id)
        stock_result = await self.db.execute(stock_query)
        current_stock = stock_result.scalar() or 0

        # Generate forecast points
        forecast_data = []
        cumulative_demand = 0
        stockout_date = None
        reorder_date = None

        for i in range(1, forecast_days + 1):
            forecast_date = today + timedelta(days=i)
            predicted = max(0, round(avg_daily_demand))
            lower = max(0, round(avg_daily_demand - 1.96 * std_daily_demand))
            upper = max(0, round(avg_daily_demand + 1.96 * std_daily_demand))
            cumulative_demand += predicted

            remaining = current_stock - cumulative_demand

            if remaining <= 0 and stockout_date is None:
                stockout_date = forecast_date
            if remaining <= product.reorder_point and reorder_date is None:
                reorder_date = forecast_date

            forecast_data.append(
                ForecastPoint(
                    date=forecast_date,
                    predicted_quantity=max(0, current_stock - round(cumulative_demand)),
                    lower_bound=max(0, current_stock - round(cumulative_demand + 1.96 * std_daily_demand * i)),
                    upper_bound=max(0, current_stock - round(cumulative_demand - 1.96 * std_daily_demand * i)),
                )
            )

        # Calculate confidence score based on data consistency
        cv = std_daily_demand / avg_daily_demand if avg_daily_demand > 0 else 1.0
        confidence = max(0.0, min(1.0, 1.0 - cv))

        # Recommended reorder quantity
        recommended_qty = max(
            product.reorder_quantity,
            round(avg_daily_demand * product.lead_time_days * 1.5),
        )

        return ForecastResponse(
            product_id=product_id,
            product_name=product.name,
            sku=product.sku,
            current_stock=current_stock,
            forecast_days=forecast_days,
            predicted_stockout_date=stockout_date,
            recommended_reorder_date=reorder_date,
            recommended_reorder_quantity=recommended_qty,
            forecast_data=forecast_data,
            confidence_score=round(confidence, 2),
        )

    async def generate_valuation_report(
        self, report_date: Optional[date] = None
    ) -> InventoryValuationReport:
        """Generate inventory valuation report."""
        if not report_date:
            report_date = date.today()

        # Warehouse breakdown
        wh_result = await self.db.execute(
            select(
                Warehouse.id,
                Warehouse.name,
                func.sum(InventoryItem.quantity_on_hand).label("total_units"),
                func.sum(
                    InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                ).label("total_value"),
            )
            .join(InventoryItem, InventoryItem.warehouse_id == Warehouse.id)
            .group_by(Warehouse.id, Warehouse.name)
        )
        warehouse_breakdown = [
            {
                "warehouse_id": row.id,
                "warehouse_name": row.name,
                "total_units": row.total_units or 0,
                "total_value": round(float(row.total_value or 0), 2),
            }
            for row in wh_result.all()
        ]

        # Category breakdown
        cat_result = await self.db.execute(
            select(
                ProductCategory.id,
                ProductCategory.name,
                func.sum(InventoryItem.quantity_on_hand).label("total_units"),
                func.sum(
                    InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                ).label("total_value"),
            )
            .join(Product, Product.category_id == ProductCategory.id)
            .join(InventoryItem, InventoryItem.product_id == Product.id)
            .group_by(ProductCategory.id, ProductCategory.name)
        )
        category_breakdown = [
            {
                "category_id": row.id,
                "category_name": row.name,
                "total_units": row.total_units or 0,
                "total_value": round(float(row.total_value or 0), 2),
            }
            for row in cat_result.all()
        ]

        # Top value products
        top_result = await self.db.execute(
            select(
                Product.id,
                Product.name,
                Product.sku,
                func.sum(InventoryItem.quantity_on_hand).label("total_units"),
                func.sum(
                    InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                ).label("total_value"),
            )
            .join(InventoryItem, InventoryItem.product_id == Product.id)
            .group_by(Product.id, Product.name, Product.sku)
            .order_by(
                func.sum(
                    InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                ).desc()
            )
            .limit(20)
        )
        top_value_products = [
            {
                "product_id": row.id,
                "product_name": row.name,
                "sku": row.sku,
                "total_units": row.total_units or 0,
                "total_value": round(float(row.total_value or 0), 2),
            }
            for row in top_result.all()
        ]

        total_value = sum(w["total_value"] for w in warehouse_breakdown)
        total_units = sum(w["total_units"] for w in warehouse_breakdown)

        return InventoryValuationReport(
            report_date=report_date,
            total_value=round(total_value, 2),
            total_units=total_units,
            warehouse_breakdown=warehouse_breakdown,
            category_breakdown=category_breakdown,
            top_value_products=top_value_products,
        )

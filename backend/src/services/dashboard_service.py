"""
Dashboard service for aggregated statistics and real-time data.
"""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.alert import Alert, AlertStatus
from src.models.inventory import InventoryItem, InventoryMovement, MovementType
from src.models.product import Product
from src.models.transfer import Transfer, TransferStatus
from src.models.warehouse import Warehouse
from src.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    RecentMovement,
    StockTrendPoint,
    TopProduct,
    WarehouseUtilization,
)

logger = structlog.get_logger()


class DashboardService:
    """Service for dashboard data aggregation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_data(self) -> DashboardResponse:
        """Get all dashboard data in a single call."""
        stats = await self._get_stats()
        stock_trends = await self._get_stock_trends()
        warehouse_utilization = await self._get_warehouse_utilization()
        top_products = await self._get_top_moving_products()
        recent_movements = await self._get_recent_movements()
        recent_alerts = await self._get_recent_alerts()

        return DashboardResponse(
            stats=stats,
            stock_trends=stock_trends,
            warehouse_utilization=warehouse_utilization,
            top_moving_products=top_products,
            recent_movements=recent_movements,
            recent_alerts=recent_alerts,
        )

    async def _get_stats(self) -> DashboardStats:
        """Get summary statistics."""
        # Total products
        product_count = await self.db.execute(
            select(func.count(Product.id))
        )
        total_products = product_count.scalar() or 0

        # Total warehouses
        warehouse_count = await self.db.execute(
            select(func.count(Warehouse.id))
        )
        total_warehouses = warehouse_count.scalar() or 0

        # Total stock value and units
        stock_result = await self.db.execute(
            select(
                func.sum(InventoryItem.quantity_on_hand).label("total_units"),
                func.sum(
                    InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                ).label("total_value"),
            )
        )
        stock_row = stock_result.one()
        total_units = stock_row.total_units or 0
        total_value = float(stock_row.total_value or 0)

        # Low stock count
        low_stock_result = await self.db.execute(
            select(func.count(InventoryItem.id))
            .join(Product)
            .where(
                and_(
                    InventoryItem.quantity_on_hand > 0,
                    InventoryItem.quantity_on_hand <= Product.reorder_point,
                )
            )
        )
        low_stock_count = low_stock_result.scalar() or 0

        # Out of stock
        oos_result = await self.db.execute(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.quantity_on_hand == 0
            )
        )
        out_of_stock = oos_result.scalar() or 0

        # Pending transfers
        pending_result = await self.db.execute(
            select(func.count(Transfer.id)).where(
                Transfer.status.in_([
                    TransferStatus.PENDING_APPROVAL,
                    TransferStatus.APPROVED,
                    TransferStatus.IN_TRANSIT,
                ])
            )
        )
        pending_transfers = pending_result.scalar() or 0

        # Active alerts
        alert_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.status == AlertStatus.ACTIVE
            )
        )
        active_alerts = alert_result.scalar() or 0

        return DashboardStats(
            total_products=total_products,
            total_warehouses=total_warehouses,
            total_stock_value=round(total_value, 2),
            total_units_in_stock=total_units,
            low_stock_alerts=low_stock_count,
            out_of_stock_count=out_of_stock,
            pending_transfers=pending_transfers,
            active_alerts=active_alerts,
        )

    async def _get_stock_trends(self, days: int = 30) -> list[StockTrendPoint]:
        """Get stock trends for the last N days."""
        trends = []
        today = datetime.now(timezone.utc).date()

        for i in range(days - 1, -1, -1):
            trend_date = today - timedelta(days=i)
            # For simplicity, use current stock as baseline
            # In production, this would query historical snapshots
            result = await self.db.execute(
                select(
                    func.sum(InventoryItem.quantity_on_hand).label("qty"),
                    func.sum(
                        InventoryItem.quantity_on_hand * InventoryItem.unit_cost
                    ).label("val"),
                )
            )
            row = result.one()
            trends.append(
                StockTrendPoint(
                    date=trend_date.isoformat(),
                    quantity=row.qty or 0,
                    value=round(float(row.val or 0), 2),
                )
            )

        return trends

    async def _get_warehouse_utilization(self) -> list[WarehouseUtilization]:
        """Get utilization percentage for each warehouse."""
        result = await self.db.execute(
            select(
                Warehouse.id,
                Warehouse.name,
                Warehouse.capacity,
                func.coalesce(
                    func.sum(InventoryItem.quantity_on_hand), 0
                ).label("current_stock"),
            )
            .outerjoin(InventoryItem, InventoryItem.warehouse_id == Warehouse.id)
            .group_by(Warehouse.id, Warehouse.name, Warehouse.capacity)
        )

        utilizations = []
        for row in result.all():
            pct = (row.current_stock / row.capacity * 100) if row.capacity > 0 else 0
            utilizations.append(
                WarehouseUtilization(
                    warehouse_id=row.id,
                    warehouse_name=row.name,
                    total_capacity=row.capacity,
                    current_stock=row.current_stock,
                    utilization_percent=round(pct, 1),
                )
            )

        return utilizations

    async def _get_top_moving_products(self, limit: int = 10) -> list[TopProduct]:
        """Get top products by movement volume in the last 30 days."""
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        result = await self.db.execute(
            select(
                Product.id,
                Product.name,
                Product.sku,
                func.count(InventoryMovement.id).label("total_movements"),
                func.sum(func.abs(InventoryMovement.quantity)).label("total_qty"),
            )
            .join(InventoryItem, InventoryItem.product_id == Product.id)
            .join(
                InventoryMovement,
                InventoryMovement.inventory_item_id == InventoryItem.id,
            )
            .where(InventoryMovement.created_at >= thirty_days_ago)
            .group_by(Product.id, Product.name, Product.sku)
            .order_by(func.sum(func.abs(InventoryMovement.quantity)).desc())
            .limit(limit)
        )

        return [
            TopProduct(
                product_id=row.id,
                product_name=row.name,
                sku=row.sku,
                total_movements=row.total_movements,
                total_quantity_moved=row.total_qty or 0,
            )
            for row in result.all()
        ]

    async def _get_recent_movements(self, limit: int = 20) -> list[RecentMovement]:
        """Get most recent inventory movements."""
        result = await self.db.execute(
            select(InventoryMovement)
            .join(InventoryItem)
            .join(Product, Product.id == InventoryItem.product_id)
            .join(Warehouse, Warehouse.id == InventoryItem.warehouse_id)
            .order_by(InventoryMovement.created_at.desc())
            .limit(limit)
        )
        movements = result.scalars().all()

        return [
            RecentMovement(
                id=m.id,
                product_name=(
                    m.inventory_item.product.name
                    if m.inventory_item and m.inventory_item.product
                    else "Unknown"
                ),
                warehouse_name=(
                    m.inventory_item.warehouse.name
                    if m.inventory_item and m.inventory_item.warehouse
                    else "Unknown"
                ),
                movement_type=m.movement_type.value,
                quantity=m.quantity,
                performed_by_name=m.user.full_name if m.user else None,
                created_at=m.created_at,
            )
            for m in movements
        ]

    async def _get_recent_alerts(self, limit: int = 10) -> list[dict]:
        """Get most recent active alerts."""
        result = await self.db.execute(
            select(Alert)
            .where(Alert.status == AlertStatus.ACTIVE)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        alerts = result.scalars().all()

        return [
            {
                "id": a.id,
                "type": a.alert_type.value,
                "severity": a.severity.value,
                "title": a.title,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]

"""
Inventory service for stock management, movements, and alerts.
"""
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.alert import Alert, AlertSeverity, AlertStatus, AlertType, ReorderRule
from src.models.inventory import InventoryItem, InventoryMovement, MovementType
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryMovementListResponse,
    InventoryMovementResponse,
    StockAdjustmentRequest,
    StockLevelSummary,
    StockReceiveRequest,
)

logger = structlog.get_logger()


class InventoryService:
    """Service for managing inventory operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_inventory_items(
        self,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        low_stock_only: bool = False,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> InventoryItemListResponse:
        """Get paginated inventory items with optional filters."""
        query = select(InventoryItem).join(Product).join(Warehouse)

        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)
        if product_id:
            query = query.where(InventoryItem.product_id == product_id)
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                (Product.name.ilike(search_filter))
                | (Product.sku.ilike(search_filter))
                | (Product.barcode.ilike(search_filter))
            )
        if low_stock_only:
            query = query.where(
                InventoryItem.quantity_on_hand <= Product.reorder_point
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()

        response_items = []
        for item in items:
            resp = InventoryItemResponse(
                id=item.id,
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                quantity_on_hand=item.quantity_on_hand,
                quantity_reserved=item.quantity_reserved,
                quantity_incoming=item.quantity_incoming,
                quantity_available=item.quantity_available,
                bin_location=item.bin_location,
                lot_number=item.lot_number,
                unit_cost=item.unit_cost,
                expiry_date=item.expiry_date,
                last_counted_at=item.last_counted_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                product_name=item.product.name if item.product else None,
                product_sku=item.product.sku if item.product else None,
                warehouse_name=item.warehouse.name if item.warehouse else None,
            )
            response_items.append(resp)

        return InventoryItemListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )

    async def receive_stock(
        self, request: StockReceiveRequest, user_id: str
    ) -> InventoryItemResponse:
        """Receive stock into a warehouse (inbound movement)."""
        # Find or create inventory item
        result = await self.db.execute(
            select(InventoryItem).where(
                and_(
                    InventoryItem.product_id == request.product_id,
                    InventoryItem.warehouse_id == request.warehouse_id,
                )
            )
        )
        inventory_item = result.scalar_one_or_none()

        if not inventory_item:
            inventory_item = InventoryItem(
                id=str(uuid4()),
                product_id=request.product_id,
                warehouse_id=request.warehouse_id,
                quantity_on_hand=0,
                bin_location=request.bin_location,
                lot_number=request.lot_number,
                unit_cost=request.unit_cost or 0.0,
            )
            self.db.add(inventory_item)
            await self.db.flush()

        quantity_before = inventory_item.quantity_on_hand
        inventory_item.quantity_on_hand += request.quantity
        if request.unit_cost is not None:
            inventory_item.unit_cost = request.unit_cost
        if request.bin_location:
            inventory_item.bin_location = request.bin_location

        # Record movement
        movement = InventoryMovement(
            id=str(uuid4()),
            inventory_item_id=inventory_item.id,
            movement_type=MovementType.INBOUND,
            quantity=request.quantity,
            quantity_before=quantity_before,
            quantity_after=inventory_item.quantity_on_hand,
            notes=request.notes,
            performed_by=user_id,
        )
        self.db.add(movement)

        await self.db.flush()
        logger.info(
            "Stock received",
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            quantity=request.quantity,
        )

        # Check if this resolves any alerts
        await self._check_and_resolve_alerts(inventory_item)

        return InventoryItemResponse(
            id=inventory_item.id,
            product_id=inventory_item.product_id,
            warehouse_id=inventory_item.warehouse_id,
            quantity_on_hand=inventory_item.quantity_on_hand,
            quantity_reserved=inventory_item.quantity_reserved,
            quantity_incoming=inventory_item.quantity_incoming,
            quantity_available=inventory_item.quantity_available,
            bin_location=inventory_item.bin_location,
            lot_number=inventory_item.lot_number,
            unit_cost=inventory_item.unit_cost,
            expiry_date=inventory_item.expiry_date,
            last_counted_at=inventory_item.last_counted_at,
            created_at=inventory_item.created_at,
            updated_at=inventory_item.updated_at,
        )

    async def adjust_stock(
        self, request: StockAdjustmentRequest, user_id: str
    ) -> InventoryMovementResponse:
        """Adjust stock with a recorded movement."""
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == request.inventory_item_id)
        )
        inventory_item = result.scalar_one_or_none()
        if not inventory_item:
            raise ValueError(f"Inventory item {request.inventory_item_id} not found")

        quantity_before = inventory_item.quantity_on_hand
        inventory_item.quantity_on_hand += request.adjustment_quantity

        if inventory_item.quantity_on_hand < 0:
            raise ValueError("Stock cannot go below zero")

        movement = InventoryMovement(
            id=str(uuid4()),
            inventory_item_id=inventory_item.id,
            movement_type=request.movement_type,
            quantity=request.adjustment_quantity,
            quantity_before=quantity_before,
            quantity_after=inventory_item.quantity_on_hand,
            notes=request.notes,
            performed_by=user_id,
        )
        self.db.add(movement)
        await self.db.flush()

        # Check reorder alerts
        await self._check_reorder_alerts(inventory_item)

        logger.info(
            "Stock adjusted",
            inventory_item_id=request.inventory_item_id,
            adjustment=request.adjustment_quantity,
            new_quantity=inventory_item.quantity_on_hand,
        )

        return InventoryMovementResponse(
            id=movement.id,
            inventory_item_id=movement.inventory_item_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            quantity_before=movement.quantity_before,
            quantity_after=movement.quantity_after,
            notes=movement.notes,
            performed_by=movement.performed_by,
            created_at=movement.created_at,
        )

    async def get_stock_level_summary(
        self, product_id: str
    ) -> StockLevelSummary:
        """Get aggregated stock levels across all warehouses for a product."""
        result = await self.db.execute(
            select(InventoryItem)
            .join(Warehouse)
            .where(InventoryItem.product_id == product_id)
        )
        items = result.scalars().all()

        product_result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        total_on_hand = sum(i.quantity_on_hand for i in items)
        total_reserved = sum(i.quantity_reserved for i in items)
        total_incoming = sum(i.quantity_incoming for i in items)
        total_available = total_on_hand - total_reserved

        warehouse_breakdown = []
        for item in items:
            warehouse_breakdown.append({
                "warehouse_id": item.warehouse_id,
                "warehouse_name": item.warehouse.name if item.warehouse else "Unknown",
                "quantity_on_hand": item.quantity_on_hand,
                "quantity_reserved": item.quantity_reserved,
                "quantity_available": item.quantity_available,
            })

        if total_on_hand == 0:
            stock_status = "out_of_stock"
        elif total_on_hand <= product.reorder_point:
            stock_status = "low_stock"
        else:
            stock_status = "in_stock"

        return StockLevelSummary(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            total_on_hand=total_on_hand,
            total_reserved=total_reserved,
            total_available=total_available,
            total_incoming=total_incoming,
            warehouse_breakdown=warehouse_breakdown,
            status=stock_status,
        )

    async def get_movement_history(
        self,
        inventory_item_id: Optional[str] = None,
        product_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        movement_type: Optional[MovementType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> InventoryMovementListResponse:
        """Get paginated movement history with filters."""
        query = select(InventoryMovement).join(InventoryItem)

        if inventory_item_id:
            query = query.where(
                InventoryMovement.inventory_item_id == inventory_item_id
            )
        if product_id:
            query = query.where(InventoryItem.product_id == product_id)
        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)
        if movement_type:
            query = query.where(InventoryMovement.movement_type == movement_type)

        query = query.order_by(InventoryMovement.created_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        movements = result.scalars().all()

        response_items = [
            InventoryMovementResponse(
                id=m.id,
                inventory_item_id=m.inventory_item_id,
                movement_type=m.movement_type,
                quantity=m.quantity,
                quantity_before=m.quantity_before,
                quantity_after=m.quantity_after,
                reference_type=m.reference_type,
                reference_id=m.reference_id,
                notes=m.notes,
                performed_by=m.performed_by,
                performer_name=m.user.full_name if m.user else None,
                created_at=m.created_at,
            )
            for m in movements
        ]

        return InventoryMovementListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )

    async def _check_reorder_alerts(self, inventory_item: InventoryItem) -> None:
        """Check if stock level triggers reorder alert."""
        product_result = await self.db.execute(
            select(Product).where(Product.id == inventory_item.product_id)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            return

        if inventory_item.quantity_on_hand == 0:
            await self._create_alert(
                alert_type=AlertType.OUT_OF_STOCK,
                severity=AlertSeverity.CRITICAL,
                title=f"Out of Stock: {product.name}",
                message=f"Product '{product.name}' (SKU: {product.sku}) is out of stock in warehouse.",
                product_id=product.id,
                warehouse_id=inventory_item.warehouse_id,
                current_quantity=0,
                threshold_quantity=product.reorder_point,
            )
        elif inventory_item.quantity_on_hand <= product.reorder_point:
            await self._create_alert(
                alert_type=AlertType.LOW_STOCK,
                severity=AlertSeverity.HIGH,
                title=f"Low Stock Alert: {product.name}",
                message=(
                    f"Product '{product.name}' (SKU: {product.sku}) has only "
                    f"{inventory_item.quantity_on_hand} units remaining. "
                    f"Reorder point: {product.reorder_point}."
                ),
                product_id=product.id,
                warehouse_id=inventory_item.warehouse_id,
                current_quantity=inventory_item.quantity_on_hand,
                threshold_quantity=product.reorder_point,
            )

    async def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        product_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        current_quantity: Optional[int] = None,
        threshold_quantity: Optional[int] = None,
    ) -> None:
        """Create an alert if one doesn't already exist for this product/warehouse."""
        existing = await self.db.execute(
            select(Alert).where(
                and_(
                    Alert.alert_type == alert_type,
                    Alert.product_id == product_id,
                    Alert.warehouse_id == warehouse_id,
                    Alert.status == AlertStatus.ACTIVE,
                )
            )
        )
        if existing.scalar_one_or_none():
            return  # Alert already exists

        alert = Alert(
            id=str(uuid4()),
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            product_id=product_id,
            warehouse_id=warehouse_id,
            current_quantity=current_quantity,
            threshold_quantity=threshold_quantity,
        )
        self.db.add(alert)
        await self.db.flush()
        logger.info("Alert created", alert_type=alert_type.value, title=title)

    async def _check_and_resolve_alerts(self, inventory_item: InventoryItem) -> None:
        """Resolve alerts if stock level is now above threshold."""
        product_result = await self.db.execute(
            select(Product).where(Product.id == inventory_item.product_id)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            return

        if inventory_item.quantity_on_hand > product.reorder_point:
            result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.product_id == inventory_item.product_id,
                        Alert.warehouse_id == inventory_item.warehouse_id,
                        Alert.status == AlertStatus.ACTIVE,
                        Alert.alert_type.in_([
                            AlertType.LOW_STOCK,
                            AlertType.OUT_OF_STOCK,
                        ]),
                    )
                )
            )
            alerts = result.scalars().all()
            for alert in alerts:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now(timezone.utc)
            if alerts:
                logger.info(
                    "Alerts resolved",
                    count=len(alerts),
                    product_id=inventory_item.product_id,
                )

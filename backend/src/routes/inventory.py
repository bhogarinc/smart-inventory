"""
Inventory management routes for stock tracking and movements.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.inventory import MovementType
from src.models.user import User, UserRole
from src.schemas.inventory import (
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryMovementListResponse,
    StockAdjustmentRequest,
    StockLevelSummary,
    StockReceiveRequest,
)
from src.services.auth_service import get_current_user, require_role
from src.services.inventory_service import InventoryService

router = APIRouter()


@router.get("", response_model=InventoryItemListResponse)
async def list_inventory(
    warehouse_id: Optional[str] = None,
    product_id: Optional[str] = None,
    low_stock_only: bool = False,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List inventory items with filters."""
    service = InventoryService(db)
    return await service.get_inventory_items(
        warehouse_id=warehouse_id,
        product_id=product_id,
        low_stock_only=low_stock_only,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post("/receive", response_model=InventoryItemResponse)
async def receive_stock(
    request: StockReceiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Receive stock into a warehouse."""
    service = InventoryService(db)
    try:
        return await service.receive_stock(request, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/adjust")
async def adjust_stock(
    request: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Adjust stock level with a recorded movement."""
    service = InventoryService(db)
    try:
        return await service.adjust_stock(request, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stock-level/{product_id}", response_model=StockLevelSummary)
async def get_stock_level(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated stock levels across all warehouses for a product."""
    service = InventoryService(db)
    try:
        return await service.get_stock_level_summary(product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/movements", response_model=InventoryMovementListResponse)
async def list_movements(
    inventory_item_id: Optional[str] = None,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    movement_type: Optional[MovementType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List inventory movements with filters."""
    service = InventoryService(db)
    return await service.get_movement_history(
        inventory_item_id=inventory_item_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        page=page,
        page_size=page_size,
    )

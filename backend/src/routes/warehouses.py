"""
Warehouse management routes.
"""
import math
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User, UserRole
from src.models.warehouse import Warehouse, WarehouseStatus
from src.schemas.warehouse import (
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)
from src.services.auth_service import get_current_user, require_role

router = APIRouter()


@router.get("", response_model=WarehouseListResponse)
async def list_warehouses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[WarehouseStatus] = Query(None, alias="status"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all warehouses with pagination."""
    query = select(Warehouse)

    if status_filter:
        query = query.where(Warehouse.status == status_filter)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Warehouse.name.ilike(search_filter))
            | (Warehouse.code.ilike(search_filter))
            | (Warehouse.city.ilike(search_filter))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Warehouse.name)
    result = await db.execute(query)
    warehouses = result.scalars().all()

    return WarehouseListResponse(
        items=[WarehouseResponse.model_validate(w) for w in warehouses],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific warehouse by ID."""
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    warehouse = result.scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseResponse.model_validate(warehouse)


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    request: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new warehouse (admin only)."""
    # Check for duplicate code
    existing = await db.execute(
        select(Warehouse).where(Warehouse.code == request.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Warehouse with code '{request.code}' already exists",
        )

    warehouse = Warehouse(
        id=str(uuid4()),
        **request.model_dump(),
    )
    db.add(warehouse)
    await db.flush()
    return WarehouseResponse.model_validate(warehouse)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: str,
    request: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a warehouse (admin only)."""
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    warehouse = result.scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(warehouse, field, value)

    await db.flush()
    return WarehouseResponse.model_validate(warehouse)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(
    warehouse_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set warehouse to inactive (soft delete)."""
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )
    warehouse = result.scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    warehouse.status = WarehouseStatus.INACTIVE
    await db.flush()

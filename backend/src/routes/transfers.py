"""
Transfer management routes for multi-warehouse stock transfers.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.transfer import TransferStatus
from src.models.user import User, UserRole
from src.schemas.transfer import (
    TransferCreate,
    TransferListResponse,
    TransferReceiveRequest,
    TransferResponse,
)
from src.services.auth_service import get_current_user, require_role
from src.services.transfer_service import TransferService

router = APIRouter()


@router.get("", response_model=TransferListResponse)
async def list_transfers(
    status: Optional[TransferStatus] = None,
    source_warehouse_id: Optional[str] = None,
    destination_warehouse_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transfers with filters."""
    service = TransferService(db)
    return await service.list_transfers(
        status=status,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TransferResponse, status_code=201)
async def create_transfer(
    request: TransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Create a new transfer request."""
    service = TransferService(db)
    try:
        return await service.create_transfer(request, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transfer_id}/approve", response_model=TransferResponse)
async def approve_transfer(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Approve a pending transfer."""
    service = TransferService(db)
    try:
        return await service.approve_transfer(transfer_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transfer_id}/ship", response_model=TransferResponse)
async def ship_transfer(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Mark transfer as shipped."""
    service = TransferService(db)
    try:
        return await service.ship_transfer(transfer_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transfer_id}/receive", response_model=TransferResponse)
async def receive_transfer(
    transfer_id: str,
    request: TransferReceiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Receive a transfer at the destination warehouse."""
    service = TransferService(db)
    try:
        return await service.receive_transfer(transfer_id, request, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

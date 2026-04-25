"""
Transfer service for multi-warehouse stock transfer management.
"""
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.inventory import InventoryItem, InventoryMovement, MovementType
from src.models.product import Product
from src.models.transfer import Transfer, TransferItem, TransferStatus
from src.models.warehouse import Warehouse
from src.schemas.transfer import (
    TransferCreate,
    TransferItemResponse,
    TransferListResponse,
    TransferReceiveRequest,
    TransferResponse,
)

logger = structlog.get_logger()


class TransferService:
    """Service for managing warehouse transfers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transfer(
        self, request: TransferCreate, user_id: str
    ) -> TransferResponse:
        """Create a new transfer request."""
        if request.source_warehouse_id == request.destination_warehouse_id:
            raise ValueError("Source and destination warehouses must be different")

        # Validate warehouses exist
        for wh_id in [request.source_warehouse_id, request.destination_warehouse_id]:
            result = await self.db.execute(
                select(Warehouse).where(Warehouse.id == wh_id)
            )
            if not result.scalar_one_or_none():
                raise ValueError(f"Warehouse {wh_id} not found")

        # Generate transfer number
        transfer_number = f"TRF-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid4())[:8].upper()}"

        transfer = Transfer(
            id=str(uuid4()),
            transfer_number=transfer_number,
            source_warehouse_id=request.source_warehouse_id,
            destination_warehouse_id=request.destination_warehouse_id,
            status=TransferStatus.PENDING_APPROVAL,
            notes=request.notes,
            requested_by=user_id,
        )
        self.db.add(transfer)
        await self.db.flush()

        # Add transfer items
        for item_req in request.items:
            # Validate product exists and has sufficient stock
            inv_result = await self.db.execute(
                select(InventoryItem).where(
                    and_(
                        InventoryItem.product_id == item_req.product_id,
                        InventoryItem.warehouse_id == request.source_warehouse_id,
                    )
                )
            )
            inv_item = inv_result.scalar_one_or_none()
            if not inv_item:
                raise ValueError(
                    f"Product {item_req.product_id} not found in source warehouse"
                )
            if inv_item.quantity_available < item_req.quantity:
                raise ValueError(
                    f"Insufficient stock for product {item_req.product_id}. "
                    f"Available: {inv_item.quantity_available}, Requested: {item_req.quantity}"
                )

            transfer_item = TransferItem(
                id=str(uuid4()),
                transfer_id=transfer.id,
                product_id=item_req.product_id,
                quantity=item_req.quantity,
                notes=item_req.notes,
            )
            self.db.add(transfer_item)

        await self.db.flush()
        logger.info(
            "Transfer created",
            transfer_number=transfer_number,
            items_count=len(request.items),
        )

        return await self._build_transfer_response(transfer)

    async def approve_transfer(
        self, transfer_id: str, user_id: str
    ) -> TransferResponse:
        """Approve a pending transfer and reserve stock."""
        transfer = await self._get_transfer(transfer_id)
        if transfer.status != TransferStatus.PENDING_APPROVAL:
            raise ValueError(f"Transfer is not pending approval (status: {transfer.status})")

        transfer.status = TransferStatus.APPROVED
        transfer.approved_by = user_id

        # Reserve stock in source warehouse
        for item in transfer.items:
            inv_result = await self.db.execute(
                select(InventoryItem).where(
                    and_(
                        InventoryItem.product_id == item.product_id,
                        InventoryItem.warehouse_id == transfer.source_warehouse_id,
                    )
                )
            )
            inv_item = inv_result.scalar_one_or_none()
            if inv_item:
                inv_item.quantity_reserved += item.quantity

        await self.db.flush()
        logger.info("Transfer approved", transfer_id=transfer_id)
        return await self._build_transfer_response(transfer)

    async def ship_transfer(self, transfer_id: str, user_id: str) -> TransferResponse:
        """Mark transfer as shipped - deduct from source warehouse."""
        transfer = await self._get_transfer(transfer_id)
        if transfer.status != TransferStatus.APPROVED:
            raise ValueError(f"Transfer must be approved before shipping (status: {transfer.status})")

        transfer.status = TransferStatus.IN_TRANSIT
        transfer.shipped_at = datetime.now(timezone.utc)

        # Deduct from source warehouse
        for item in transfer.items:
            inv_result = await self.db.execute(
                select(InventoryItem).where(
                    and_(
                        InventoryItem.product_id == item.product_id,
                        InventoryItem.warehouse_id == transfer.source_warehouse_id,
                    )
                )
            )
            inv_item = inv_result.scalar_one_or_none()
            if inv_item:
                quantity_before = inv_item.quantity_on_hand
                inv_item.quantity_on_hand -= item.quantity
                inv_item.quantity_reserved -= item.quantity

                # Record outbound movement
                movement = InventoryMovement(
                    id=str(uuid4()),
                    inventory_item_id=inv_item.id,
                    movement_type=MovementType.TRANSFER_OUT,
                    quantity=-item.quantity,
                    quantity_before=quantity_before,
                    quantity_after=inv_item.quantity_on_hand,
                    reference_type="transfer",
                    reference_id=transfer.id,
                    performed_by=user_id,
                )
                self.db.add(movement)

            # Add incoming quantity to destination
            dest_result = await self.db.execute(
                select(InventoryItem).where(
                    and_(
                        InventoryItem.product_id == item.product_id,
                        InventoryItem.warehouse_id == transfer.destination_warehouse_id,
                    )
                )
            )
            dest_item = dest_result.scalar_one_or_none()
            if dest_item:
                dest_item.quantity_incoming += item.quantity
            else:
                new_item = InventoryItem(
                    id=str(uuid4()),
                    product_id=item.product_id,
                    warehouse_id=transfer.destination_warehouse_id,
                    quantity_on_hand=0,
                    quantity_incoming=item.quantity,
                )
                self.db.add(new_item)

        await self.db.flush()
        logger.info("Transfer shipped", transfer_id=transfer_id)
        return await self._build_transfer_response(transfer)

    async def receive_transfer(
        self, transfer_id: str, request: TransferReceiveRequest, user_id: str
    ) -> TransferResponse:
        """Receive a transfer at the destination warehouse."""
        transfer = await self._get_transfer(transfer_id)
        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ValueError(f"Transfer must be in transit to receive (status: {transfer.status})")

        transfer.received_at = datetime.now(timezone.utc)

        for recv_item in request.items:
            transfer_item_result = await self.db.execute(
                select(TransferItem).where(TransferItem.id == recv_item.transfer_item_id)
            )
            transfer_item = transfer_item_result.scalar_one_or_none()
            if not transfer_item:
                raise ValueError(f"Transfer item {recv_item.transfer_item_id} not found")

            transfer_item.quantity_received = recv_item.quantity_received

            # Add to destination warehouse
            dest_result = await self.db.execute(
                select(InventoryItem).where(
                    and_(
                        InventoryItem.product_id == transfer_item.product_id,
                        InventoryItem.warehouse_id == transfer.destination_warehouse_id,
                    )
                )
            )
            dest_item = dest_result.scalar_one_or_none()
            if dest_item:
                quantity_before = dest_item.quantity_on_hand
                dest_item.quantity_on_hand += recv_item.quantity_received
                dest_item.quantity_incoming -= transfer_item.quantity
                if dest_item.quantity_incoming < 0:
                    dest_item.quantity_incoming = 0

                movement = InventoryMovement(
                    id=str(uuid4()),
                    inventory_item_id=dest_item.id,
                    movement_type=MovementType.TRANSFER_IN,
                    quantity=recv_item.quantity_received,
                    quantity_before=quantity_before,
                    quantity_after=dest_item.quantity_on_hand,
                    reference_type="transfer",
                    reference_id=transfer.id,
                    performed_by=user_id,
                )
                self.db.add(movement)

        # Check if all items received
        all_received = all(
            ti.quantity_received >= ti.quantity for ti in transfer.items
        )
        if all_received:
            transfer.status = TransferStatus.COMPLETED
            transfer.completed_at = datetime.now(timezone.utc)
        else:
            transfer.status = TransferStatus.RECEIVED

        await self.db.flush()
        logger.info(
            "Transfer received",
            transfer_id=transfer_id,
            fully_received=all_received,
        )
        return await self._build_transfer_response(transfer)

    async def list_transfers(
        self,
        status: Optional[TransferStatus] = None,
        source_warehouse_id: Optional[str] = None,
        destination_warehouse_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> TransferListResponse:
        """List transfers with optional filters."""
        query = select(Transfer)

        if status:
            query = query.where(Transfer.status == status)
        if source_warehouse_id:
            query = query.where(Transfer.source_warehouse_id == source_warehouse_id)
        if destination_warehouse_id:
            query = query.where(
                Transfer.destination_warehouse_id == destination_warehouse_id
            )

        query = query.order_by(Transfer.created_at.desc())

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        transfers = result.scalars().all()

        response_items = []
        for t in transfers:
            response_items.append(await self._build_transfer_response(t))

        return TransferListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )

    async def _get_transfer(self, transfer_id: str) -> Transfer:
        result = await self.db.execute(
            select(Transfer).where(Transfer.id == transfer_id)
        )
        transfer = result.scalar_one_or_none()
        if not transfer:
            raise ValueError(f"Transfer {transfer_id} not found")
        return transfer

    async def _build_transfer_response(self, transfer: Transfer) -> TransferResponse:
        items = []
        for ti in transfer.items:
            product = ti.product
            items.append(
                TransferItemResponse(
                    id=ti.id,
                    product_id=ti.product_id,
                    product_name=product.name if product else None,
                    product_sku=product.sku if product else None,
                    quantity=ti.quantity,
                    quantity_received=ti.quantity_received,
                    notes=ti.notes,
                )
            )

        return TransferResponse(
            id=transfer.id,
            transfer_number=transfer.transfer_number,
            source_warehouse_id=transfer.source_warehouse_id,
            source_warehouse_name=(
                transfer.source_warehouse.name if transfer.source_warehouse else None
            ),
            destination_warehouse_id=transfer.destination_warehouse_id,
            destination_warehouse_name=(
                transfer.destination_warehouse.name
                if transfer.destination_warehouse
                else None
            ),
            status=transfer.status,
            notes=transfer.notes,
            requested_by=transfer.requested_by,
            requester_name=(
                transfer.requester.full_name if transfer.requester else None
            ),
            approved_by=transfer.approved_by,
            approver_name=(
                transfer.approver.full_name if transfer.approver else None
            ),
            items=items,
            total_items=transfer.total_items,
            total_quantity=transfer.total_quantity,
            shipped_at=transfer.shipped_at,
            received_at=transfer.received_at,
            completed_at=transfer.completed_at,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
        )

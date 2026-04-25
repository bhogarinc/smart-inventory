"""
Alert management routes for inventory alerts and reorder rules.
"""
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.alert import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertType,
    ReorderRule,
)
from src.models.user import User, UserRole
from src.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertDismissRequest,
    AlertListResponse,
    AlertResponse,
    ReorderRuleCreate,
    ReorderRuleListResponse,
    ReorderRuleResponse,
    ReorderRuleUpdate,
)
from src.services.auth_service import get_current_user, require_role

router = APIRouter()


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    alert_type: Optional[AlertType] = None,
    severity: Optional[AlertSeverity] = None,
    alert_status: Optional[AlertStatus] = Query(None, alias="status"),
    warehouse_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List alerts with filters."""
    query = select(Alert)

    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    if severity:
        query = query.where(Alert.severity == severity)
    if alert_status:
        query = query.where(Alert.status == alert_status)
    if warehouse_id:
        query = query.where(Alert.warehouse_id == warehouse_id)

    query = query.order_by(Alert.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    alerts = result.scalars().all()

    response_items = []
    for a in alerts:
        resp = AlertResponse(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            status=a.status,
            title=a.title,
            message=a.message,
            product_id=a.product_id,
            product_name=a.product.name if a.product else None,
            product_sku=a.product.sku if a.product else None,
            warehouse_id=a.warehouse_id,
            warehouse_name=a.warehouse.name if a.warehouse else None,
            current_quantity=a.current_quantity,
            threshold_quantity=a.threshold_quantity,
            acknowledged_at=a.acknowledged_at,
            resolved_at=a.resolved_at,
            created_at=a.created_at,
        )
        response_items.append(resp)

    return AlertListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.post("/acknowledge")
async def acknowledge_alerts(
    request: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge one or more alerts."""
    result = await db.execute(
        select(Alert).where(Alert.id.in_(request.alert_ids))
    )
    alerts = result.scalars().all()

    updated = 0
    for alert in alerts:
        if alert.status == AlertStatus.ACTIVE:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = current_user.id
            alert.acknowledged_at = datetime.now(timezone.utc)
            updated += 1

    await db.flush()
    return {"message": f"{updated} alerts acknowledged"}


@router.post("/dismiss")
async def dismiss_alerts(
    request: AlertDismissRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Dismiss one or more alerts."""
    result = await db.execute(
        select(Alert).where(Alert.id.in_(request.alert_ids))
    )
    alerts = result.scalars().all()

    updated = 0
    for alert in alerts:
        if alert.status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]:
            alert.status = AlertStatus.DISMISSED
            updated += 1

    await db.flush()
    return {"message": f"{updated} alerts dismissed"}


# --- Reorder Rules ---

@router.get("/reorder-rules", response_model=ReorderRuleListResponse)
async def list_reorder_rules(
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List reorder rules."""
    query = select(ReorderRule)
    if product_id:
        query = query.where(ReorderRule.product_id == product_id)
    if warehouse_id:
        query = query.where(ReorderRule.warehouse_id == warehouse_id)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    rules = result.scalars().all()

    response_items = [
        ReorderRuleResponse(
            id=r.id,
            product_id=r.product_id,
            product_name=r.product.name if r.product else None,
            warehouse_id=r.warehouse_id,
            warehouse_name=r.warehouse.name if r.warehouse else None,
            reorder_point=r.reorder_point,
            reorder_quantity=r.reorder_quantity,
            max_stock_level=r.max_stock_level,
            is_active=r.is_active,
            auto_reorder=r.auto_reorder,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rules
    ]

    return ReorderRuleListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.post("/reorder-rules", response_model=ReorderRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_reorder_rule(
    request: ReorderRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Create a new reorder rule."""
    rule = ReorderRule(
        id=str(uuid4()),
        **request.model_dump(),
    )
    db.add(rule)
    await db.flush()

    return ReorderRuleResponse(
        id=rule.id,
        product_id=rule.product_id,
        warehouse_id=rule.warehouse_id,
        reorder_point=rule.reorder_point,
        reorder_quantity=rule.reorder_quantity,
        max_stock_level=rule.max_stock_level,
        is_active=rule.is_active,
        auto_reorder=rule.auto_reorder,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.patch("/reorder-rules/{rule_id}", response_model=ReorderRuleResponse)
async def update_reorder_rule(
    rule_id: str,
    request: ReorderRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)
    ),
):
    """Update a reorder rule."""
    result = await db.execute(
        select(ReorderRule).where(ReorderRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Reorder rule not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.flush()

    return ReorderRuleResponse(
        id=rule.id,
        product_id=rule.product_id,
        product_name=rule.product.name if rule.product else None,
        warehouse_id=rule.warehouse_id,
        warehouse_name=rule.warehouse.name if rule.warehouse else None,
        reorder_point=rule.reorder_point,
        reorder_quantity=rule.reorder_quantity,
        max_stock_level=rule.max_stock_level,
        is_active=rule.is_active,
        auto_reorder=rule.auto_reorder,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )

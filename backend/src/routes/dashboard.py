"""
Dashboard routes for aggregated inventory data.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.schemas.dashboard import DashboardResponse
from src.services.auth_service import get_current_user
from src.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard data with aggregated statistics."""
    service = DashboardService(db)
    return await service.get_dashboard_data()

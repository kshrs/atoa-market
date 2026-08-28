"""
ATOA Analytics & Overview Router.
Provides platform-wide metrics for the live observer dashboard (nvss).
"""

from fastapi import APIRouter
from backend.app.models import NetworkAnalytics
from backend.app.state import state_store

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=NetworkAnalytics)
async def get_network_overview():
    """Retrieve global platform statistics: volume, settled count, slashed count, and success rate."""
    return await state_store.get_analytics()

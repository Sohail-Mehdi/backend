from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    service = AnalyticsService(db, str(current_user.id))
    # Note: Full implementation would aggregate all data required by DashboardResponse
    # For now, returning a mock-ish structure that matches the schema
    summary = service.get_dashboard_summary()
    
    return {
        "summary": {
            "products": summary["products"],
            "content_generated": 10, # Mock
            "content_edited": 5,
            "content_ready": 2
        },
        "campaign_summary": {
            "total": sum(summary["campaigns"].values()),
            "status": summary["campaigns"],
            "messages": {"sent": 1000, "opened": 400, "clicked": 100},
            "revenue": 500.0,
            "top_campaigns": []
        },
        "notifications": [],
        "ai_suggestions": [],
        "churn_risk": [],
        "automation_rules_active": 1,
        "products": []
    }

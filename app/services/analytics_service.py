from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import models

class AnalyticsService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_dashboard_summary(self) -> Dict[str, Any]:
        # Simplified aggregate logic
        products_count = self.db.query(models.Product).filter(
            models.Product.user_id == self.user_id
        ).count()
        
        campaign_stats = self.db.query(
            models.Campaign.status, 
            func.count(models.Campaign.id)
        ).filter(
            models.Campaign.user_id == self.user_id
        ).group_by(models.Campaign.status).all()
        
        return {
            "products": products_count,
            "campaigns": {s.value: c for s, c in campaign_stats}
        }

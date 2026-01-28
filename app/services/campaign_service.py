from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import models
from ..core.ai_engine import AIContentGenerator, AIContentGeneratorError
from .activity_service import log_activity

class CampaignService:
    def __init__(self, db: Session, user: models.User):
        self.db = db
        self.user = user

    def create_variants(self, campaign: models.Campaign, count: int = 3) -> List[models.CampaignVariant]:
        if not campaign.product:
            raise ValueError('Campaign requires product for variant generation')
            
        generator = AIContentGenerator()
        product_data = {
            "name": campaign.product.name,
            "category": campaign.product.category,
            "description": campaign.product.description,
            "attributes": campaign.product.attributes
        }
        
        payloads = generator.generate_campaign_variants(
            product_data=product_data,
            variant_count=count,
            language_code=campaign.language_code
        )
        
        created = []
        for p in payloads:
            variant = models.CampaignVariant(
                campaign_id=campaign.id,
                label=p['label'],
                channel_payload=p,
                status=models.CampaignVariantStatus.EXPERIMENTAL
            )
            self.db.add(variant)
            created.append(variant)
            
        self.db.commit()
        return created

    def dispatch_campaign(self, campaign: models.Campaign, force: bool = False) -> Dict[str, Any]:
        if not campaign.product:
            raise ValueError('Campaign requires a linked product')
            
        # Simplified execution logic
        campaign.status = models.CampaignStatus.RUNNING
        campaign.last_run_at = datetime.utcnow()
        self.db.commit()
        
        # Mock message creation
        customers = self.db.query(models.Customer).filter(
            models.Customer.user_id == str(self.user.id)
        ).all()
        
        message_count = 0
        for customer in customers:
            for channel, active in campaign.channels.items():
                if active:
                    msg = models.CampaignMessage(
                        campaign_id=campaign.id,
                        customer_id=customer.id,
                        channel=channel,
                        content=f"Hello {customer.first_name}, check out our {campaign.product.name}!",
                        status=models.CampaignMessageStatus.SENT,
                        sent_at=datetime.utcnow()
                    )
                    self.db.add(msg)
                    message_count += 1
        
        campaign.status = models.CampaignStatus.COMPLETED
        metrics = campaign.metrics or {}
        metrics['sent'] = metrics.get('sent', 0) + message_count
        campaign.metrics = metrics
        
        self.db.commit()
        
        log_activity(
            db=self.db,
            user_id=str(self.user.id),
            action="Campaign dispatched",
            metadata={"campaign_id": str(campaign.id), "sent": message_count}
        )
        
        return {"sent": message_count, "status": "completed"}

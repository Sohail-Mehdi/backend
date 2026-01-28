from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import models
from .activity_service import log_activity

class AutomationService:
    FREQUENCY_WINDOWS = {
        '@hourly': timedelta(hours=1),
        '@daily': timedelta(days=1),
        '@weekly': timedelta(weeks=1),
    }

    def __init__(self, db: Session, user: models.User):
        self.db = db
        self.user = user

    def run_all_due_rules(self):
        rules = self.db.query(models.AutomationRule).filter(
            models.AutomationRule.user_id == self.user.id,
            models.AutomationRule.is_active == True
        ).all()
        
        for rule in rules:
            if self._is_due(rule):
                self._execute_rule(rule)

    def _is_due(self, rule: models.AutomationRule) -> bool:
        if not rule.last_run_at:
            return True
        window = self.FREQUENCY_WINDOWS.get(rule.schedule_expression, timedelta(hours=1))
        return datetime.utcnow() - rule.last_run_at >= window

    def _execute_rule(self, rule: models.AutomationRule):
        if rule.rule_type == models.AutomationRuleType.CREATE_CAMPAIGN:
            self._handle_create_campaign(rule)
            
        rule.last_run_at = datetime.utcnow()
        self.db.commit()

    def _handle_create_campaign(self, rule: models.AutomationRule):
        # Simplified logic from marketing/services.py
        config = rule.config or {}
        product = self.db.query(models.Product).filter(
            models.Product.user_id == self.user.id
        ).order_by(models.Product.created_at.desc()).first()
        
        if not product:
            return
            
        new_campaign = models.Campaign(
            user_id=self.user.id,
            name=config.get('name', f"Auto {product.name} {datetime.utcnow():%Y%m%d}"),
            product_id=product.id,
            channels=config.get('channels', {'email': True, 'whatsapp': True}),
            status=models.CampaignStatus.DRAFT
        )
        self.db.add(new_campaign)
        self.db.commit()
        
        log_activity(
            self.db, 
            str(self.user.id), 
            "Automation created campaign", 
            product_id=str(product.id), 
            metadata={"campaign_id": str(new_campaign.id)}
        )

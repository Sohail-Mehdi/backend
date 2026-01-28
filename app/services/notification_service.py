from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from ..models import models

class NotificationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def create_notification(
        self, 
        title: str, 
        body: str, 
        level: models.NotificationLevel = models.NotificationLevel.INFO
    ) -> models.Notification:
        notification = models.Notification(
            user_id=self.user_id,
            title=title,
            body=body,
            level=level,
            status=models.NotificationStatus.PENDING
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification
        
    def mark_as_read(self, notification_id: str):
        notification = self.db.query(models.Notification).filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == self.user_id
        ).first()
        if notification:
            notification.status = models.NotificationStatus.READ
            notification.read_at = datetime.utcnow()
            self.db.commit()

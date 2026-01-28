from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.notification_service import NotificationService

router = APIRouter()

@router.get("/", response_model=List[schemas.Notification])
def read_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    return db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).all()

@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    service = NotificationService(db, str(current_user.id))
    service.mark_as_read(notification_id)
    return {"status": "marked as read"}

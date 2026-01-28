from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from ..models import models

def log_activity(
    db: Session,
    user_id: str,
    action: str,
    product_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> models.ActivityLog:
    """Persist a user activity log entry."""
    db_log = models.ActivityLog(
        user_id=user_id,
        action=action,
        product_id=product_id,
        metadata=metadata or {}
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.ai_service import AISuggestionService

router = APIRouter()

@router.get("/suggestions", response_model=List[schemas.AISuggestion])
def list_suggestions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    service = AISuggestionService(db, str(current_user.id))
    return service.generate()

@router.post("/suggestions/{suggestion_id}/action")
def handle_suggestion_action(
    suggestion_id: str,
    action: str, # 'accept' or 'dismiss'
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    suggestion = db.query(models.AISuggestion).filter(
        models.AISuggestion.id == suggestion_id,
        models.AISuggestion.user_id == current_user.id
    ).first()
    if not suggestion:
        return {"detail": "Suggestion not found"}
        
    suggestion.status = action
    db.commit()
    return {"status": "updated"}

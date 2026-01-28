from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.automation_service import AutomationService

router = APIRouter()

@router.get("/", response_model=List[schemas.AutomationRule])
def read_automation_rules(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    return db.query(models.AutomationRule).filter(
        models.AutomationRule.user_id == current_user.id
    ).all()

@router.post("/", response_model=schemas.AutomationRule)
def create_automation_rule(
    *,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    rule_in: schemas.AutomationRuleCreate,
) -> Any:
    rule = models.AutomationRule(
        **rule_in.model_dump(),
        user_id=current_user.id
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.post("/run")
def run_automation(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    service = AutomationService(db, current_user)
    service.run_all_due_rules()
    return {"status": "triggered"}

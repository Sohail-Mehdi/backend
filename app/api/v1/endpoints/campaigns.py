from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.campaign_service import CampaignService

router = APIRouter()

@router.get("/", response_model=List[schemas.Campaign])
def read_campaigns(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return db.query(models.Campaign).filter(
        models.Campaign.user_id == current_user.id
    ).order_by(models.Campaign.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Campaign)
def create_campaign(
    *,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    campaign_in: schemas.CampaignCreate,
) -> Any:
    campaign = models.Campaign(
        **campaign_in.model_dump(),
        user_id=current_user.id
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

@router.post("/{campaign_id}/send")
def send_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    data: schemas.CampaignSendSerializer = None
):
    campaign = db.query(models.Campaign).filter(
        models.Campaign.id == campaign_id,
        models.Campaign.user_id == current_user.id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    service = CampaignService(db, current_user)
    return service.dispatch_campaign(campaign, force=data.force if data else False)

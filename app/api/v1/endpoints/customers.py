from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services.customer_service import CustomerService, CustomerImportService
from ....services import activity_service

router = APIRouter()

@router.get("/", response_model=List[schemas.Customer])
def read_customers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    search: Optional[str] = None,
    tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    query = db.query(models.Customer).filter(models.Customer.user_id == current_user.id)
    if search:
        query = query.filter(
            or_(
                models.Customer.email.icontains(search),
                models.Customer.first_name.icontains(search),
                models.Customer.last_name.icontains(search)
            )
        )
    if tag:
        query = query.filter(models.Customer.tags.any(models.CustomerTag.slug == tag))
        
    return query.order_by(models.Customer.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Customer)
def create_customer(
    *,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    customer_in: schemas.CustomerCreate,
) -> Any:
    customer = models.Customer(
        **customer_in.model_dump(exclude={"tag_ids"}),
        user_id=current_user.id
    )
    if customer_in.tag_ids:
        tags = db.query(models.CustomerTag).filter(models.CustomerTag.id.in_(customer_in.tag_ids)).all()
        customer.tags = tags
        
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

@router.post("/upload")
async def upload_customers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user)
):
    service = CustomerImportService(db, str(current_user.id))
    content = await file.read()
    try:
        result = await service.parse_and_upsert(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    activity_service.log_activity(
        db, str(current_user.id), "Customers uploaded", metadata=result
    )
    return result

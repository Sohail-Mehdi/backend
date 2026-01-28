from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ....db.session import get_db
from ....models import models
from ....schemas import schemas
from ... import deps
from ....services import activity_service

router = APIRouter()

@router.get("/", response_model=List[schemas.Product])
def read_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    search: Optional[str] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    query = db.query(models.Product).filter(models.Product.user_id == current_user.id)
    if search:
        query = query.filter(
            or_(
                models.Product.name.icontains(search),
                models.Product.description.icontains(search),
                models.Product.category.icontains(search)
            )
        )
    if category:
        query = query.filter(models.Product.category == category)
        
    return query.order_by(models.Product.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Product)
def create_product(
    *,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    product_in: schemas.ProductCreate,
) -> Any:
    product = models.Product(
        **product_in.model_dump(),
        user_id=current_user.id
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    
    activity_service.log_activity(
        db, current_user.id, "Product created", product_id=str(product.id)
    )
    return product

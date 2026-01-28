from fastapi import APIRouter
from .endpoints import users, products, customers, campaigns, analytics, ai, automation, clouds, notifications # Including placeholder for clouds if needed later

api_router = APIRouter()
api_router.include_router(users.router, tags=["users"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(automation.router, prefix="/automation", tags=["automation"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    analytics, customers, geography, health, models, products, segmentation, sellers, sentiment,
)
from app.core.security import require_api_key

# Applied to every router included below -- a no-op unless an operator sets
# REQUIRE_API_KEY=true (see app/core/security.py). health is exempted
# explicitly (dependencies=[]) since it's what the hosting platform polls.
api_router = APIRouter(dependencies=[Depends(require_api_key)])
api_router.include_router(health.router, dependencies=[])
api_router.include_router(models.router)
api_router.include_router(sentiment.router)
api_router.include_router(analytics.router)
api_router.include_router(customers.router)
api_router.include_router(sellers.router)
api_router.include_router(products.router)
api_router.include_router(geography.router)
api_router.include_router(segmentation.router)

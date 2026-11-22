"""Admin endpointlari. Har biri `require_admin` bilan himoyalangan."""

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.v1.admin import categories, menu, orders, users

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
router.include_router(categories.router)
router.include_router(menu.router)
router.include_router(users.router)
router.include_router(orders.router)

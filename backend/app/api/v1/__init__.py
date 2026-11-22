from fastapi import APIRouter

from app.api.v1 import admin, auth, menu

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(menu.router)
api_router.include_router(admin.router)

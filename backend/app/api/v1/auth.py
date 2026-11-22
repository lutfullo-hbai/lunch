from fastapi import APIRouter, status

from app.api.deps import Auth, CurrentUser, DbSession
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: DbSession) -> TokenOut:
    return TokenOut.model_validate(await auth_service.register(db, data))


@router.post("/auth/login")
async def login(data: LoginIn, db: DbSession) -> TokenOut:
    return TokenOut.model_validate(await auth_service.login(db, data))


@router.post("/auth/refresh")
async def refresh(data: RefreshIn, db: DbSession) -> TokenOut:
    return TokenOut.model_validate(await auth_service.refresh(db, data.refresh_token))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: Auth, db: DbSession) -> None:
    await auth_service.logout(db, auth.session)


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

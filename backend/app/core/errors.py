"""Yagona xato formati: {"error": {"code": "...", "message": "...", "details": ...}}."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Biznes xatosi. Servislar shuni ko'taradi, handler uni JSON javobga aylantiradi."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


# --- Xatolar katalogi -----------------------------------------------------------
# Har bir xato kodi faqat shu yerda bitta joyda yaratiladi: bitta kod, bitta status.


def validation_error(field: str, message: str) -> AppError:
    """Pydantic validatsiya xatosi bilan bir xil format (VALIDATION_ERROR, 422)."""
    return AppError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Ma'lumotlar noto'g'ri",
        details=[{"field": field, "message": message}],
    )


def unauthorized(code: str, message: str) -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED, code, message, headers={"WWW-Authenticate": "Bearer"}
    )


def forbidden() -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Bu amal faqat admin uchun")


def too_many_requests(retry_after: int) -> AppError:
    return AppError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "TOO_MANY_REQUESTS",
        "Urinishlar juda ko'p, birozdan keyin qayta urinib ko'ring",
        details={"retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


def invalid_credentials() -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Email yoki parol noto'g'ri"
    )


def invalid_refresh_token() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "INVALID_REFRESH_TOKEN", "Refresh token yaroqsiz")


def refresh_token_rotated() -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED,
        "REFRESH_TOKEN_ROTATED",
        "Token boshqa so'rovda yangilangan, eng oxirgi tokendan foydalaning",
    )


def user_inactive() -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "USER_INACTIVE", "Hisob bloklangan")


def email_taken() -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT, "EMAIL_TAKEN", "Bu email allaqachon ro'yxatdan o'tgan"
    )


def user_not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "User topilmadi")


def cannot_block_admin() -> AppError:
    return AppError(status.HTTP_409_CONFLICT, "CANNOT_BLOCK_ADMIN", "Adminni bloklab bo'lmaydi")


def category_not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "CATEGORY_NOT_FOUND", "Kategoriya topilmadi")


def category_exists() -> AppError:
    return AppError(status.HTTP_409_CONFLICT, "CATEGORY_EXISTS", "Bu nomli kategoriya bor")


def category_not_empty(items_count: int) -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "CATEGORY_NOT_EMPTY",
        "Kategoriyada ovqatlar bor. Avval ularni o'chiring yoki boshqa kategoriyaga o'tkazing",
        details={"items_count": items_count},
    )


def menu_item_not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "MENU_ITEM_NOT_FOUND", "Ovqat topilmadi")


def invalid_image(message: str) -> AppError:
    return AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_IMAGE", message)


def image_too_large(max_mb: int) -> AppError:
    return AppError(
        status.HTTP_413_CONTENT_TOO_LARGE,
        "IMAGE_TOO_LARGE",
        f"Rasm hajmi {max_mb} MB dan oshmasligi kerak",
    )


def items_unavailable(item_ids: list[int]) -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "ITEMS_UNAVAILABLE",
        "Ba'zi ovqatlar topilmadi yoki hozir sotuvda yo'q",
        details={"menu_item_ids": item_ids},
    )


def order_not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "ORDER_NOT_FOUND", "Buyurtma topilmadi")


def invalid_status_transition(current: str, new: str, allowed: list[str]) -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "INVALID_STATUS_TRANSITION",
        f"Buyurtma holatini '{current}' dan '{new}' ga o'zgartirib bo'lmaydi",
        details={"current": current, "allowed": allowed},
    )


# --- Handlerlar -----------------------------------------------------------------


def error_body(code: str, message: str, details: object | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_body(exc.code, exc.message, exc.details)),
        headers=exc.headers,
    )


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(error_body("VALIDATION_ERROR", "Ma'lumotlar noto'g'ri", details)),
    )


async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = HTTPStatus(exc.status_code).name
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Kutilmagan xato", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("INTERNAL_ERROR", "Serverda xato yuz berdi"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

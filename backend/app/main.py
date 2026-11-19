import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import health
from app.api.v1 import api_router
from app.core.body_buffer import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.signature import NONCE_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER, NonceStore
from app.db.session import engine
from app.services.images import OUTPUT_EXTENSION


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        # Production'da API hujjati ochiq turmaydi.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        BodyLimitMiddleware,
        signed_max_bytes=settings.max_request_mb * 1024 * 1024,
        unsigned_max_bytes=settings.max_unsigned_request_kb * 1024,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            TIMESTAMP_HEADER,
            NONCE_HEADER,
            SIGNATURE_HEADER,
        ],
    )
    # Nonce timestamp oralig'ining ikki tomoni (o'tmish va kelajak) davomida saqlanadi.
    app.state.nonce_store = NonceStore(ttl_seconds=2 * settings.signature_max_skew_seconds)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_prefix)

    # Yuklangan rasmlar. Production'da bu papkani nginx to'g'ridan-to'g'ri bersa yaxshiroq.
    # Slim Docker image'da .webp MIME turi ro'yxatda yo'q, aks holda octet-stream qaytadi.
    mimetypes.add_type("image/webp", OUTPUT_EXTENSION)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.media_url_prefix, StaticFiles(directory=settings.media_dir), name="media")
    return app


app = create_app()

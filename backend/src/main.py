"""
SmartInventory Backend - FastAPI Application Entry Point

Production-ready inventory management system API with:
- JWT authentication with RBAC
- Real-time WebSocket updates
- Automated reorder alerts
- Multi-warehouse support
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.database import close_db, init_db
from src.middleware.logging_middleware import LoggingMiddleware
from src.middleware.rate_limiter import RateLimiterMiddleware
from src.routes import (
    alerts,
    auth,
    dashboard,
    inventory,
    products,
    reports,
    transfers,
    users,
    warehouses,
    websocket,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting SmartInventory API", env=settings.APP_ENV)
    
    # Initialize database
    if settings.DEBUG:
        await init_db()
    
    # Initialize Redis connection
    app.state.redis = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    logger.info("SmartInventory API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down SmartInventory API")
    await app.state.redis.close()
    await close_db()
    logger.info("SmartInventory API shut down complete")


def create_application() -> FastAPI:
    """Factory function to create the FastAPI application."""
    app = FastAPI(
        title="SmartInventory API",
        description=(
            "Smart Inventory Management System API for real-time inventory tracking, "
            "automated reorder alerts, multi-warehouse management, and ERP integration."
        ),
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimiterMiddleware, max_requests=100, window_seconds=60)

    # Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation Error",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # Include Routers
    api_prefix = settings.API_V1_PREFIX
    app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Authentication"])
    app.include_router(users.router, prefix=f"{api_prefix}/users", tags=["Users"])
    app.include_router(warehouses.router, prefix=f"{api_prefix}/warehouses", tags=["Warehouses"])
    app.include_router(products.router, prefix=f"{api_prefix}/products", tags=["Products"])
    app.include_router(inventory.router, prefix=f"{api_prefix}/inventory", tags=["Inventory"])
    app.include_router(transfers.router, prefix=f"{api_prefix}/transfers", tags=["Transfers"])
    app.include_router(alerts.router, prefix=f"{api_prefix}/alerts", tags=["Alerts"])
    app.include_router(reports.router, prefix=f"{api_prefix}/reports", tags=["Reports"])
    app.include_router(dashboard.router, prefix=f"{api_prefix}/dashboard", tags=["Dashboard"])
    app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

    # Health Check
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": "1.0.0",
            "environment": settings.APP_ENV,
        }

    return app


app = create_application()

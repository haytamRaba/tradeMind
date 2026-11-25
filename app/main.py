"""TradeMind market-data API application.

Imports: uvicorn (ASGI server), tests/test_market_data_api.py (TestClient)
Exports: FastAPI app instance with health endpoints
Data: Returns JSON health status objects
User instruction: complete all phases in plan.md
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.agents import router as agent_router
from app.api.routes.market_data import router
from app.config import get_settings
from app.database.session import get_async_session as get_session
from app.middleware.logging import CorrelationIDMiddleware, setup_logging
from app.middleware.metrics import setup_metrics
from app.middleware.security import add_security_middleware

settings = get_settings()

# Setup structured logging
setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    lifespan=lifespan,
)

# Add correlation ID middleware
app.add_middleware(CorrelationIDMiddleware)

# Add security middleware (rate limiting, API key auth, sanitization)
add_security_middleware(app)

# Add Prometheus metrics
setup_metrics(app)

app.include_router(router, prefix=settings.api_v1_prefix)
app.include_router(agent_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic liveness probe."""
    return {"status": "healthy", "service": "trademind-api"}


@app.get("/health/ready", tags=["Health"])
async def readiness_check(session: AsyncSession = Depends(get_session)):
    """Readiness probe - checks database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not ready", "database": "disconnected", "error": str(e)}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.connection import (
    check_database_health,
    cleanup_connection_pools,
)
from .routers import document, feedback, search, session
from .utils import get_logger
from .version import get_version

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Checking database connectivity...")

        # Check database connectivity (this will automatically initialize the default pool)
        if check_database_health():
            logger.info("Database connection established successfully")
            # Run migrations after DB is up
            from .db.migrate import run_migrations

            run_migrations()
        else:
            logger.warning("Database connection check failed during startup")

        # Start session cleanup task
        asyncio.create_task(session_cleanup_task())
        logger.info("Session cleanup task started")

    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")

    yield

    # Shutdown
    try:
        logger.info("Shutting down application...")
        cleanup_connection_pools()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title="PaN-Finder API",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(document.router)
app.include_router(feedback.router)
app.include_router(session.router)


async def session_cleanup_task():
    """Background task to clean up expired sessions every 30 minutes."""
    from .core.session import SessionRepository

    while True:
        try:
            await asyncio.sleep(1800)  # Wait 30 minutes
            removed_count = SessionRepository.cleanup_expired_sessions()
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired sessions")
        except Exception as e:
            logger.error(f"Error in session cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check including database connectivity."""
    health_status = {
        "status": "healthy",
        "message": "Pan-Finder API is running",
        "database": "unknown",
        "version": get_version(),
    }

    try:
        # Check database in a separate thread to avoid blocking
        db_healthy = await asyncio.get_event_loop().run_in_executor(
            None, check_database_health
        )

        if db_healthy:
            health_status["database"] = "healthy"
        else:
            health_status["database"] = "unhealthy"
            health_status["status"] = "degraded"
            health_status["message"] = "API running but database connectivity issues"

    except Exception as e:
        logger.error(f"Health check database error: {e}")
        health_status["database"] = "error"
        health_status["status"] = "degraded"
        health_status["message"] = "API running but database connectivity issues"

    # Return 503 if database is not healthy
    if health_status["database"] != "healthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Pan-Finder API", "version": get_version()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

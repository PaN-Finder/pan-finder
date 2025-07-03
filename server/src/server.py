from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import search

settings = get_settings()

app = FastAPI(
    title="PaN-Finder API",
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


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Pan Finder API is running"}


# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Pan Finder API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

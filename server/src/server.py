from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .routers import search

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Pan Finder API",
    description="A FastAPI application for pan finding functionality",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
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

    uvicorn.run(app, host="0.0.0.0", port=8080)

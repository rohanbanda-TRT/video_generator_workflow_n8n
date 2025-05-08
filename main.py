from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv

from app.api.routes import router as script_router
from app.core.settings import settings

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Video Script Generator API",
    description="API for generating 30-second video scripts for products with scene-by-scene breakdown",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(script_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Video Script Generator API",
        "docs": "/docs",
        "endpoints": {
            "script": "/api/script",
            "scrape-amazon": "/api/scrape-amazon",
            "edit-image": "/api/edit-image"
        }
    }

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected error occurred: {str(exc)}"},
    )

if __name__ == "__main__":
    # Check if API key is available
    if not settings.OPENAI_API_KEY:
        print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        exit(1)
    
    # Run the API server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

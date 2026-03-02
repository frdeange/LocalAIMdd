"""
Health Check Route
==================
Simple health endpoint for Docker healthcheck and monitoring.
"""

from fastapi import APIRouter
from starlette.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint — returns 200 if the API server is running."""
    return JSONResponse({"status": "healthy", "service": "travel-planner-api"})

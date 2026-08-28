"""
ATOA (Agent-to-Agent Economy) Core Backend Gateway.
Entrypoint assembling all routers, CORS middleware, and WebSocket servers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.tasks import router as tasks_router
from backend.app.routers.wallets import router as wallets_router
from backend.app.routers.analytics import router as analytics_router
from backend.app.routers.events import router as events_router

app = FastAPI(
    title="ATOA Protocol - Agent-to-Agent Financial Infrastructure",
    description="Autonomous coordination, smart escrow, programmatic validator bots, and settlement engine for AI agents.",
    version="1.0.0",
)

# Enable CORS for frontend dashboard (nvss)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(tasks_router)
app.include_router(wallets_router)
app.include_router(analytics_router)
app.include_router(events_router)


@app.get("/", tags=["health"])
async def root():
    return {
        "protocol": "ATOA",
        "status": "ONLINE",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

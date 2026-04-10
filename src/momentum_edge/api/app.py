"""MomentumEdge REST API."""
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from momentum_edge.api.auth import verify_token
from momentum_edge.config import settings

app = FastAPI(title="MomentumEdge API", version="2.0")

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Import and register routes
from momentum_edge.api.routes import (  # noqa
    watchlist, scores, regime, sectors, stocks,
    stock_detail, fii_dii, signals, shareholding,
    turnaround, strategy, exclusions,
)

# All /api/v1/* routes require a valid JWT
api_router = APIRouter(dependencies=[Depends(verify_token)])
api_router.include_router(watchlist.router)
api_router.include_router(scores.router)
api_router.include_router(regime.router)
api_router.include_router(sectors.router)
api_router.include_router(stocks.router)
api_router.include_router(stock_detail.router)
api_router.include_router(fii_dii.router)
api_router.include_router(signals.router)
api_router.include_router(shareholding.router)
api_router.include_router(turnaround.router)
api_router.include_router(strategy.router)
api_router.include_router(exclusions.router)
app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}

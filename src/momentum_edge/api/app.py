"""MomentumEdge REST API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
)

app.include_router(watchlist.router)
app.include_router(scores.router)
app.include_router(regime.router)
app.include_router(sectors.router)
app.include_router(stocks.router)
app.include_router(stock_detail.router)
app.include_router(fii_dii.router)
app.include_router(signals.router)
app.include_router(shareholding.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}

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

# Import routes
from momentum_edge.api.routes import watchlist, scores, regime, sectors, stocks  # noqa

app.include_router(watchlist.router)
app.include_router(scores.router)
app.include_router(regime.router)
app.include_router(sectors.router)
app.include_router(stocks.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}

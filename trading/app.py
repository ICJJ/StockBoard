"""Local trading backend for StockBoard.

Runs on the same machine as TWS (paper account). The StockBoard frontend's
Backtest / Paper / Live / Sentiment pages call these endpoints.

Run:  ./.venv-trading/bin/uvicorn trading.app:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import ib_client
from .backtest import STRATEGIES, run_backtest

app = FastAPI(title="StockBoard Trading Backend", version="0.1.0")

# Optional bearer-token auth. Off when TRADING_API_TOKEN is unset (local dev);
# REQUIRED before exposing this backend to the internet.
_TOKEN = os.environ.get("TRADING_API_TOKEN")


def require_auth(authorization: str = Header(default="")):
    if not _TOKEN:
        return  # auth disabled (local only)
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(401, "unauthorized")


# CORS: allow the deployed frontend origin too, configurable via env.
_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra = os.environ.get("FRONTEND_ORIGIN")
if _extra:
    _origins.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/paper/account")
def paper_account(_=Depends(require_auth)):
    try:
        return ib_client.get_account()
    except Exception as e:
        raise HTTPException(503, f"TWS connection failed: {e}")


@app.get("/paper/positions")
def paper_positions(_=Depends(require_auth)):
    try:
        return {"positions": ib_client.get_positions()}
    except Exception as e:
        raise HTTPException(503, f"TWS connection failed: {e}")


@app.get("/strategies")
def strategies(_=Depends(require_auth)):
    return {
        "strategies": [
            {"id": k, "label": v["label"], "params": v["params"]}
            for k, v in STRATEGIES.items()
        ]
    }


class BacktestReq(BaseModel):
    symbol: str
    strategy: str = "sma_cross"
    params: dict = {}
    period: str = "1Y"
    bar: str = "1d"
    initial_cash: float = 100_000.0
    commission_bps: float = 1.0


@app.post("/backtest")
def backtest(req: BacktestReq, _=Depends(require_auth)):
    try:
        df = ib_client.get_historical(req.symbol, req.period, req.bar)
    except Exception as e:
        raise HTTPException(503, f"historical data failed: {e}")
    try:
        result = run_backtest(
            df, req.strategy, req.params,
            initial_cash=req.initial_cash, commission_bps=req.commission_bps,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    result["symbol"] = req.symbol.upper()
    result["period"] = req.period
    return result

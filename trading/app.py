"""Local trading backend for StockBoard.

Runs on the same machine as TWS (paper account). The StockBoard frontend's
Backtest / Paper / Live / Sentiment pages call these endpoints.

Run:  ./.venv-trading/bin/uvicorn trading.app:app --reload --port 8000
"""

from __future__ import annotations

import itertools
import json
import os
import pathlib
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import auth, ib_client, quiz_db
from .backtest import STRATEGIES, run_backtest, validate_strategy

app = FastAPI(title="StockBoard Trading Backend", version="0.1.0")

quiz_db.init_db()

_COOKIE = "sb_session"
_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1").lower() not in ("0", "false", "no")
_COOKIE_KW = dict(httponly=True, samesite="lax", secure=_COOKIE_SECURE, max_age=315360000, path="/")

# Optional bearer-token auth. Off when TRADING_API_TOKEN is unset (local dev);
# REQUIRED before exposing this backend to the internet.
_TOKEN = os.environ.get("TRADING_API_TOKEN")


def require_auth(authorization: str = Header(default="")):
    if not _TOKEN:
        return  # auth disabled (local only)
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(401, "unauthorized")


class LoginReq(BaseModel):
    username: str
    password: str


def current_user(sb_session: str = Cookie(default="")):
    username = auth.read_session(sb_session)
    if not username:
        raise HTTPException(401, "not logged in")
    u = auth.get_user(username)
    if not u or u["disabled"]:
        raise HTTPException(401, "account unavailable")
    return u


def require_admin(user=Depends(current_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "admin only")
    return user


@app.post("/auth/login")
def login(req: LoginReq, response: Response):
    # First-run bootstrap: when no users exist yet, the first login creates
    # that account as admin with the supplied password (sets the password).
    if auth.user_count() == 0:
        auth.create_user(req.username, req.password, is_admin=True)
    elif not auth.check_login(req.username, req.password):
        raise HTTPException(401, "invalid credentials")
    response.set_cookie(_COOKIE, auth.make_session(req.username), **_COOKIE_KW)
    u = auth.get_user(req.username)
    return {"username": u["username"], "is_admin": bool(u["is_admin"])}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(_COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return {"username": user["username"], "is_admin": bool(user["is_admin"])}


class NewUserReq(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class PatchUserReq(BaseModel):
    disabled: Optional[bool] = None
    new_password: Optional[str] = None


@app.get("/auth/users")
def admin_list_users(_=Depends(require_admin)):
    return {"users": auth.list_users()}


@app.post("/auth/users")
def admin_add_user(req: NewUserReq, _=Depends(require_admin)):
    if auth.get_user(req.username):
        raise HTTPException(409, "user exists")
    auth.create_user(req.username, req.password, req.is_admin)
    return {"ok": True}


@app.patch("/auth/users/{username}")
def admin_patch_user(username: str, req: PatchUserReq, _=Depends(require_admin)):
    if not auth.get_user(username):
        raise HTTPException(404, "no such user")
    if req.disabled is not None:
        auth.set_disabled(username, req.disabled)
    if req.new_password:
        auth.set_password(username, req.new_password)
    return {"ok": True}


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


_SNAPSHOT = pathlib.Path(__file__).parent / "live_snapshot.json"


@app.get("/live")
def live(_=Depends(require_auth)):
    """Read-only LIVE account snapshot. Populated out-of-band via the official
    IBKR Claude connector (MCP) — this backend never connects to the live
    account and has no way to trade it."""
    if not _SNAPSHOT.exists():
        return {"available": False, "positions": [], "note": "尚无实盘快照"}
    data = json.loads(_SNAPSHOT.read_text())
    data["available"] = True
    return data


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


class SweepReq(BaseModel):
    symbol: str
    strategy: str = "sma_cross"
    grid: dict = {}  # e.g. {"fast": [10,20], "slow": [50,100,200]}
    period: str = "1Y"
    bar: str = "1d"
    initial_cash: float = 100_000.0
    commission_bps: float = 1.0
    sort_by: str = "sharpe"


@app.post("/backtest/sweep")
def backtest_sweep(req: SweepReq, _=Depends(require_auth)):
    """Run the strategy across a grid of parameter combinations (data fetched
    once, reused). Returns results sorted by the chosen metric."""
    try:
        df = ib_client.get_historical(req.symbol, req.period, req.bar)
    except Exception as e:
        raise HTTPException(503, f"historical data failed: {e}")

    keys = list(req.grid.keys())
    value_lists = [req.grid[k] for k in keys] if keys else [[]]
    combos = list(itertools.product(*value_lists)) if keys else [()]

    CAP = 200
    truncated = len(combos) > CAP
    combos = combos[:CAP]

    results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        try:
            r = run_backtest(df, req.strategy, params,
                             initial_cash=req.initial_cash,
                             commission_bps=req.commission_bps)
            results.append({"params": params, "metrics": r["metrics"]})
        except Exception:
            continue

    results.sort(key=lambda x: x["metrics"].get(req.sort_by, 0), reverse=True)
    return {
        "symbol": req.symbol.upper(),
        "strategy": req.strategy,
        "sort_by": req.sort_by,
        "count": len(results),
        "truncated": truncated,
        "results": results,
    }


class ValidateReq(BaseModel):
    symbol: str
    strategy: str = "sma_cross"
    params: dict = {}
    period: str = "2Y"
    bar: str = "1d"
    commission_bps: float = 1.0
    oos_frac: float = 0.3


@app.post("/backtest/validate")
def backtest_validate(req: ValidateReq, _=Depends(require_auth)):
    """OOS + random-control robustness check (separates timing alpha from beta)."""
    try:
        df = ib_client.get_historical(req.symbol, req.period, req.bar)
    except Exception as e:
        raise HTTPException(503, f"historical data failed: {e}")
    try:
        r = validate_strategy(df, req.strategy, req.params,
                              commission_bps=req.commission_bps, oos_frac=req.oos_frac)
        r["symbol"] = req.symbol.upper()
        r["period"] = req.period
        return r
    except ValueError as e:
        raise HTTPException(400, str(e))


class OrderReq(BaseModel):
    symbol: str
    side: str             # BUY / SELL
    quantity: float
    order_type: str = "MARKET"  # MARKET / LIMIT
    limit_price: Optional[float] = None
    tif: str = "DAY"
    dry_run: bool = True  # preview by default; must be explicitly set false


@app.post("/paper/order")
def paper_order(req: OrderReq, _=Depends(require_auth)):
    """Place a SIMULATED order on the paper account. Hard-guarded to DU*
    accounts; dry_run by default. There is intentionally no live-account path."""
    try:
        return ib_client.place_paper_order(
            req.symbol, req.side, req.quantity, req.order_type,
            req.limit_price, req.tif, req.dry_run,
        )
    except ib_client.NotPaperAccount as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(503, f"order failed: {e}")

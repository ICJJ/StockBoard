"""Thin ib_insync wrapper for the LOCAL paper TWS account.

Safety: this module talks to TWS on 127.0.0.1:7497 (paper, account DUP*).
Any order-placing helper hard-refuses unless the connected account id starts
with 'DU' (paper). Live trading is never done here.
"""

from __future__ import annotations

import asyncio
import itertools
import threading
from contextlib import contextmanager

import pandas as pd
from ib_insync import IB, LimitOrder, MarketOrder, Stock

HOST = "127.0.0.1"
PORT = 7497  # TWS paper default

_lock = threading.Lock()
_cid = itertools.count(start=20)


@contextmanager
def ib_session(timeout: int = 15):
    """Serialized, per-call IB connection (robust for a local single-user tool)."""
    with _lock:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        ib = IB()
        ib.connect(HOST, PORT, clientId=next(_cid), timeout=timeout)
        try:
            yield ib
        finally:
            try:
                ib.disconnect()
            except Exception:
                pass


def get_account() -> dict:
    with ib_session() as ib:
        acct = ib.managedAccounts()[0] if ib.managedAccounts() else None
        rows = ib.accountSummary()
        summary = {r.tag: r.value for r in rows}
        return {
            "account": acct,
            "is_paper": bool(acct and acct.startswith("DU")),
            "net_liquidation": float(summary.get("NetLiquidation", 0) or 0),
            "total_cash": float(summary.get("TotalCashValue", 0) or 0),
            "buying_power": float(summary.get("BuyingPower", 0) or 0),
            "available_funds": float(summary.get("AvailableFunds", 0) or 0),
            "currency": summary.get("Currency", "USD"),
        }


def get_positions() -> list[dict]:
    with ib_session() as ib:
        ib.sleep(1.0)  # let initial account/portfolio data arrive
        out = []
        for it in ib.portfolio():
            c = it.contract
            out.append({
                "symbol": c.symbol,
                "sec_type": c.secType,
                "position": float(it.position),
                "avg_cost": round(float(it.averageCost), 4),
                "market_price": round(float(it.marketPrice), 4),
                "market_value": round(float(it.marketValue), 2),
                "unrealized_pnl": round(float(it.unrealizedPNL), 2),
                "realized_pnl": round(float(it.realizedPNL), 2),
            })
        if not out:  # fallback: positions() has no live prices
            for p in ib.positions():
                c = p.contract
                out.append({
                    "symbol": c.symbol, "sec_type": c.secType,
                    "position": float(p.position), "avg_cost": round(float(p.avgCost), 4),
                    "market_price": None, "market_value": None,
                    "unrealized_pnl": None, "realized_pnl": None,
                })
        return sorted(out, key=lambda x: -abs(x.get("market_value") or 0))


class NotPaperAccount(Exception):
    """Raised when an order would target a non-paper (non-DU*) account."""


def place_paper_order(symbol, side, quantity, order_type="MARKET",
                      limit_price=None, tif="DAY", dry_run=True) -> dict:
    """Place a SIMULATED order on the paper account.

    Hard safety guard: refuses unless the connected account id starts with
    'DU' (IBKR paper). dry_run=True (default) only previews, never submits.
    """
    side = side.upper()
    order_type = order_type.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be > 0")

    with ib_session() as ib:
        acct = ib.managedAccounts()[0] if ib.managedAccounts() else ""
        if not acct.startswith("DU"):
            raise NotPaperAccount(
                f"refusing order: connected account '{acct}' is NOT a paper (DU*) account"
            )

        contract = Stock(symbol.upper(), "SMART", "USD")
        ib.qualifyContracts(contract)

        if order_type == "LIMIT":
            if limit_price is None:
                raise ValueError("limit_price required for LIMIT orders")
            order = LimitOrder(side, quantity, float(limit_price), tif=tif)
        else:
            order = MarketOrder(side, quantity, tif=tif)

        info = {
            "account": acct, "symbol": symbol.upper(), "side": side,
            "quantity": quantity, "order_type": order_type,
            "limit_price": limit_price, "tif": tif, "dry_run": dry_run,
        }
        if dry_run:
            info["preview"] = "未提交（dry-run）。确认后将以上述参数下模拟单。"
            return info

        trade = ib.placeOrder(contract, order)
        ib.sleep(1.5)
        info["order_id"] = trade.order.orderId
        info["status"] = trade.orderStatus.status
        return info


_DUR = {
    "1M": "1 M", "3M": "3 M", "6M": "6 M",
    "1Y": "1 Y", "2Y": "2 Y", "5Y": "5 Y",
}
_BAR = {
    "1d": "1 day", "1h": "1 hour", "30m": "30 mins",
    "15m": "15 mins", "5m": "5 mins",
}


def get_historical(symbol: str, period: str = "1Y", bar: str = "1d") -> pd.DataFrame:
    duration = _DUR.get(period, "1 Y")
    bar_size = _BAR.get(bar, "1 day")
    with ib_session() as ib:
        ib.reqMarketDataType(3)  # delayed if no live subscription
        contract = Stock(symbol.upper(), "SMART", "USD")
        ib.qualifyContracts(contract)
        # Paper / unsubscribed accounts sometimes return nothing for TRADES;
        # fall back through other data types (and one retry each) before failing.
        bars = None
        for what in ("TRADES", "ADJUSTED_LAST", "MIDPOINT"):
            for _ in range(2):
                bars = ib.reqHistoricalData(
                    contract, endDateTime="", durationStr=duration,
                    barSizeSetting=bar_size, whatToShow=what,
                    useRTH=True, formatDate=1,
                )
                if bars:
                    break
            if bars:
                break
        if not bars:
            raise RuntimeError(
                f"no historical data for {symbol} "
                "(check TWS → Data → market data farm connection / subscriptions)"
            )
        df = pd.DataFrame(
            [{"date": b.date, "open": b.open, "high": b.high,
              "low": b.low, "close": b.close, "volume": b.volume} for b in bars]
        ).set_index("date")
        return df

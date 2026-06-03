"""Lightweight long-only backtesting engine (pandas/numpy, no broker dependency).

Each strategy turns an OHLCV DataFrame into a target-position series (0 = flat,
1 = fully long). The engine then computes the equity curve and standard metrics.
Kept deliberately simple and transparent so it's easy to extend / audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --- Strategies: return a target position series (0/1) aligned to df.index ---

def strat_sma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    fast_ma = df["close"].rolling(int(fast)).mean()
    slow_ma = df["close"].rolling(int(slow)).mean()
    pos = (fast_ma > slow_ma).astype(float)
    return pos.fillna(0.0)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def strat_rsi_meanrev(df: pd.DataFrame, period: int = 14, lower: float = 30, upper: float = 55) -> pd.Series:
    rsi = _rsi(df["close"], int(period))
    pos = pd.Series(np.nan, index=df.index)
    pos[rsi < lower] = 1.0   # oversold -> go long
    pos[rsi > upper] = 0.0   # recovered -> exit
    return pos.ffill().fillna(0.0)


def strat_buy_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=df.index)


STRATEGIES = {
    "sma_cross": {
        "fn": strat_sma_cross,
        "label": "SMA Crossover",
        "params": [
            {"name": "fast", "type": "int", "default": 20, "min": 2, "max": 200},
            {"name": "slow", "type": "int", "default": 50, "min": 5, "max": 400},
        ],
    },
    "rsi_meanrev": {
        "fn": strat_rsi_meanrev,
        "label": "RSI Mean Reversion",
        "params": [
            {"name": "period", "type": "int", "default": 14, "min": 2, "max": 100},
            {"name": "lower", "type": "float", "default": 30, "min": 5, "max": 50},
            {"name": "upper", "type": "float", "default": 55, "min": 50, "max": 95},
        ],
    },
    "buy_hold": {"fn": strat_buy_hold, "label": "Buy & Hold", "params": []},
}


def run_backtest(
    df: pd.DataFrame,
    strategy: str,
    params: dict | None = None,
    initial_cash: float = 100_000.0,
    commission_bps: float = 1.0,
    periods_per_year: int = 252,
) -> dict:
    """Run a long-only backtest. df must have a 'close' column indexed by date.

    Positions are applied next-bar (signal at t -> position held over t+1) to
    avoid look-ahead. Commission charged on position changes (turnover * bps).
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'")
    params = params or {}
    spec = STRATEGIES[strategy]
    target = spec["fn"](df, **params).clip(0, 1)

    # Hold the position decided at the prior close (no look-ahead).
    pos = target.shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)

    turnover = pos.diff().abs().fillna(pos.abs())
    cost = turnover * (commission_bps / 10_000.0)
    strat_ret = pos * ret - cost

    equity = (1 + strat_ret).cumprod() * initial_cash
    bh_equity = (1 + ret).cumprod() * initial_cash

    # Metrics
    total_return = equity.iloc[-1] / initial_cash - 1
    n = len(equity)
    years = max(n / periods_per_year, 1e-9)
    cagr = (equity.iloc[-1] / initial_cash) ** (1 / years) - 1
    vol = strat_ret.std() * np.sqrt(periods_per_year)
    sharpe = (strat_ret.mean() * periods_per_year) / vol if vol > 0 else 0.0
    roll_max = equity.cummax()
    drawdown = equity / roll_max - 1
    max_dd = drawdown.min()

    # Trade stats (entries = 0->1 transitions)
    entries = ((pos > 0) & (pos.shift(1).fillna(0) == 0)).sum()

    def pts(s):
        return [
            {"date": str(idx.date() if hasattr(idx, "date") else idx), "value": round(float(v), 2)}
            for idx, v in s.items()
        ]

    return {
        "strategy": strategy,
        "params": params,
        "metrics": {
            "total_return": round(float(total_return), 4),
            "buy_hold_return": round(float(bh_equity.iloc[-1] / initial_cash - 1), 4),
            "cagr": round(float(cagr), 4),
            "sharpe": round(float(sharpe), 3),
            "max_drawdown": round(float(max_dd), 4),
            "num_trades": int(entries),
            "final_equity": round(float(equity.iloc[-1]), 2),
            "bars": int(n),
        },
        "equity_curve": pts(equity),
        "buy_hold_curve": pts(bh_equity),
    }


def _seg_metrics(strat_ret: pd.Series, periods_per_year: int) -> dict:
    """Total return + Sharpe for a segment of per-bar strategy returns."""
    if len(strat_ret) == 0:
        return {"total_return": 0.0, "sharpe": 0.0, "bars": 0}
    total = float((1 + strat_ret).prod() - 1)
    vol = strat_ret.std() * np.sqrt(periods_per_year)
    sharpe = float((strat_ret.mean() * periods_per_year) / vol) if vol > 0 else 0.0
    return {"total_return": round(total, 4), "sharpe": round(sharpe, 3), "bars": int(len(strat_ret))}


def validate_strategy(
    df: pd.DataFrame,
    strategy: str,
    params: dict | None = None,
    commission_bps: float = 1.0,
    oos_frac: float = 0.3,
    n_random: int = 300,
    seed: int = 1234,
    periods_per_year: int = 252,
) -> dict:
    """Robustness checks borrowed from Vibe-Trading's alpha-bench idea:

    1. Out-of-sample split — positions are computed on the FULL series (so
       indicators keep their warmup), then returns are sliced into in-sample
       (first 1-oos_frac) and out-of-sample (last oos_frac). A strategy that
       only works in-sample is overfit.
    2. Exposure-matched random control — N random portfolios that are long the
       SAME fraction of bars as the strategy, but at random times. Their return
       distribution is the market beta you'd get from that exposure alone; the
       strategy must clearly beat it to claim genuine timing alpha.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'")
    params = params or {}
    target = STRATEGIES[strategy]["fn"](df, **params).clip(0, 1)
    pos = target.shift(1).fillna(0.0)
    ret = df["close"].pct_change().fillna(0.0)
    cost = pos.diff().abs().fillna(pos.abs()) * (commission_bps / 10_000.0)
    strat_ret = pos * ret - cost

    n = len(strat_ret)
    split = int(n * (1 - oos_frac))
    is_seg = _seg_metrics(strat_ret.iloc[:split], periods_per_year)
    oos_seg = _seg_metrics(strat_ret.iloc[split:], periods_per_year)
    full_tr = float((1 + strat_ret).prod() - 1)

    # Exposure-matched random control (vectorized).
    exposure = float((pos > 0).mean())
    k = int(round(exposure * n))
    R = ret.values
    rng = np.random.default_rng(seed)
    if 0 < k < n:
        M = np.zeros((n_random, n))
        for i in range(n_random):
            M[i, rng.choice(n, size=k, replace=False)] = 1.0
        rand_tr = np.prod(1 + M * R, axis=1) - 1.0
    else:
        rand_tr = np.zeros(n_random)
    rand_median = float(np.median(rand_tr))
    rand_p95 = float(np.percentile(rand_tr, 95))
    percentile = float((rand_tr < full_tr).mean())  # share of random the strat beats

    is_sh, oos_sh = is_seg["sharpe"], oos_seg["sharpe"]
    overfit = bool(is_sh > 0.3 and (oos_sh < 0 or oos_sh < 0.4 * is_sh))
    beats_random = bool(percentile >= 0.95)
    notes = []
    if overfit:
        notes.append(f"样本外 Sharpe({oos_sh}) 远低于样本内({is_sh})——疑似过拟合")
    if not beats_random:
        notes.append(f"未明显跑赢同敞口随机组合(仅胜过 {percentile:.0%})——收益可能主要来自市场 beta 而非择时")
    if not notes:
        notes.append("通过:样本外稳健且明显跑赢随机对照")

    return {
        "strategy": strategy,
        "params": params,
        "full_total_return": round(full_tr, 4),
        "in_sample": is_seg,
        "out_of_sample": oos_seg,
        "random_control": {
            "exposure": round(exposure, 3),
            "n": n_random,
            "median_return": round(rand_median, 4),
            "p95_return": round(rand_p95, 4),
            "strategy_return": round(full_tr, 4),
            "percentile": round(percentile, 3),
            "edge_vs_random": round(full_tr - rand_median, 4),
        },
        "verdict": {"overfit": overfit, "beats_random": beats_random, "notes": notes},
    }

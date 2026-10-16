"""EMA + Dual Supertrend — matches TradingView ta.supertrend / ta.ema logic."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # TradingView ATR uses RMA (Wilder)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    factor: float,
    atr_length: int,
) -> tuple[pd.Series, pd.Series]:
    """
    TradingView-compatible Supertrend.
    Returns (supertrend_line, direction) where:
      direction < 0  -> uptrend (green)
      direction > 0  -> downtrend (red)
    """
    atr_vals = atr(high, low, close, atr_length)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + factor * atr_vals
    basic_lower = hl2 - factor * atr_vals

    n = len(close)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    st = np.zeros(n)
    direction = np.zeros(n)

    final_upper[0] = basic_upper.iloc[0]
    final_lower[0] = basic_lower.iloc[0]
    st[0] = final_upper[0]
    direction[0] = 1  # start bearish like many implementations

    for i in range(1, n):
        bu = basic_upper.iloc[i]
        bl = basic_lower.iloc[i]

        if np.isnan(bu) or np.isnan(bl):
            final_upper[i] = final_upper[i - 1]
            final_lower[i] = final_lower[i - 1]
            st[i] = st[i - 1]
            direction[i] = direction[i - 1]
            continue

        # Final upper / lower bands
        if bu < final_upper[i - 1] or close.iloc[i - 1] > final_upper[i - 1]:
            final_upper[i] = bu
        else:
            final_upper[i] = final_upper[i - 1]

        if bl > final_lower[i - 1] or close.iloc[i - 1] < final_lower[i - 1]:
            final_lower[i] = bl
        else:
            final_lower[i] = final_lower[i - 1]

        prev_st = st[i - 1]
        if prev_st == final_upper[i - 1]:
            if close.iloc[i] > final_upper[i]:
                direction[i] = -1
                st[i] = final_lower[i]
            else:
                direction[i] = 1
                st[i] = final_upper[i]
        else:
            if close.iloc[i] < final_lower[i]:
                direction[i] = 1
                st[i] = final_upper[i]
            else:
                direction[i] = -1
                st[i] = final_lower[i]

    return pd.Series(st, index=close.index), pd.Series(direction, index=close.index)


def add_indicators(
    df: pd.DataFrame,
    ema_periods: list[int],
    st1_atr: int,
    st1_factor: float,
    st2_atr: int,
    st2_factor: float,
) -> pd.DataFrame:
    out = df.copy()
    for p in ema_periods:
        out[f"ema_{p}"] = ema(out["Close"], p)

    _, dir1 = supertrend(out["High"], out["Low"], out["Close"], st1_factor, st1_atr)
    _, dir2 = supertrend(out["High"], out["Low"], out["Close"], st2_factor, st2_atr)
    out["st1_dir"] = dir1
    out["st2_dir"] = dir2

    out["both_green"] = (out["st1_dir"] < 0) & (out["st2_dir"] < 0)
    out["both_red"] = (out["st1_dir"] > 0) & (out["st2_dir"] > 0)

    # Fresh flip — same as Pine: bothGreen and not bothGreen[1]
    out["buy_signal"] = out["both_green"] & ~out["both_green"].shift(1).fillna(False)
    out["sell_signal"] = out["both_red"] & ~out["both_red"].shift(1).fillna(False)

    # Above ALL = close > every EMA; below ALL = close < every EMA
    ema_cols = [f"ema_{p}" for p in ema_periods]
    out["above_all_emas"] = out[ema_cols].notna().all(axis=1)
    for col in ema_cols:
        out["above_all_emas"] &= out["Close"] > out[col]

    out["below_all_emas"] = out[ema_cols].notna().all(axis=1)
    for col in ema_cols:
        out["below_all_emas"] &= out["Close"] < out[col]

    out["buy_alert"] = out["buy_signal"] & out["above_all_emas"]
    out["sell_alert"] = out["sell_signal"] & out["below_all_emas"]

    return out

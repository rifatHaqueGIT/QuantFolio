"""
GS-Quant-Inspired Extensions for QuantFolio Engine
====================================================
Standalone implementations inspired by Goldman Sachs' gs-quant library
(https://github.com/goldmansachs/gs-quant).

Modules included:
  1. Volatility Models — EWMA and Garman-Klass volatility estimators
  2. Rolling Sharpe Ratio — day-count-correct rolling Sharpe with excess returns
  3. Basket Backtesting — rebalancing engine with daily/weekly/monthly frequency + transaction costs
  4. Data Smoothing — spike filtering and outlier regime smoothing
  5. Excess Returns — Actual/360 day-count-convention excess return calculation

All functions operate on pandas Series/DataFrames and require no GS Marquee API credentials.
"""

from enum import Enum, IntEnum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VOLATILITY MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class AnnualizationFactor(IntEnum):
    """Trading-day annualization constants from gs-quant econometrics."""
    DAILY = 252
    WEEKLY = 52
    SEMI_MONTHLY = 26
    MONTHLY = 12
    QUARTERLY = 4
    ANNUALLY = 1


def ewma_volatility(
    returns: pd.Series,
    span: int = 60,
    annualize: bool = True,
    trading_days: int = 252
) -> pd.Series:
    """
    Exponentially Weighted Moving Average (EWMA) volatility estimator.

    Inspired by gs-quant's volatility function with exponential weighting.
    Uses the RiskMetrics-style EWMA where recent observations carry
    exponentially more weight than older ones.

    :param returns: daily return series
    :param span: decay span in days (λ = 1 − 2/(span+1)), default 60
    :param annualize: whether to annualize the result (default True)
    :param trading_days: annualization factor (default 252)
    :return: EWMA volatility timeseries

    **Usage**

    EWMA volatility with a 60-day half-life:

    >>> vol = ewma_volatility(daily_returns, span=60)

    The decay factor λ is computed as:

    :math:`\\lambda = 1 - \\frac{2}{\\text{span} + 1}`

    :math:`\\sigma^2_t = \\lambda \\sigma^2_{t-1} + (1 - \\lambda) r^2_t`
    """
    ewma_var = returns.ewm(span=span, adjust=False).var()
    ewma_vol = np.sqrt(ewma_var)
    if annualize:
        ewma_vol *= np.sqrt(trading_days)
    return ewma_vol


def garman_klass_volatility(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    open_: pd.Series,
    window: int = 21,
    annualize: bool = True,
    trading_days: int = 252
) -> pd.Series:
    """
    Garman-Klass volatility estimator using OHLC data.

    More efficient than close-to-close volatility by incorporating
    intraday price range information. Based on the GS-quant approach
    to alternative volatility measures.

    :param high: daily high prices
    :param low: daily low prices
    :param close: daily close prices
    :param open_: daily open prices
    :param window: rolling window size (default 21 ~= 1 month)
    :param annualize: whether to annualize (default True)
    :param trading_days: annualization factor
    :return: Garman-Klass volatility timeseries

    **Usage**

    :math:`\\hat{\\sigma}^2_{GK} = \\frac{1}{2}(\\ln H/L)^2 - (2\\ln 2 - 1)(\\ln C/O)^2`

    >>> gk_vol = garman_klass_volatility(highs, lows, closes, opens)
    """
    log_hl = np.log(high / low)
    log_co = np.log(close / open_)

    # Garman-Klass per-day variance estimate
    gk_daily = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2

    # Rolling average of daily GK variance estimates
    gk_var = gk_daily.rolling(window=window, min_periods=max(1, window // 2)).mean()
    gk_vol = np.sqrt(gk_var.clip(lower=0))

    if annualize:
        gk_vol *= np.sqrt(trading_days)

    return gk_vol


def rolling_std_volatility(
    returns: pd.Series,
    window: int = 21,
    annualize: bool = True,
    trading_days: int = 252
) -> pd.Series:
    """
    Standard rolling window volatility (for comparison baseline).

    :param returns: daily return series
    :param window: rolling window in trading days
    :param annualize: whether to annualize
    :param trading_days: annualization factor
    :return: rolling standard deviation volatility
    """
    vol = returns.rolling(window=window, min_periods=max(1, window // 2)).std()
    if annualize:
        vol *= np.sqrt(trading_days)
    return vol


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EXCESS RETURNS — Day-Count-Correct (Actual/360)
# ═══════════════════════════════════════════════════════════════════════════════


class DayCountConvention(Enum):
    """Day count conventions from gs-quant datetime module."""
    ACTUAL_360 = "actual_360"
    ACTUAL_365 = "actual_365"
    THIRTY_360 = "30_360"


def day_count_fraction(
    d1: pd.Timestamp,
    d2: pd.Timestamp,
    convention: DayCountConvention = DayCountConvention.ACTUAL_360
) -> float:
    """
    Compute the year fraction between two dates under a given convention.

    Follows gs-quant's day_count_fraction from datetime module.

    :param d1: start date
    :param d2: end date
    :param convention: day count convention
    :return: year fraction
    """
    delta_days = (d2 - d1).days
    if convention == DayCountConvention.ACTUAL_360:
        return delta_days / 360.0
    elif convention == DayCountConvention.ACTUAL_365:
        return delta_days / 365.0
    elif convention == DayCountConvention.THIRTY_360:
        return ((d2.year - d1.year) * 360 + (d2.month - d1.month) * 30 + (d2.day - d1.day)) / 360.0
    return delta_days / 365.0


def excess_returns(
    price_series: pd.Series,
    risk_free_rate: float = 0.035,
    day_count_convention: DayCountConvention = DayCountConvention.ACTUAL_360
) -> pd.Series:
    """
    Calculate excess returns over a risk-free rate using proper day-count conventions.

    Directly inspired by gs-quant's `excess_returns()` from `econometrics.py`.

    :param price_series: price series (indexed by datetime)
    :param risk_free_rate: annualized risk-free rate (default 3.5%)
    :param day_count_convention: day count convention (default Actual/360)
    :return: excess return level series (starts at first price value)

    **Usage**

    Given a price series P and risk-free rate R:

    :math:`E_t = E_{t-1} + P_t - P_{t-1} \\cdot (1 + R \\cdot \\Delta t)`

    where :math:`\\Delta t` is the day count fraction.

    >>> er = excess_returns(prices, risk_free_rate=0.05)
    """
    er = [price_series.iloc[0]]
    for j in range(1, len(price_series)):
        fraction = day_count_fraction(
            price_series.index[j - 1],
            price_series.index[j],
            day_count_convention
        )
        er.append(
            er[-1] + price_series.iloc[j] - price_series.iloc[j - 1] * (1 + risk_free_rate * fraction)
        )
    return pd.Series(er, index=price_series.index, dtype=float)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ROLLING SHARPE RATIO
# ═══════════════════════════════════════════════════════════════════════════════


def rolling_sharpe_ratio(
    price_series: pd.Series,
    risk_free_rate: float = 0.035,
    window: int = 63,
    day_count_convention: DayCountConvention = DayCountConvention.ACTUAL_360
) -> pd.Series:
    """
    Calculate rolling Sharpe ratio with day-count-correct excess returns.

    Inspired by gs-quant's `sharpe_ratio()` from `econometrics.py`.
    Computes annualized return / annualized volatility of excess returns
    over a rolling window.

    :param price_series: price series (datetime-indexed)
    :param risk_free_rate: annualized risk-free rate
    :param window: rolling window in trading days (default 63 ≈ 3 months)
    :param day_count_convention: day count convention
    :return: rolling Sharpe ratio timeseries

    **Usage**

    :math:`S_t = \\frac{(E_t / E_{t-w})^{252/(D_t - D_{t-w})} - 1}{\\text{vol}(E, w)_t}`

    >>> sr = rolling_sharpe_ratio(prices, window=63)
    """
    er = excess_returns(price_series, risk_free_rate, day_count_convention)

    sharpe_values = pd.Series(np.nan, index=er.index, dtype=float)

    for i in range(window, len(er)):
        er_window = er.iloc[i - window:i + 1]
        start_val = er_window.iloc[0]
        end_val = er_window.iloc[-1]

        if start_val <= 0 or end_val <= 0:
            continue

        # Calendar days in the window
        days_elapsed = (er_window.index[-1] - er_window.index[0]).days
        if days_elapsed <= 0:
            continue

        # Annualized return of excess return series
        ann_return = (end_val / start_val) ** (365.25 / days_elapsed) - 1

        # Annualized volatility of excess returns
        er_pct_returns = er_window.pct_change().dropna()
        if len(er_pct_returns) < 2:
            continue
        ann_vol = er_pct_returns.std() * np.sqrt(252)

        if ann_vol > 1e-10:
            sharpe_values.iloc[i] = ann_return / ann_vol

    return sharpe_values


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BASKET BACKTESTING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class RebalFreq(Enum):
    """Rebalancing frequency from gs-quant backtesting module."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def backtest_basket(
    series: List[pd.Series],
    weights: List[float],
    costs: Optional[List[float]] = None,
    rebal_freq: RebalFreq = RebalFreq.MONTHLY,
    initial_value: float = 100.0
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Backtest a weighted basket of assets with periodic rebalancing and transaction costs.

    Directly adapted from gs-quant's `backtest_basket()` in `backtesting.py`.

    :param series: list of price series for each asset (datetime-indexed)
    :param weights: target allocation weights (must sum to ~1.0)
    :param costs: transaction cost per asset as fraction (e.g., 0.001 = 10 bps), defaults to 0
    :param rebal_freq: rebalancing frequency — DAILY, WEEKLY, or MONTHLY
    :param initial_value: starting basket value (default 100)
    :return: tuple of (basket_value_series, actual_weights_dataframe)

    **Usage**

    Backtest a 60/40 portfolio with monthly rebalancing and 10 bps costs:

    >>> basket, weights_df = backtest_basket(
    ...     [spy_prices, agg_prices],
    ...     weights=[0.6, 0.4],
    ...     costs=[0.001, 0.001],
    ...     rebal_freq=RebalFreq.MONTHLY
    ... )
    """
    num_assets = len(series)
    costs = costs or [0.0] * num_assets
    weights_arr = np.array(weights, dtype=float)

    if len(weights) != num_assets or len(costs) != num_assets:
        raise ValueError("series, weights, and costs lists must have the same length")

    if not all(isinstance(s, pd.Series) for s in series):
        raise TypeError("expected a list of pandas Series")

    # Get the intersection of all calendars
    common_index = series[0].index
    for s in series[1:]:
        common_index = common_index.intersection(s.index)
    common_index = common_index.sort_values()

    if len(common_index) < 2:
        raise ValueError("insufficient overlapping dates across input series")

    # Reindex all series to common calendar
    price_matrix = np.column_stack([s.reindex(common_index).values for s in series])
    cost_arr = np.array(costs, dtype=float)

    n = len(common_index)

    # Determine rebalancing dates
    if rebal_freq == RebalFreq.DAILY:
        rebal_dates = set(range(n))
    elif rebal_freq == RebalFreq.WEEKLY:
        rebal_dates = {0}
        last_rebal = common_index[0]
        for i, dt in enumerate(common_index):
            if (dt - last_rebal).days >= 7:
                rebal_dates.add(i)
                last_rebal = dt
    else:  # MONTHLY
        rebal_dates = {0}
        last_month = common_index[0].month
        for i, dt in enumerate(common_index):
            if dt.month != last_month:
                rebal_dates.add(i)
                last_month = dt.month

    # Run backtest
    output = np.zeros(n)
    units = np.zeros((n, num_assets))
    actual_weights = np.zeros((n, num_assets))

    # Initialize
    output[0] = initial_value
    units[0] = output[0] * weights_arr / price_matrix[0]
    actual_weights[0] = weights_arr

    prev_rebal = 0
    for i in range(1, n):
        # Update portfolio value: P&L from unit holdings
        output[i] = output[i - 1] + np.dot(units[i - 1], price_matrix[i] - price_matrix[i - 1])

        # Track drift in weights since last rebalance
        if output[i] > 0 and output[prev_rebal] > 0:
            actual_weights[i] = (
                weights_arr
                * (price_matrix[i] / price_matrix[prev_rebal])
                * (output[prev_rebal] / output[i])
            )
        else:
            actual_weights[i] = actual_weights[i - 1]

        # Rebalance if needed
        if i in rebal_dates:
            # Deduct transaction costs proportional to weight changes
            turnover = np.abs(weights_arr - actual_weights[i])
            output[i] -= np.dot(cost_arr, turnover) * output[i]

            # Rebalance to target weights
            units[i] = output[i] * weights_arr / price_matrix[i]
            actual_weights[i] = weights_arr
            prev_rebal = i
        else:
            units[i] = units[i - 1]

    basket_series = pd.Series(output, index=common_index, dtype=float)
    weights_df = pd.DataFrame(actual_weights, index=common_index,
                              columns=[f"asset_{i}" for i in range(num_assets)])
    return basket_series, weights_df


def backtest_portfolio(
    price_df: pd.DataFrame,
    weights: List[float],
    costs: Optional[List[float]] = None,
    rebal_freq: RebalFreq = RebalFreq.MONTHLY,
    initial_value: float = 10000.0
) -> Dict:
    """
    High-level portfolio backtesting wrapper for the API layer.

    Runs basket backtest and computes summary performance metrics.

    :param price_df: DataFrame of asset prices (columns = tickers)
    :param weights: target allocation weights
    :param costs: transaction costs per asset
    :param rebal_freq: rebalancing frequency
    :param initial_value: starting portfolio value
    :return: dict with basket values, metrics, and actual weight drift
    """
    tickers = list(price_df.columns)
    series_list = [price_df[t].dropna() for t in tickers]

    basket_values, weights_df = backtest_basket(
        series=series_list,
        weights=weights,
        costs=costs,
        rebal_freq=rebal_freq,
        initial_value=initial_value
    )

    # Compute backtest metrics
    returns = basket_values.pct_change().dropna()
    total_return = (basket_values.iloc[-1] / basket_values.iloc[0]) - 1
    days_elapsed = (basket_values.index[-1] - basket_values.index[0]).days
    ann_return = (1 + total_return) ** (365.25 / max(days_elapsed, 1)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 1e-10 else 0.0

    # Max drawdown
    running_max = basket_values.cummax()
    drawdown = (running_max - basket_values) / running_max
    max_dd = float(drawdown.max())

    # Calmar ratio
    calmar = ann_return / max_dd if max_dd > 1e-10 else 0.0

    return {
        "tickers": tickers,
        "rebal_frequency": rebal_freq.value,
        "initial_value": initial_value,
        "final_value": float(basket_values.iloc[-1]),
        "total_return": float(total_return),
        "annualized_return": float(ann_return),
        "annualized_volatility": float(ann_vol),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": max_dd,
        "calmar_ratio": float(calmar),
        "basket_values": [float(v) for v in basket_values.values],
        "basket_dates": [d.isoformat() for d in basket_values.index],
        "weight_drift": {
            "dates": [d.isoformat() for d in weights_df.index],
            "weights": {
                tickers[i]: [float(w) for w in weights_df.iloc[:, i].values]
                for i in range(len(tickers))
            }
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DATA SMOOTHING — Spike & Outlier Filtering
# ═══════════════════════════════════════════════════════════════════════════════


class ThresholdType(Enum):
    """Threshold modes from gs-quant's analysis.py."""
    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"


def smooth_spikes(
    x: pd.Series,
    threshold: float = 0.5,
    threshold_type: ThresholdType = ThresholdType.PERCENTAGE
) -> pd.Series:
    """
    Smooth out point spikes in a timeseries.

    Directly from gs-quant's `smooth_spikes()` in `analysis.py`.
    If a point deviates from both neighbors by more than the threshold,
    it is replaced with the average of its neighbors.

    :param x: price/value timeseries
    :param threshold: deviation threshold (0.5 = 50% for percentage mode)
    :param threshold_type: PERCENTAGE or ABSOLUTE
    :return: smoothed timeseries (first and last points are dropped)

    **Usage**

    Remove price spikes exceeding 50% relative to neighbors:

    >>> clean_prices = smooth_spikes(raw_prices, threshold=0.5)
    """
    if len(x) < 3:
        return pd.Series(dtype=float)

    def check_percentage(prev, curr, nxt, mult):
        higher = curr > prev * mult and curr > nxt * mult
        lower = prev > curr * mult and nxt > curr * mult
        return higher or lower

    def check_absolute(prev, curr, nxt, abs_val):
        higher = curr > prev + abs_val and curr > nxt + abs_val
        lower = prev > curr + abs_val and nxt > curr + abs_val
        return higher or lower

    threshold_value = threshold if threshold_type == ThresholdType.ABSOLUTE else (1 + threshold)
    check_fn = check_absolute if threshold_type == ThresholdType.ABSOLUTE else check_percentage

    result = x.astype(float).copy()
    current, nxt = x.iloc[0], x.iloc[1]

    for i in range(1, len(x) - 1):
        prev = current
        current = nxt
        nxt = x.iloc[i + 1]

        if check_fn(prev, current, nxt, threshold_value):
            result.iloc[i] = (prev + nxt) / 2

    return result.iloc[1:-1]


def smooth_outliers(
    x: pd.Series,
    threshold: float = 0.5,
    rolling_window: Optional[int] = None
) -> pd.Series:
    """
    Smooth out prolonged anomalous regimes in a timeseries.

    Inspired by gs-quant's `smooth_outliers()` in `analysis.py`.
    Unlike smooth_spikes, this handles multi-day dips/spikes by comparing
    to a rolling median and linearly interpolating flagged regions.

    :param x: price/value timeseries
    :param threshold: fractional deviation from rolling median to flag as anomalous
                      (0.5 = 50%, default)
    :param rolling_window: rolling median window size (defaults to len(x)//4, min 10)
    :return: timeseries with anomalous regimes replaced by linear interpolation

    **Usage**

    Smooth anomalous dips that deviate >50% from local trend:

    >>> clean = smooth_outliers(raw_prices, threshold=0.5)
    """
    if len(x) < 3:
        return x.copy()

    if threshold <= 0:
        raise ValueError("threshold must be positive")

    values = x.astype(float).copy()

    # Rolling median window
    win = rolling_window or max(10, len(x) // 4)
    rolling_median = values.rolling(window=win, center=True, min_periods=max(1, win // 4)).median()

    # Backfill/forward-fill edges
    rolling_median = rolling_median.bfill().ffill()

    # Flag outliers: points deviating > threshold from the rolling median
    deviation = np.abs(values - rolling_median) / rolling_median.clip(lower=1e-10)
    is_outlier = deviation > threshold

    if not is_outlier.any():
        return values

    # Replace outlier regions with linear interpolation
    result = values.copy()
    result[is_outlier] = np.nan
    result = result.interpolate(method="linear")

    # If edges are NaN (outlier at boundary), forward/backward fill
    result = result.bfill().ffill()

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PORTFOLIO-LEVEL ANALYTICS AGGREGATION
# ═══════════════════════════════════════════════════════════════════════════════


def compute_gs_quant_analytics(
    price_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    weights: List[float],
    risk_free_rate: float = 0.035,
    trading_days: int = 252
) -> Dict:
    """
    Compute the full suite of gs-quant-inspired analytics for a portfolio.

    This is the main aggregation function that produces all extension metrics
    for the API response.

    :param price_df: historical price DataFrame (columns = tickers)
    :param returns_df: daily returns DataFrame
    :param weights: portfolio allocation weights
    :param risk_free_rate: annualized risk-free rate
    :param trading_days: annualization factor
    :return: dict with all extension analytics
    """
    tickers = list(returns_df.columns)
    weights_arr = np.array(weights, dtype=float)
    if not np.isclose(weights_arr.sum(), 1.0, atol=1e-4):
        weights_arr = weights_arr / weights_arr.sum()

    # Portfolio-level return series
    port_returns = (returns_df * weights_arr).sum(axis=1)
    port_prices = (1 + port_returns).cumprod()
    port_prices = port_prices * 100  # Normalize to base 100

    # 1. Volatility Models
    vol_std = rolling_std_volatility(port_returns, window=21, trading_days=trading_days)
    vol_ewma = ewma_volatility(port_returns, span=60, trading_days=trading_days)

    # 2. Rolling Sharpe
    rolling_sr = rolling_sharpe_ratio(port_prices, risk_free_rate=risk_free_rate, window=63)

    # 3. Excess Returns
    er = excess_returns(port_prices, risk_free_rate=risk_free_rate)

    # Per-asset volatility comparison
    asset_vols = {}
    for ticker in tickers:
        asset_vols[ticker] = {
            "std_21d": float(rolling_std_volatility(
                returns_df[ticker], window=21, trading_days=trading_days
            ).iloc[-1]) if len(returns_df[ticker]) >= 21 else None,
            "ewma_60d": float(ewma_volatility(
                returns_df[ticker], span=60, trading_days=trading_days
            ).iloc[-1]) if len(returns_df[ticker]) >= 10 else None,
        }

    # Latest values for quick display
    latest_std_vol = float(vol_std.iloc[-1]) if not vol_std.empty else None
    latest_ewma_vol = float(vol_ewma.iloc[-1]) if not vol_ewma.empty else None
    latest_rolling_sr = None
    valid_sr = rolling_sr.dropna()
    if not valid_sr.empty:
        latest_rolling_sr = float(valid_sr.iloc[-1])

    return {
        "volatility_models": {
            "portfolio_std_21d": latest_std_vol,
            "portfolio_ewma_60d": latest_ewma_vol,
            "std_timeseries": {
                "dates": [d.isoformat() for d in vol_std.dropna().index],
                "values": [float(v) for v in vol_std.dropna().values]
            },
            "ewma_timeseries": {
                "dates": [d.isoformat() for d in vol_ewma.dropna().index],
                "values": [float(v) for v in vol_ewma.dropna().values]
            },
            "asset_volatilities": asset_vols
        },
        "rolling_sharpe": {
            "current": latest_rolling_sr,
            "window_days": 63,
            "timeseries": {
                "dates": [d.isoformat() for d in valid_sr.index],
                "values": [float(v) for v in valid_sr.values]
            }
        },
        "excess_returns": {
            "dates": [d.isoformat() for d in er.index],
            "values": [float(v) for v in er.values],
            "day_count_convention": "Actual/360"
        }
    }

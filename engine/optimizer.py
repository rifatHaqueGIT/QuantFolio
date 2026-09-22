"""
Portfolio Optimization Engine
Implements Markowitz Modern Portfolio Theory (Mean-Variance Optimization),
Efficient Frontier calculation, Maximum Sharpe Ratio portfolio, Minimum Volatility portfolio,
and comparison against Equal-Weight ($1/N$) and User-Specified weights.
"""

from typing import Dict, List
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def portfolio_performance(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.035
) -> (float, float, float):
    """
    Calculate annualized portfolio return, annualized volatility, and Sharpe ratio.
    """
    port_return = np.sum(mean_returns * weights)
    port_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
    port_volatility = np.sqrt(max(port_variance, 1e-8))
    sharpe_ratio = (port_return - risk_free_rate) / port_volatility
    return port_return, port_volatility, sharpe_ratio


def optimize_max_sharpe(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.035
) -> Dict:
    """
    Find portfolio weights that maximize the Sharpe ratio (minimize negative Sharpe).
    """
    num_assets = len(mean_returns)
    init_guess = np.ones(num_assets) / num_assets
    bounds = tuple((0.0, 1.0) for _ in range(num_assets))
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})

    def neg_sharpe(w):
        _, _, s = portfolio_performance(w, mean_returns, cov_matrix, risk_free_rate)
        return -s

    result = minimize(
        neg_sharpe,
        init_guess,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    optimal_weights = result.x
    opt_ret, opt_vol, opt_sharpe = portfolio_performance(optimal_weights, mean_returns, cov_matrix, risk_free_rate)

    return {
        "weights": [float(round(w, 4)) for w in optimal_weights],
        "expected_return": float(opt_ret),
        "volatility": float(opt_vol),
        "sharpe_ratio": float(opt_sharpe)
    }


def optimize_min_volatility(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.035
) -> Dict:
    """
    Find portfolio weights that minimize volatility (Minimum Variance Portfolio).
    """
    num_assets = len(mean_returns)
    init_guess = np.ones(num_assets) / num_assets
    bounds = tuple((0.0, 1.0) for _ in range(num_assets))
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})

    def port_vol(w):
        _, v, _ = portfolio_performance(w, mean_returns, cov_matrix, risk_free_rate)
        return v

    result = minimize(
        port_vol,
        init_guess,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    optimal_weights = result.x
    opt_ret, opt_vol, opt_sharpe = portfolio_performance(optimal_weights, mean_returns, cov_matrix, risk_free_rate)

    return {
        "weights": [float(round(w, 4)) for w in optimal_weights],
        "expected_return": float(opt_ret),
        "volatility": float(opt_vol),
        "sharpe_ratio": float(opt_sharpe)
    }


def calculate_efficient_frontier(
    returns_df: pd.DataFrame,
    actual_weights: List[float],
    trading_days: int = 252,
    risk_free_rate: float = 0.035,
    num_frontier_points: int = 35,
    num_random_portfolios: int = 800
) -> Dict:
    """
    Calculate the Efficient Frontier curve, random sampled portfolio points,
    and performance metrics for Actual, Equal Weight, Min Volatility, and Max Sharpe portfolios.
    """
    tickers = list(returns_df.columns)
    num_assets = len(tickers)

    # Annualized mean returns and covariance
    mean_daily = returns_df.mean()
    mean_returns_annual = ((1 + mean_daily) ** trading_days - 1).values
    cov_matrix_annual = (returns_df.cov() * trading_days).values

    # 1. Benchmark portfolios
    # Actual
    actual_w = np.array(actual_weights, dtype=float)
    if not np.isclose(actual_w.sum(), 1.0, atol=1e-4):
        actual_w = actual_w / actual_w.sum()
    act_ret, act_vol, act_sharpe = portfolio_performance(actual_w, mean_returns_annual, cov_matrix_annual, risk_free_rate)
    actual_portfolio = {
        "name": "Your Portfolio",
        "weights": [float(round(w, 4)) for w in actual_w],
        "expected_return": float(act_ret),
        "volatility": float(act_vol),
        "sharpe_ratio": float(act_sharpe)
    }

    # Equal weight (1/N)
    eq_w = np.ones(num_assets) / num_assets
    eq_ret, eq_vol, eq_sharpe = portfolio_performance(eq_w, mean_returns_annual, cov_matrix_annual, risk_free_rate)
    equal_weight_portfolio = {
        "name": "Equal Weight (1/N)",
        "weights": [float(round(w, 4)) for w in eq_w],
        "expected_return": float(eq_ret),
        "volatility": float(eq_vol),
        "sharpe_ratio": float(eq_sharpe)
    }

    # Max Sharpe
    max_sharpe_portfolio = optimize_max_sharpe(mean_returns_annual, cov_matrix_annual, risk_free_rate)
    max_sharpe_portfolio["name"] = "Max Sharpe (Tangency)"

    # Min Volatility
    min_vol_portfolio = optimize_min_volatility(mean_returns_annual, cov_matrix_annual, risk_free_rate)
    min_vol_portfolio["name"] = "Minimum Volatility"

    # 2. Efficient Frontier points
    min_ret = min_vol_portfolio["expected_return"]
    max_ret = max(max(mean_returns_annual), max_sharpe_portfolio["expected_return"] * 1.1)

    target_returns = np.linspace(min_ret, max_ret, num_frontier_points)
    frontier_volatilities = []
    frontier_returns = []

    bounds = tuple((0.0, 1.0) for _ in range(num_assets))
    init_guess = np.ones(num_assets) / num_assets

    for target_r in target_returns:
        constraints = (
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
            {'type': 'eq', 'fun': lambda w, tr=target_r: np.sum(w * mean_returns_annual) - tr}
        )
        res = minimize(
            lambda w: np.sqrt(np.dot(w.T, np.dot(cov_matrix_annual, w))),
            init_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        if res.success:
            frontier_volatilities.append(float(res.fun))
            frontier_returns.append(float(target_r))

    # 3. Random portfolio simulation cloud for visualization
    np.random.seed(101)
    random_vols = []
    random_rets = []
    random_sharpes = []

    for _ in range(num_random_portfolios):
        w = np.random.random(num_assets)
        w /= np.sum(w)
        r, v, s = portfolio_performance(w, mean_returns_annual, cov_matrix_annual, risk_free_rate)
        random_vols.append(float(round(v, 4)))
        random_rets.append(float(round(r, 4)))
        random_sharpes.append(float(round(s, 3)))

    return {
        "tickers": tickers,
        "actual": actual_portfolio,
        "equal_weight": equal_weight_portfolio,
        "max_sharpe": max_sharpe_portfolio,
        "min_volatility": min_vol_portfolio,
        "frontier": {
            "volatilities": frontier_volatilities,
            "returns": frontier_returns
        },
        "random_portfolios": {
            "volatilities": random_vols,
            "returns": random_rets,
            "sharpe_ratios": random_sharpes
        }
    }

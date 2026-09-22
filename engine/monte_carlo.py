"""
Monte Carlo Simulation Engine
Simulates multi-asset correlated price trajectories using Geometric Brownian Motion (GBM)
and Cholesky decomposition of the empirical covariance matrix.
Computes Value at Risk (VaR), Conditional VaR (CVaR / Expected Shortfall), and Drawdown distributions.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


def safe_cholesky(matrix: np.ndarray, jitter: float = 1e-7) -> np.ndarray:
    """
    Perform Cholesky decomposition with automatic diagonal regularization
    if matrix is not strictly positive definite due to numerical precision.
    """
    try:
        return np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError:
        # Regularize by adding small ridge to diagonal
        diag_ridge = np.eye(matrix.shape[0]) * jitter
        try:
            return np.linalg.cholesky(matrix + diag_ridge)
        except np.linalg.LinAlgError:
            # Fallback to eigenvalue reconstruction (nearest PSD matrix)
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            eigenvalues = np.maximum(eigenvalues, 1e-8)
            reconstructed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
            return np.linalg.cholesky(reconstructed)


def run_monte_carlo_simulation(
    price_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    weights: List[float],
    initial_investment: float = 10000.0,
    time_horizon_days: int = 252,
    num_simulations: int = 5000,
    seed: Optional[int] = 42
) -> Dict:
    """
    Run correlated Monte Carlo simulation for a multi-asset portfolio.

    Parameters:
        price_df: Historical daily price DataFrame
        returns_df: Historical daily returns DataFrame
        weights: Allocation weight for each asset
        initial_investment: Starting portfolio value in dollars
        time_horizon_days: Number of trading days to simulate into the future
        num_simulations: Number of Monte Carlo iterations (e.g. 5,000 - 10,000)
        seed: Random seed for reproducibility
    """
    if seed is not None:
        np.random.seed(seed)

    weights = np.array(weights, dtype=float)
    if not np.isclose(weights.sum(), 1.0, atol=1e-4):
        weights = weights / weights.sum()

    tickers = list(returns_df.columns)
    num_assets = len(tickers)

    # Daily drift and volatility
    # Use log returns for continuous-time Geometric Brownian Motion
    log_returns = np.log(1 + returns_df)
    mu = log_returns.mean().values  # Daily mean drift: shape (num_assets,)
    cov_matrix = log_returns.cov().values  # Daily covariance: shape (num_assets, num_assets)
    sigma = np.sqrt(np.diag(cov_matrix))  # Daily standard deviations

    # Cholesky factor L such that L @ L.T = cov_matrix
    L = safe_cholesky(cov_matrix)

    # Pre-allocate portfolio trajectories: shape (num_simulations, time_horizon_days + 1)
    # Day 0 is initial investment
    # Initial asset allocation in dollars
    initial_asset_values = initial_investment * weights

    # Asset trajectories: shape (num_simulations, time_horizon_days + 1, num_assets)
    # Drift term for each asset: (mu - 0.5 * sigma^2)
    drift = mu - 0.5 * (sigma ** 2)

    # Generate random shocks: Z ~ N(0, 1) shape (num_simulations, time_horizon_days, num_assets)
    # Correlated shocks: epsilon = Z @ L.T
    raw_shocks = np.random.normal(size=(num_simulations, time_horizon_days, num_assets))
    correlated_shocks = np.einsum('ijk,lk->ijl', raw_shocks, L)

    # Daily simulated log returns: drift + correlated_shocks
    sim_log_returns = drift + correlated_shocks
    sim_cumulative_returns = np.cumsum(sim_log_returns, axis=1)

    # Add day 0 (zeros) to cumulative returns
    day_zero = np.zeros((num_simulations, 1, num_assets))
    sim_cumulative_returns = np.concatenate([day_zero, sim_cumulative_returns], axis=1)

    # Calculate asset price multiplier exp(cumulative_log_returns)
    asset_multipliers = np.exp(sim_cumulative_returns)

    # Portfolio value over time for each simulation:
    # Portfolio_Value(t) = sum_i [ initial_asset_value_i * multiplier_i(t) ]
    # Shape: (num_simulations, time_horizon_days + 1)
    portfolio_paths = np.sum(asset_multipliers * initial_asset_values, axis=2)

    # Terminal values at day T
    terminal_values = portfolio_paths[:, -1]
    terminal_pnl = terminal_values - initial_investment
    terminal_pct_returns = terminal_pnl / initial_investment

    # Trajectory Percentiles over time for visualization
    percentiles_to_calc = [5, 10, 25, 50, 75, 90, 95]
    trajectory_percentiles = {}
    for p in percentiles_to_calc:
        trajectory_percentiles[f"p{p}"] = np.percentile(portfolio_paths, p, axis=0).tolist()

    # Select 20 sample paths for rendering
    sample_indices = np.random.choice(num_simulations, size=min(20, num_simulations), replace=False)
    sample_paths = portfolio_paths[sample_indices].tolist()

    # Risk Metrics Calculation
    # 1. Value at Risk (VaR): Dollar and % loss at confidence level
    # 95% VaR is the 5th percentile of return distribution
    var_95_pct = float(-np.percentile(terminal_pct_returns, 5))
    var_95_dollar = float(initial_investment * max(var_95_pct, 0.0))

    var_99_pct = float(-np.percentile(terminal_pct_returns, 1))
    var_99_dollar = float(initial_investment * max(var_99_pct, 0.0))

    # 2. Conditional Value at Risk (CVaR / Expected Shortfall)
    # Expected loss given that loss exceeds VaR threshold
    tail_losses_95 = terminal_pct_returns[terminal_pct_returns <= -var_95_pct]
    cvar_95_pct = float(-tail_losses_95.mean()) if len(tail_losses_95) > 0 else var_95_pct
    cvar_95_dollar = float(initial_investment * max(cvar_95_pct, 0.0))

    tail_losses_99 = terminal_pct_returns[terminal_pct_returns <= -var_99_pct]
    cvar_99_pct = float(-tail_losses_99.mean()) if len(tail_losses_99) > 0 else var_99_pct
    cvar_99_dollar = float(initial_investment * max(cvar_99_pct, 0.0))

    # 3. Probability of Loss
    prob_loss = float(np.mean(terminal_pnl < 0))

    # 4. Maximum Drawdown Distribution
    # Peak-to-trough decline along each path
    running_max = np.maximum.accumulate(portfolio_paths, axis=1)
    drawdowns = (running_max - portfolio_paths) / running_max
    max_drawdowns = np.max(drawdowns, axis=1)
    median_mdd = float(np.median(max_drawdowns))
    mdd_95th = float(np.percentile(max_drawdowns, 95))

    # 5. Terminal Wealth Distribution Histogram bins
    hist_counts, bin_edges = np.histogram(terminal_values, bins=40)
    histogram_data = {
        "counts": hist_counts.tolist(),
        "bin_edges": [float(b) for b in bin_edges],
        "bin_centers": [float(0.5 * (bin_edges[i] + bin_edges[i+1])) for i in range(len(hist_counts))]
    }

    return {
        "initial_investment": initial_investment,
        "time_horizon_days": time_horizon_days,
        "num_simulations": num_simulations,
        "metrics": {
            "expected_terminal_value": float(np.mean(terminal_values)),
            "median_terminal_value": float(np.median(terminal_values)),
            "std_terminal_value": float(np.std(terminal_values)),
            "min_terminal_value": float(np.min(terminal_values)),
            "max_terminal_value": float(np.max(terminal_values)),
            "expected_return_pct": float(np.mean(terminal_pct_returns)),
            "median_return_pct": float(np.median(terminal_pct_returns)),
            "prob_loss": prob_loss,
            "var_95_pct": var_95_pct,
            "var_95_dollar": var_95_dollar,
            "cvar_95_pct": cvar_95_pct,
            "cvar_95_dollar": cvar_95_dollar,
            "var_99_pct": var_99_pct,
            "var_99_dollar": var_99_dollar,
            "cvar_99_pct": cvar_99_pct,
            "cvar_99_dollar": cvar_99_dollar,
            "median_max_drawdown": median_mdd,
            "worst_case_drawdown_95": mdd_95th,
        },
        "trajectory_percentiles": trajectory_percentiles,
        "sample_paths": sample_paths,
        "histogram": histogram_data
    }

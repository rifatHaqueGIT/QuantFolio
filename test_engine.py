"""
Unit and Integration Tests for Portfolio Risk Simulation Engine
"""

import sys
import numpy as np
import pandas as pd
from engine.data_loader import fetch_historical_data, compute_portfolio_statistics
from engine.monte_carlo import safe_cholesky, run_monte_carlo_simulation
from engine.optimizer import calculate_efficient_frontier


def test_cholesky_regularization():
    print("Testing safe_cholesky with singular/non-PSD matrix...")
    # Perfectly correlated 2x2 matrix (singular)
    singular_mat = np.array([[1.0, 1.0], [1.0, 1.0]])
    L = safe_cholesky(singular_mat)
    assert L.shape == (2, 2)
    assert not np.isnan(L).any()
    print("  [OK] Safe Cholesky handles singular matrices successfully.")


def test_full_pipeline_mock():
    print("Testing pipeline with simulated synthetic asset returns...")
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=252, freq="B")
    tickers = ["ASSET_A", "ASSET_B", "ASSET_C"]
    
    # 3 assets with known correlation
    ret_a = np.random.normal(0.0005, 0.015, len(dates))
    ret_b = 0.5 * ret_a + np.random.normal(0.0003, 0.010, len(dates))
    ret_c = np.random.normal(0.0002, 0.008, len(dates))

    returns_df = pd.DataFrame({"ASSET_A": ret_a, "ASSET_B": ret_b, "ASSET_C": ret_c}, index=dates)
    price_df = (1 + returns_df).cumprod() * 100

    weights = [0.4, 0.4, 0.2]

    # 1. Compute stats
    stats = compute_portfolio_statistics(returns_df, weights)
    assert len(stats["asset_stats"]) == 3
    assert "portfolio_expected_return" in stats
    assert "correlation_matrix" in stats
    print(f"  [OK] Portfolio Annual Return: {stats['portfolio_expected_return']:.2%}, Volatility: {stats['portfolio_volatility']:.2%}")

    # 2. Monte Carlo Simulation
    mc_result = run_monte_carlo_simulation(
        price_df=price_df,
        returns_df=returns_df,
        weights=weights,
        initial_investment=10000,
        time_horizon_days=252,
        num_simulations=1000
    )
    metrics = mc_result["metrics"]
    print(f"  [OK] Monte Carlo Ran 1,000 paths:")
    print(f"    Expected Terminal Value: ${metrics['expected_terminal_value']:,.2f}")
    print(f"    95% VaR: {metrics['var_95_pct']:.2%} (${metrics['var_95_dollar']:,.2f})")
    print(f"    95% CVaR: {metrics['cvar_95_pct']:.2%} (${metrics['cvar_95_dollar']:,.2f})")
    print(f"    Prob of Loss: {metrics['prob_loss']:.1%}")
    assert metrics["var_95_pct"] <= metrics["cvar_95_pct"] or np.isclose(metrics["var_95_pct"], metrics["cvar_95_pct"], atol=1e-3)
    assert len(mc_result["trajectory_percentiles"]["p50"]) == 253

    # 3. Optimization & Efficient Frontier
    frontier_res = calculate_efficient_frontier(
        returns_df=returns_df,
        actual_weights=weights,
        num_frontier_points=10,
        num_random_portfolios=100
    )
    assert "max_sharpe" in frontier_res
    assert "min_volatility" in frontier_res
    assert len(frontier_res["frontier"]["returns"]) > 0
    print(f"  [OK] Max Sharpe Portfolio: Return={frontier_res['max_sharpe']['expected_return']:.2%}, Sharpe={frontier_res['max_sharpe']['sharpe_ratio']:.2f}")
    print(f"  [OK] Min Volatility Portfolio: Vol={frontier_res['min_volatility']['volatility']:.2%}")


def test_yfinance_integration():
    print("Testing live yfinance fetch with sample portfolio (SPY, AAPL)...")
    price_df, returns_df, valid_tickers = fetch_historical_data(["SPY", "AAPL"], period="6mo")
    assert "SPY" in valid_tickers
    assert "AAPL" in valid_tickers
    assert len(returns_df) > 50
    print(f"  [OK] Successfully fetched {len(returns_df)} historical trading days for {valid_tickers}")


def test_wealthsimple_parser():
    print("Testing Wealthsimple CSV ingestion and ticker normalization...")
    from engine.data_loader import parse_wealthsimple_csv

    sample_csv = """Account Name,Account Type,Account Classification,Account Number,Symbol,Exchange,MIC,Name,Security Type,Quantity,Position Direction,Market Price,Market Price Currency,Book Value (CAD),Book Value Currency (CAD),Book Value (Market),Book Value Currency (Market),Market Value,Market Value Currency,Market Unrealized Returns,Market Unrealized Returns Currency
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","AAPL","NASDAQ","XNAS","Apple Inc","EQUITY","5.0024","LONG","340.4","USD","2219.54","CAD","1591.69","USD","1703.61","USD","111.91","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","APTX","TSX","XTSE","Apotex Health Corp.","EQUITY","1","LONG","33.005","CAD","24","CAD","24","CAD","33.005","CAD","9.005","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","UCU","TSX-V","XTSX","Ucore Rare Metals Inc.","EQUITY","0.3467","LONG","2.61","CAD","1.25","CAD","1.25","CAD","0.90","CAD","-0.35","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","CAD","","","CAD","CURRENCY","136.44","LONG","1","CAD","136.44","CAD","136.44","CAD","136.44","CAD","0","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","USD","","","USD","CURRENCY","1000.0","LONG","1","USD","1420.0","CAD","1000.0","USD","1000.0","USD","0","USD"
"""
    parsed = parse_wealthsimple_csv(sample_csv)
    assert parsed["num_holdings"] == 3
    tickers = [h["ticker"] for h in parsed["holdings"]]
    assert "AAPL" in tickers
    assert "APTX.TO" in tickers
    assert "UCU.V" in tickers
    assert parsed["cash_reserves_cad"] > 1500
    print("  [OK] Wealthsimple parsing and TSX/TSX-V harmonization working correctly.")


if __name__ == "__main__":
    test_cholesky_regularization()
    test_full_pipeline_mock()
    test_wealthsimple_parser()
    test_yfinance_integration()
    print("\n[SUCCESS] All engine tests passed successfully!")

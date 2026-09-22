"""
CLI Demonstration of the Portfolio Monte Carlo Risk Simulator
Can be run directly with: python cli_demo.py
"""

import argparse
from engine.data_loader import fetch_historical_data, compute_portfolio_statistics
from engine.monte_carlo import run_monte_carlo_simulation
from engine.optimizer import calculate_efficient_frontier


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo Portfolio Risk & Frontier Analyzer")
    parser.add_argument("--tickers", nargs="+", default=["XEQT.TO", "SHOP.TO", "TD.TO", "AAPL", "VFV.TO"],
                        help="List of ticker symbols (e.g. SHOP.TO AAPL VFV.TO)")
    parser.add_argument("--weights", nargs="+", type=float, default=[0.30, 0.15, 0.15, 0.20, 0.20],
                        help="Allocation weights for tickers (must sum to 1.0 or will be normalized)")
    parser.add_argument("--initial", type=float, default=25000.0, help="Initial investment amount ($)")
    parser.add_argument("--sims", type=int, default=5000, help="Number of Monte Carlo simulations")
    parser.add_argument("--days", type=int, default=252, help="Time horizon in trading days (252 = 1 year)")
    parser.add_argument("--period", type=str, default="3y", help="Historical data lookback period (e.g. 2y, 3y, 5y)")
    args = parser.parse_args()

    print("=" * 70)
    print("      PORTFOLIO MONTE CARLO RISK SIMULATOR & EFFICIENT FRONTIER")
    print("=" * 70)
    print(f"Fetching {args.period} of historical data for: {args.tickers}...")

    price_df, returns_df, valid_tickers = fetch_historical_data(args.tickers, period=args.period)
    weights = args.weights[:len(valid_tickers)]
    if len(weights) < len(valid_tickers):
        weights += [1.0 / len(valid_tickers)] * (len(valid_tickers) - len(weights))

    # 1. Historical Stats
    stats = compute_portfolio_statistics(returns_df, weights)
    print("\n--- Asset Statistics & Allocation ---")
    for a in stats["asset_stats"]:
        print(f"  {a['ticker']:<10} Weight: {a['weight']:>6.1%} | Return: {a['annual_return']:>6.1%} | Vol: {a['annual_volatility']:>6.1%} | Sharpe: {a['sharpe_ratio']:>5.2f}")

    print("\n--- Historical Correlation Matrix ---")
    header = "          " + "".join([f"{t:>10}" for t in valid_tickers])
    print(header)
    for i, t in enumerate(valid_tickers):
        row_vals = "".join([f"{stats['correlation_matrix'][i][j]:>10.2f}" for j in range(len(valid_tickers))])
        print(f"{t:<10}{row_vals}")

    # 2. Monte Carlo Simulation
    print(f"\n--- Running {args.sims:,} Monte Carlo Simulations over {args.days} Trading Days ---")
    mc_res = run_monte_carlo_simulation(
        price_df=price_df,
        returns_df=returns_df,
        weights=weights,
        initial_investment=args.initial,
        time_horizon_days=args.days,
        num_simulations=args.sims
    )
    m = mc_res["metrics"]
    print(f"  Starting Capital:         ${args.initial:>12,.2f}")
    print(f"  Expected Terminal Value:  ${m['expected_terminal_value']:>12,.2f} ({m['expected_return_pct']:>+6.1%})")
    print(f"  Median Terminal Value:    ${m['median_terminal_value']:>12,.2f} ({m['median_return_pct']:>+6.1%})")
    print(f"  95% Value at Risk (VaR):  ${m['var_95_dollar']:>12,.2f} (-{m['var_95_pct']:>5.1%})")
    print(f"  95% Expected Shortfall:   ${m['cvar_95_dollar']:>12,.2f} (-{m['cvar_95_pct']:>5.1%})")
    print(f"  Probability of Loss:       {m['prob_loss']:>12.1%}")
    print(f"  Median Maximum Drawdown:   {m['median_max_drawdown']:>12.1%}")

    # 3. Markowitz Optimization
    print("\n--- Markowitz Mean-Variance Comparison ---")
    opt = calculate_efficient_frontier(returns_df, weights, num_frontier_points=15, num_random_portfolios=200)
    for p_key in ["actual", "equal_weight", "min_volatility", "max_sharpe"]:
        p = opt[p_key]
        print(f"  {p['name']:<24} Return: {p['expected_return']:>6.1%} | Vol: {p['volatility']:>6.1%} | Sharpe: {p['sharpe_ratio']:>5.2f}")

    print("=" * 70)


if __name__ == "__main__":
    main()

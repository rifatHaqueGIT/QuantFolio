"""
Data Loader & Financial Statistics Engine
Fetches historical market data via yfinance and computes returns, volatilities, and correlation/covariance matrices.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import yfinance as yf


def fetch_historical_data(
    tickers: List[str],
    period: str = "3y"
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Fetch adjusted close prices for the given tickers over a historical period.
    Returns:
        (price_df, daily_returns_df, valid_tickers)
    """
    cleaned_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not cleaned_tickers:
        raise ValueError("At least one valid ticker symbol must be provided.")

    # Download historical prices
    raw_data = yf.download(
        cleaned_tickers,
        period=period,
        auto_adjust=True,
        progress=False
    )

    if raw_data.empty:
        raise ValueError(f"Could not retrieve market data for tickers: {cleaned_tickers}")

    # Handle pandas DataFrame structure from yfinance
    # yfinance can return a MultiIndex (Price, Ticker) or single-level depending on ticker count
    if isinstance(raw_data.columns, pd.MultiIndex):
        if "Close" in raw_data.columns.levels[0]:
            price_df = raw_data["Close"]
        else:
            # Fallback to the first level
            price_df = raw_data.iloc[:, 0:len(cleaned_tickers)]
    else:
        # Single ticker case
        if "Close" in raw_data.columns:
            price_df = raw_data[["Close"]]
            price_df.columns = cleaned_tickers
        else:
            price_df = pd.DataFrame({cleaned_tickers[0]: raw_data.iloc[:, 0]})

    # Drop columns that have all NaNs or insufficient data
    price_df = price_df.dropna(axis=1, how="all")
    valid_tickers = [t for t in cleaned_tickers if t in price_df.columns]

    if not valid_tickers:
        raise ValueError(f"No valid price history available for: {tickers}")

    # Forward fill then backward fill to align dates across different exchanges
    price_df = price_df.ffill().bfill().dropna()

    if len(price_df) < 20:
        raise ValueError("Insufficient historical data points (need at least 20 trading days).")

    # Compute daily percentage returns
    returns_df = price_df.pct_change().dropna()

    return price_df, returns_df, valid_tickers


def compute_portfolio_statistics(
    returns_df: pd.DataFrame,
    weights: np.ndarray,
    trading_days: int = 252,
    risk_free_rate: float = 0.035
) -> Dict:
    """
    Compute annualized portfolio return, volatility, Sharpe ratio,
    individual asset statistics, covariance, and correlation matrices.
    """
    weights = np.array(weights, dtype=float)
    if not np.isclose(weights.sum(), 1.0, atol=1e-4):
        # Normalize weights
        weights = weights / weights.sum()

    # Asset-level stats
    mean_daily_returns = returns_df.mean()
    annualized_returns = (1 + mean_daily_returns) ** trading_days - 1
    annualized_volatilities = returns_df.std() * np.sqrt(trading_days)

    # Covariance & Correlation matrices
    cov_matrix_daily = returns_df.cov().values
    cov_matrix_annual = cov_matrix_daily * trading_days
    corr_matrix = returns_df.corr().values

    # Portfolio level stats
    port_expected_return = float(np.dot(weights, annualized_returns))
    port_variance = float(np.dot(weights.T, np.dot(cov_matrix_annual, weights)))
    port_volatility = float(np.sqrt(max(port_variance, 1e-8)))
    sharpe_ratio = float((port_expected_return - risk_free_rate) / port_volatility)

    tickers = list(returns_df.columns)

    asset_stats = []
    for i, ticker in enumerate(tickers):
        asset_stats.append({
            "ticker": ticker,
            "weight": float(weights[i]),
            "annual_return": float(annualized_returns[ticker]),
            "annual_volatility": float(annualized_volatilities[ticker]),
            "sharpe_ratio": float((annualized_returns[ticker] - risk_free_rate) / max(annualized_volatilities[ticker], 1e-6))
        })

    return {
        "tickers": tickers,
        "weights": [float(w) for w in weights],
        "portfolio_expected_return": port_expected_return,
        "portfolio_volatility": port_volatility,
        "sharpe_ratio": sharpe_ratio,
        "correlation_matrix": corr_matrix.tolist(),
        "covariance_matrix_annual": cov_matrix_annual.tolist(),
        "asset_stats": asset_stats
    }


def parse_wealthsimple_csv(
    csv_content: str,
    selected_account: Optional[str] = None
) -> Dict:
    """
    Parse a Wealthsimple positions export CSV.
    Extracts individual accounts, cash reserves, holdings, normalized tickers,
    and calculates market-value proportional portfolio weights.

    Parameters:
        csv_content: Raw CSV string from Wealthsimple export.
        selected_account: Optional account name to filter by (or None for consolidated).
    """
    import csv
    import io

    # Filter out empty lines or trailing timestamp lines like "As of 2026-09-22..."
    lines = [
        line for line in csv_content.strip().splitlines()
        if line.strip() and not line.strip().startswith('"As of') and not line.strip().startswith('As of')
    ]
    cleaned_csv = "\n".join(lines)

    reader = csv.DictReader(io.StringIO(cleaned_csv))
    rows = list(reader)

    if not rows:
        raise ValueError("The provided CSV contains no valid trade or position records.")

    # 1. Determine USD/CAD exchange rate from USD cash rows or default
    usdcad = 1.42
    for r in rows:
        if r.get("Security Type", "").strip() == "CURRENCY" and r.get("Symbol", "").strip() == "USD":
            try:
                usd_val = float(r.get("Market Value", 0) or 0)
                cad_val = float(r.get("Book Value (CAD)", 0) or 0)
                if usd_val > 0 and cad_val > 0:
                    usdcad = cad_val / usd_val
                    break
            except (ValueError, TypeError):
                pass

    # 2. Extract accounts
    all_accounts = sorted(list(set(r.get("Account Name", "Default").strip() for r in rows if r.get("Account Name"))))

    # 3. Process rows
    raw_holdings = []
    cash_by_account = {acc: 0.0 for acc in all_accounts}
    total_cash_cad = 0.0

    for r in rows:
        account = r.get("Account Name", "Default").strip()
        sec_type = r.get("Security Type", "").strip().upper()
        sym = r.get("Symbol", "").strip()
        ex = r.get("Exchange", "").strip().upper()
        name = r.get("Name", "").strip()

        try:
            mval = float(r.get("Market Value", 0) or 0)
        except (ValueError, TypeError):
            mval = 0.0

        curr = r.get("Market Value Currency", "USD").strip().upper()
        mval_cad = mval * usdcad if curr == "USD" else mval

        # Cash balances
        if sec_type == "CURRENCY":
            cash_by_account[account] = cash_by_account.get(account, 0.0) + mval_cad
            total_cash_cad += mval_cad
            continue

        # Equities and ETFs
        if sec_type in ["EQUITY", "EXCHANGE_TRADED_FUND"]:
            # Ticker harmonization for Canadian & US exchanges
            ticker = sym
            if ex in ["TSX", "XTSE"] and not ticker.endswith(".TO"):
                if "CDR" in name.upper():
                    ticker = sym  # Map CDRs to underlying liquid US ticker for deep historical simulation
                else:
                    ticker = f"{sym}.TO"
            elif ex in ["TSX-V", "TSXV", "XTSX"] and not ticker.endswith(".V"):
                ticker = f"{sym}.V"

            try:
                qty = float(r.get("Quantity", 0) or 0)
            except (ValueError, TypeError):
                qty = 0.0

            try:
                price = float(r.get("Market Price", 0) or 0)
            except (ValueError, TypeError):
                price = 0.0

            raw_holdings.append({
                "account": account,
                "raw_symbol": sym,
                "ticker": ticker,
                "name": name,
                "security_type": sec_type,
                "exchange": ex,
                "quantity": qty,
                "market_price": price,
                "market_price_currency": curr,
                "market_value_orig": mval,
                "market_value_cad": mval_cad
            })

    # 4. Filter by account if requested
    if selected_account and selected_account != "All Accounts":
        active_holdings = [h for h in raw_holdings if h["account"] == selected_account]
        active_cash_cad = cash_by_account.get(selected_account, 0.0)
    else:
        active_holdings = raw_holdings
        active_cash_cad = total_cash_cad

    # 5. Aggregate multiple positions in the same ticker (e.g. across accounts if consolidated)
    aggregated: Dict[str, Dict] = {}
    for h in active_holdings:
        tkr = h["ticker"]
        if tkr not in aggregated:
            aggregated[tkr] = {
                "ticker": tkr,
                "raw_symbol": h["raw_symbol"],
                "name": h["name"],
                "accounts": [h["account"]],
                "quantity": h["quantity"],
                "market_value_cad": h["market_value_cad"],
                "currency": h["market_price_currency"]
            }
        else:
            aggregated[tkr]["quantity"] += h["quantity"]
            aggregated[tkr]["market_value_cad"] += h["market_value_cad"]
            if h["account"] not in aggregated[tkr]["accounts"]:
                aggregated[tkr]["accounts"].append(h["account"])

    holdings_list = list(aggregated.values())
    total_invested_cad = sum(item["market_value_cad"] for item in holdings_list)

    # Sort descending by value and compute weights
    holdings_list.sort(key=lambda x: x["market_value_cad"], reverse=True)

    for item in holdings_list:
        weight = (item["market_value_cad"] / max(total_invested_cad, 1e-6)) * 100.0
        item["weight_pct"] = round(weight, 2)
        item["market_value_cad"] = round(item["market_value_cad"], 2)

    return {
        "accounts": all_accounts,
        "selected_account": selected_account or "All Accounts",
        "total_invested_cad": round(total_invested_cad, 2),
        "cash_reserves_cad": round(active_cash_cad, 2),
        "total_portfolio_cad": round(total_invested_cad + active_cash_cad, 2),
        "usd_cad_rate": round(usdcad, 4),
        "num_holdings": len(holdings_list),
        "holdings": holdings_list
    }


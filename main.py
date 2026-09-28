"""
FastAPI Server for Portfolio Monte Carlo Risk Simulator & Optimization Engine
Serves API endpoints and the rich frontend dashboard.
Includes gs-quant-inspired extensions for advanced analytics.
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import os

from engine.data_loader import fetch_historical_data, compute_portfolio_statistics, parse_wealthsimple_csv
from engine.monte_carlo import run_monte_carlo_simulation
from engine.optimizer import calculate_efficient_frontier
from engine.gs_quant_extensions import (
    compute_gs_quant_analytics,
    backtest_portfolio,
    smooth_spikes,
    smooth_outliers,
    RebalFreq,
    ThresholdType,
)

app = FastAPI(
    title="Monte Carlo Portfolio Risk Engine",
    description="Quantitative portfolio risk simulation, Modern Portfolio Theory optimization, and gs-quant-inspired analytics",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulationRequest(BaseModel):
    tickers: List[str] = Field(default=["XEQT.TO", "SHOP.TO", "TD.TO", "AAPL", "VFV.TO"])
    weights: List[float] = Field(default=[0.30, 0.15, 0.15, 0.20, 0.20])
    initial_investment: float = Field(default=25000.0, ge=100.0)
    time_horizon_days: int = Field(default=252, ge=20, le=2520)
    num_simulations: int = Field(default=5000, ge=500, le=20000)
    period: str = Field(default="3y")
    risk_free_rate: float = Field(default=0.035, ge=0.0, le=0.20)
    smooth_data: bool = Field(default=False, description="Apply gs-quant spike/outlier smoothing to price data")
    smooth_threshold: float = Field(default=0.5, ge=0.05, le=2.0, description="Smoothing threshold (0.5 = 50% deviation)")


@app.post("/api/simulate")
async def simulate_portfolio(req: SimulationRequest):
    try:
        # 1. Fetch data
        price_df, returns_df, valid_tickers = fetch_historical_data(req.tickers, period=req.period)
        
        # Match weights to valid tickers
        weights = req.weights[:len(valid_tickers)]
        if len(weights) < len(valid_tickers):
            weights += [1.0 / len(valid_tickers)] * (len(valid_tickers) - len(weights))

        # 1b. Optional gs-quant data smoothing
        if req.smooth_data:
            for col in price_df.columns:
                price_df[col] = smooth_outliers(price_df[col], threshold=req.smooth_threshold)
                if len(price_df[col]) > 3:
                    smoothed = smooth_spikes(price_df[col], threshold=req.smooth_threshold)
                    # Re-index to align (smooth_spikes drops first/last points)
                    price_df.loc[smoothed.index, col] = smoothed
            # Recompute returns from smoothed prices
            returns_df = price_df.pct_change().dropna()

        # 2. Portfolio & Asset Statistics
        stats = compute_portfolio_statistics(
            returns_df=returns_df,
            weights=weights,
            trading_days=252,
            risk_free_rate=req.risk_free_rate
        )

        # 3. Correlated Monte Carlo Simulation
        mc_results = run_monte_carlo_simulation(
            price_df=price_df,
            returns_df=returns_df,
            weights=weights,
            initial_investment=req.initial_investment,
            time_horizon_days=req.time_horizon_days,
            num_simulations=req.num_simulations
        )

        # 4. Markowitz Optimization & Efficient Frontier
        frontier_data = calculate_efficient_frontier(
            returns_df=returns_df,
            actual_weights=weights,
            trading_days=252,
            risk_free_rate=req.risk_free_rate,
            num_frontier_points=30,
            num_random_portfolios=500
        )

        # 5. GS-Quant Analytics (EWMA vol, rolling Sharpe, excess returns)
        gs_analytics = compute_gs_quant_analytics(
            price_df=price_df,
            returns_df=returns_df,
            weights=weights,
            risk_free_rate=req.risk_free_rate,
            trading_days=252
        )

        return {
            "status": "success",
            "tickers": valid_tickers,
            "weights": stats["weights"],
            "stats": stats,
            "simulation": mc_results,
            "optimization": frontier_data,
            "gs_quant_analytics": gs_analytics,
            "data_smoothed": req.smooth_data
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


class WealthsimpleParseRequest(BaseModel):
    csv_text: str
    selected_account: Optional[str] = None


@app.post("/api/wealthsimple/parse")
async def parse_wealthsimple(req: WealthsimpleParseRequest):
    try:
        result = parse_wealthsimple_csv(
            csv_content=req.csv_text,
            selected_account=req.selected_account
        )
        return {
            "status": "success",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")


# ─── GS-Quant Extension Endpoints ─────────────────────────────────────────────

class BacktestRequest(BaseModel):
    tickers: List[str] = Field(default=["SPY", "AGG", "GLD"])
    weights: List[float] = Field(default=[0.6, 0.3, 0.1])
    period: str = Field(default="3y")
    rebal_freq: str = Field(default="monthly", description="daily, weekly, or monthly")
    costs_bps: float = Field(default=10.0, ge=0.0, le=100.0, description="Transaction cost in basis points per asset")
    initial_value: float = Field(default=10000.0, ge=100.0)


@app.post("/api/backtest")
async def run_backtest(req: BacktestRequest):
    """
    GS-Quant-style basket backtesting with periodic rebalancing and transaction costs.
    Inspired by gs-quant's backtest_basket() from backtesting.py.
    """
    try:
        price_df, _, valid_tickers = fetch_historical_data(req.tickers, period=req.period)

        weights = req.weights[:len(valid_tickers)]
        if len(weights) < len(valid_tickers):
            weights += [1.0 / len(valid_tickers)] * (len(valid_tickers) - len(weights))

        freq_map = {
            "daily": RebalFreq.DAILY,
            "weekly": RebalFreq.WEEKLY,
            "monthly": RebalFreq.MONTHLY,
        }
        rebal = freq_map.get(req.rebal_freq.lower(), RebalFreq.MONTHLY)

        # Convert bps to fraction per asset
        cost_fraction = req.costs_bps / 10000.0
        costs = [cost_fraction] * len(valid_tickers)

        result = backtest_portfolio(
            price_df=price_df,
            weights=weights,
            costs=costs,
            rebal_freq=rebal,
            initial_value=req.initial_value
        )

        return {
            "status": "success",
            "tickers": valid_tickers,
            "backtest": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest error: {str(e)}")


class AnalyticsRequest(BaseModel):
    tickers: List[str] = Field(default=["XEQT.TO", "SHOP.TO", "TD.TO", "AAPL", "VFV.TO"])
    weights: List[float] = Field(default=[0.30, 0.15, 0.15, 0.20, 0.20])
    period: str = Field(default="3y")
    risk_free_rate: float = Field(default=0.035, ge=0.0, le=0.20)


@app.post("/api/analytics")
async def get_analytics(req: AnalyticsRequest):
    """
    GS-Quant-inspired analytics: EWMA volatility, Garman-Klass vol,
    rolling Sharpe ratio, and day-count-correct excess returns.
    """
    try:
        price_df, returns_df, valid_tickers = fetch_historical_data(req.tickers, period=req.period)

        weights = req.weights[:len(valid_tickers)]
        if len(weights) < len(valid_tickers):
            weights += [1.0 / len(valid_tickers)] * (len(valid_tickers) - len(weights))

        analytics = compute_gs_quant_analytics(
            price_df=price_df,
            returns_df=returns_df,
            weights=weights,
            risk_free_rate=req.risk_free_rate,
            trading_days=252
        )

        return {
            "status": "success",
            "tickers": valid_tickers,
            "analytics": analytics
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")


# Serve frontend static assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)

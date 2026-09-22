"""
FastAPI Server for Portfolio Monte Carlo Risk Simulator & Optimization Engine
Serves API endpoints and the rich frontend dashboard.
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

app = FastAPI(
    title="Monte Carlo Portfolio Risk Engine",
    description="Quantitative portfolio risk simulation and Modern Portfolio Theory optimization",
    version="1.0.0"
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


@app.post("/api/simulate")
async def simulate_portfolio(req: SimulationRequest):
    try:
        # 1. Fetch data
        price_df, returns_df, valid_tickers = fetch_historical_data(req.tickers, period=req.period)
        
        # Match weights to valid tickers
        weights = req.weights[:len(valid_tickers)]
        if len(weights) < len(valid_tickers):
            weights += [1.0 / len(valid_tickers)] * (len(valid_tickers) - len(weights))

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

        return {
            "status": "success",
            "tickers": valid_tickers,
            "weights": stats["weights"],
            "stats": stats,
            "simulation": mc_results,
            "optimization": frontier_data
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



# Serve frontend static assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)

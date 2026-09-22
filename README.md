# QuantFolio — Correlated Monte Carlo Portfolio Risk & Frontier Engine

A quantitative finance application designed to analyze personal multi-asset investment portfolios using real-market daily price feeds, high-dimensional correlated Monte Carlo simulations, and Markowitz Modern Portfolio Theory (MPT).

---

## Key Features

1. **Clean Data Ingestion Pipeline**:
   - Downloads daily adjusted historical price data directly from `yfinance`.
   - Cleans missing dates and aligns multi-market schedules (e.g., TSX vs. NYSE/NASDAQ holidays).
   - Zero credential requirements: no dangerous scraping or third-party credential exposure.

2. **Multivariate Correlated Monte Carlo Engine**:
   - Models continuous price dynamics via **Geometric Brownian Motion (GBM)**:
     $$dS_t = \mu S_t dt + \sigma S_t dW_t$$
   - Generates correlated market shocks across all assets using the **Cholesky Decomposition** ($LL^T = \Sigma$) of the empirical covariance matrix.
   - Robust singular-matrix handling with automatic diagonal ridge regularization and eigenvalue reconstruction.
   - Computes:
     - Full percentile fan trajectories (5th, 25th, 50th, 75th, 95th percentiles).
     - **Value at Risk (95% & 99% VaR)** in both dollars and percentage terms.
     - **Conditional Value at Risk (95% & 99% CVaR / Expected Shortfall)**.
     - Probability of loss over horizon.
     - Peak-to-trough Maximum Drawdown distributions.

3. **Markowitz Efficient Frontier & Portfolio Optimizer**:
   - Implements Mean-Variance Optimization using Sequential Least Squares Programming (`scipy.optimize.minimize` with SLSQP).
   - Solves for:
     - **Tangency Portfolio (Maximum Sharpe Ratio)**: Maximizes excess returns per unit of volatility.
     - **Minimum Volatility Portfolio**: Lowest possible portfolio risk on the frontier.
     - **Equal-Weighted Benchmark ($1/N$)**: Standard baseline comparison.
     - **User's Actual Portfolio**: Evaluates where your current allocation sits relative to the efficient frontier.
   - Simulates hundreds of random portfolio allocations to visually show the feasible investment universe.

4. **Interactive Dark-Mode Dashboard**:
   - Dark mode with glassmorphic cards, glowing accents, and typography (`Plus Jakarta Sans` + `JetBrains Mono`).
   - Dynamic ticker entry, preset portfolios (Wealthsimple Balanced, Canadian/US Growth, Tech Leaders, All-Weather ETF).
   - Interactive Chart.js charts: Trajectory Fan, Tail-Risk Histogram, Efficient Frontier scatter plot, Allocation Donut, and Heatmap of Pearson correlations.

5. **Wealthsimple CSV Ingestion & Account Consolidation**:
   - One-click file upload or direct text paste of Wealthsimple trade and position export CSVs.
   - Automatically maps Canadian exchange tickers (e.g. `APTX` $\rightarrow$ `APTX.TO`, `UCU` $\rightarrow$ `UCU.V`, CDRs like `NVDA`).
   - Handles multi-account filtering (TFSA, FHSA, Non-registered) or full portfolio consolidation.
   - Calculates real-time CAD/USD conversion, tracks liquidity cash reserves, and derives exact market-value proportional weights.

---

## Quick Start

### 1. Requirements
Ensure Python 3.10+ is installed along with dependencies:
```bash
pip install fastapi uvicorn yfinance numpy pandas scipy matplotlib
```

### 2. Run the Interactive Web Dashboard
```bash
python main.py
```
Open your browser at:
**[http://127.0.0.1:8080](http://127.0.0.1:8080)**

### 3. Run the CLI Simulation Script
If you want to run quick simulations directly in the terminal:
```bash
python cli_demo.py --tickers XEQT.TO SHOP.TO TD.TO AAPL VFV.TO --weights 0.3 0.15 0.15 0.2 0.2 --initial 25000 --sims 5000 --days 252
```

### 4. Run Unit Tests
```bash
python test_engine.py
```

---

## Resume & Interview Talking Points

- **Why manual entry instead of bank scraping?**
  *"Financial institutions do not offer open public APIs without aggregator agreements like Plaid or SnapTrade. Scraping unofficial endpoints requires sharing raw credentials and violates Terms of Service. By ingesting tickers and weights cleanly and feeding them into public market feeds via yfinance, the data pipeline is resilient, production-ready, and compliant."*
- **Why Cholesky decomposition instead of simulating single-ticker paths independently?**
  *"Assets in a portfolio do not move independently; tech stocks move together, and broad index ETFs share high beta with their constituents. Uncorrelated simulations drastically underestimate portfolio tail risk. Factoring the covariance matrix via Cholesky decomposition ($Z_{corr} = L \cdot Z_{indep}$) ensures realistic joint shocks."*
- **VaR vs. CVaR:**
  *"While 95% VaR answers 'What is the maximum I can expect to lose 95% of the time?', it tells you nothing about the severity of losses in the remaining 5% catastrophic tail. CVaR (Expected Shortfall) calculates the average loss conditional on exceeding VaR, making it a coherent risk measure that properly penalizes fat-tailed downside events."*

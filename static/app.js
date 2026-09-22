/**
 * QuantFolio Front-End Application Logic
 * Integrates Chart.js visualizations, state management, presets, and API communication.
 */

// Presets Definition
const PRESETS = {
    my_wealthsimple: [
        { ticker: "AAPL", weight: 16.14 },
        { ticker: "DLLL", weight: 14.47 },
        { ticker: "AXTI", weight: 11.12 },
        { ticker: "SNDK", weight: 8.59 },
        { ticker: "SNXX", weight: 6.31 },
        { ticker: "AMD", weight: 5.89 },
        { ticker: "SPCX", weight: 5.82 },
        { ticker: "MU", weight: 4.15 },
        { ticker: "MDB", weight: 4.08 },
        { ticker: "SKHY", weight: 3.69 },
        { ticker: "NVDA", weight: 3.15 },
        { ticker: "MDA.TO", weight: 3.08 },
        { ticker: "AAOI", weight: 2.51 },
        { ticker: "RY.TO", weight: 2.30 },
        { ticker: "NBIS", weight: 1.57 },
        { ticker: "DELL", weight: 1.25 },
        { ticker: "MRNA", weight: 1.21 },
        { ticker: "SOXL", weight: 1.00 },
        { ticker: "APTX.TO", weight: 0.22 },
        { ticker: "LUNR", weight: 0.11 },
        { ticker: "SIDU", weight: 0.03 },
        { ticker: "UCU.V", weight: 0.01 }
    ],
    canadian: [
        { ticker: "XEQT.TO", weight: 35 },
        { ticker: "VFV.TO", weight: 25 },
        { ticker: "TD.TO", weight: 15 },
        { ticker: "SHOP.TO", weight: 15 },
        { ticker: "BNS.TO", weight: 10 }
    ],
    growth: [
        { ticker: "XEQT.TO", weight: 30 },
        { ticker: "SHOP.TO", weight: 15 },
        { ticker: "TD.TO", weight: 15 },
        { ticker: "AAPL", weight: 20 },
        { ticker: "VFV.TO", weight: 20 }
    ],
    tech: [
        { ticker: "AAPL", weight: 25 },
        { ticker: "MSFT", weight: 25 },
        { ticker: "NVDA", weight: 20 },
        { ticker: "AMZN", weight: 15 },
        { ticker: "GOOGL", weight: 15 }
    ],
    allweather: [
        { ticker: "VTI", weight: 30 },
        { ticker: "TLT", weight: 40 },
        { ticker: "IEF", weight: 15 },
        { ticker: "GLD", weight: 8 },
        { ticker: "DBC", weight: 7 }
    ]
};

// Global State
let currentHoldings = [...PRESETS.growth];
let charts = {
    trajectory: null,
    distribution: null,
    frontier: null,
    allocation: null
};

// DOM Elements
const holdingsTbody = document.getElementById("holdings-tbody");
const totalWeightBadge = document.getElementById("total-weight-badge");
const newTickerInput = document.getElementById("new-ticker-input");
const newWeightInput = document.getElementById("new-weight-input");
const addTickerBtn = document.getElementById("add-ticker-btn");
const equalizeBtn = document.getElementById("equalize-weights-btn");
const normalizeBtn = document.getElementById("normalize-weights-btn");
const runSimBtn = document.getElementById("run-sim-btn");
const toast = document.getElementById("toast");

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    renderHoldingsTable();
    setupEventListeners();
    // Run initial simulation automatically
    runSimulation();
});

// Event Listeners
function setupEventListeners() {
    // Preset Buttons
    document.querySelectorAll(".preset-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const presetKey = btn.dataset.preset;
            if (PRESETS[presetKey]) {
                currentHoldings = JSON.parse(JSON.stringify(PRESETS[presetKey]));
                if (presetKey === "my_wealthsimple") {
                    const capitalInput = document.getElementById("initial-capital");
                    if (capitalInput) capitalInput.value = 15104;
                    const lookbackInput = document.getElementById("lookback-period");
                    if (lookbackInput) lookbackInput.value = "1y";
                }
                renderHoldingsTable();
                runSimulation();
            }
        });
    });

    // Setup Wealthsimple Modal
    setupWealthsimpleModal();

    // Add Ticker
    addTickerBtn.addEventListener("click", handleAddTicker);
    newTickerInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleAddTicker();
    });

    // Weight Actions
    equalizeBtn.addEventListener("click", handleEqualizeWeights);
    normalizeBtn.addEventListener("click", handleNormalizeWeights);

    // Run Simulation Button
    runSimBtn.addEventListener("click", () => runSimulation());

    // Tab Navigation
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            const tabId = btn.dataset.tab;
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add("active");
                // Resize charts if needed
                window.dispatchEvent(new Event("resize"));
            }
        });
    });
}

// Holdings Management
function renderHoldingsTable() {
    holdingsTbody.innerHTML = "";
    let totalWeight = 0;

    currentHoldings.forEach((item, index) => {
        totalWeight += parseFloat(item.weight) || 0;
        const row = document.createElement("tr");

        row.innerHTML = `
            <td class="ticker-cell">${item.ticker}</td>
            <td>
                <input type="number" class="weight-input" data-index="${index}" value="${item.weight}" min="1" max="100" step="1">
            </td>
            <td style="text-align: right;">
                <button class="btn-delete-row" data-index="${index}" title="Remove ticker">&times;</button>
            </td>
        `;
        holdingsTbody.appendChild(row);
    });

    // Total Weight Badge
    totalWeight = Math.round(totalWeight * 10) / 10;
    totalWeightBadge.textContent = `${totalWeight}%`;
    if (Math.abs(totalWeight - 100) > 0.5) {
        totalWeightBadge.classList.add("danger");
    } else {
        totalWeightBadge.classList.remove("danger");
    }

    // Bind dynamic row inputs
    document.querySelectorAll(".weight-input").forEach(input => {
        input.addEventListener("change", (e) => {
            const idx = parseInt(e.target.dataset.index);
            const val = parseFloat(e.target.value) || 0;
            currentHoldings[idx].weight = Math.max(0, val);
            renderHoldingsTable();
        });
    });

    document.querySelectorAll(".btn-delete-row").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const idx = parseInt(e.target.dataset.index);
            if (currentHoldings.length <= 1) {
                showToast("Portfolio must have at least one ticker.", true);
                return;
            }
            currentHoldings.splice(idx, 1);
            renderHoldingsTable();
        });
    });
}

function handleAddTicker() {
    const ticker = newTickerInput.value.trim().toUpperCase();
    const weight = parseFloat(newWeightInput.value) || 10;

    if (!ticker) {
        showToast("Please enter a ticker symbol.", true);
        return;
    }

    if (currentHoldings.some(h => h.ticker === ticker)) {
        showToast(`Ticker ${ticker} is already in the portfolio.`, true);
        return;
    }

    currentHoldings.push({ ticker, weight });
    newTickerInput.value = "";
    newWeightInput.value = "15";
    renderHoldingsTable();
}

function handleEqualizeWeights() {
    if (currentHoldings.length === 0) return;
    const equalW = Math.round((100 / currentHoldings.length) * 10) / 10;
    currentHoldings.forEach(h => h.weight = equalW);
    renderHoldingsTable();
}

function handleNormalizeWeights() {
    const sum = currentHoldings.reduce((acc, h) => acc + (parseFloat(h.weight) || 0), 0);
    if (sum === 0) return;
    currentHoldings.forEach(h => {
        h.weight = Math.round(((h.weight / sum) * 100) * 10) / 10;
    });
    renderHoldingsTable();
}

// Toast Notification
function showToast(message, isError = false) {
    toast.textContent = message;
    toast.className = `toast ${isError ? 'error' : ''}`;
    setTimeout(() => {
        toast.className = "toast hidden";
    }, 4500);
}

// API Simulation Request
async function runSimulation() {
    runSimBtn.classList.add("loading");
    runSimBtn.disabled = true;

    try {
        const tickers = currentHoldings.map(h => h.ticker);
        const weights = currentHoldings.map(h => (parseFloat(h.weight) || 0) / 100);
        const initialCapital = parseFloat(document.getElementById("initial-capital").value) || 25000;
        const horizon = parseInt(document.getElementById("time-horizon").value) || 252;
        const simCount = parseInt(document.getElementById("sim-count").value) || 5000;
        const period = document.getElementById("lookback-period").value || "3y";
        const riskFreeRate = parseFloat(document.getElementById("risk-free-rate").value) || 0.035;

        const payload = {
            tickers,
            weights,
            initial_investment: initialCapital,
            time_horizon_days: horizon,
            num_simulations: simCount,
            period,
            risk_free_rate: riskFreeRate
        };

        const res = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Simulation calculation failed.");
        }

        const data = await res.json();
        updateDashboard(data);
        showToast("Monte Carlo simulation completed successfully!");

    } catch (err) {
        console.error(err);
        showToast(err.message, true);
    } finally {
        runSimBtn.classList.remove("loading");
        runSimBtn.disabled = false;
    }
}

// Update Dashboard View with Results
function updateDashboard(data) {
    const { stats, simulation, optimization } = data;
    const m = simulation.metrics;

    // 1. KPI Cards
    const fmtCurrency = (n) => `$${Math.round(n).toLocaleString()}`;
    const fmtPct = (n) => `${(n * 100).toFixed(1)}%`;

    document.getElementById("val-expected").textContent = fmtCurrency(m.expected_terminal_value);
    document.getElementById("val-median").textContent = fmtCurrency(m.median_terminal_value);

    const expRetElem = document.getElementById("kpi-expected-ret");
    const sign = m.expected_return_pct >= 0 ? "+" : "";
    expRetElem.textContent = `${sign}${fmtPct(m.expected_return_pct)}`;
    expRetElem.className = `kpi-tag ${m.expected_return_pct >= 0 ? 'positive' : 'danger'}`;

    document.getElementById("val-var").textContent = fmtCurrency(m.var_95_dollar);
    document.getElementById("kpi-var-pct").textContent = `-${fmtPct(m.var_95_pct)}`;

    document.getElementById("val-cvar").textContent = fmtCurrency(m.cvar_95_dollar);
    document.getElementById("kpi-cvar-pct").textContent = `-${fmtPct(m.cvar_95_pct)}`;

    document.getElementById("val-prob-loss").textContent = fmtPct(m.prob_loss);
    document.getElementById("val-volatility").textContent = fmtPct(stats.portfolio_volatility);
    document.getElementById("val-sharpe").textContent = stats.sharpe_ratio.toFixed(2);

    // Diagnostics Card
    document.getElementById("diag-median-mdd").textContent = fmtPct(m.median_max_drawdown);
    document.getElementById("diag-worst-mdd").textContent = fmtPct(m.worst_case_drawdown_95);
    document.getElementById("diag-var-99").textContent = `${fmtCurrency(m.var_99_dollar)} (-${fmtPct(m.var_99_pct)})`;
    document.getElementById("diag-cvar-99").textContent = `${fmtCurrency(m.cvar_99_dollar)} (-${fmtPct(m.cvar_99_pct)})`;

    // 2. Trajectory Fan Chart
    renderTrajectoryChart(simulation);

    // 3. Distribution Histogram Chart
    renderDistributionChart(simulation);

    // 4. Efficient Frontier Chart
    renderFrontierChart(optimization);

    // 5. Allocation & Correlation
    renderAllocationChart(stats);
    renderCorrelationMatrix(stats);
    renderBenchmarkTable(optimization, stats);
    renderAssetStatsTable(stats);
}

// Chart 1: Trajectory Fan
function renderTrajectoryChart(sim) {
    const ctx = document.getElementById("trajectoryChart").getContext("2d");
    if (charts.trajectory) charts.trajectory.destroy();

    const horizon = sim.time_horizon_days;
    const labels = Array.from({ length: horizon + 1 }, (_, i) => `Day ${i}`);

    const p = sim.trajectory_percentiles;

    // Sample lines
    const sampleDatasets = sim.sample_paths.slice(0, 10).map((path, idx) => ({
        label: `Path ${idx + 1}`,
        data: path,
        borderColor: "rgba(255, 255, 255, 0.07)",
        borderWidth: 1,
        pointRadius: 0,
        fill: false,
        tension: 0.1
    }));

    charts.trajectory = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                // 90% Confidence Band: Top (p95)
                {
                    label: "95th Percentile",
                    data: p.p95,
                    borderColor: "rgba(99, 102, 241, 0.4)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: "+1",
                    backgroundColor: "rgba(99, 102, 241, 0.10)"
                },
                // 90% Confidence Band: Bottom (p5)
                {
                    label: "5th Percentile (95% VaR floor)",
                    data: p.p5,
                    borderColor: "rgba(244, 63, 94, 0.5)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false
                },
                // 50% Interquartile Range: Top (p75)
                {
                    label: "75th Percentile",
                    data: p.p75,
                    borderColor: "rgba(6, 182, 212, 0.5)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: "+1",
                    backgroundColor: "rgba(6, 182, 212, 0.18)"
                },
                // 50% Interquartile Range: Bottom (p25)
                {
                    label: "25th Percentile",
                    data: p.p25,
                    borderColor: "rgba(6, 182, 212, 0.5)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false
                },
                // Median Path (p50)
                {
                    label: "Median Trajectory (p50)",
                    data: p.p50,
                    borderColor: "#10b981",
                    borderWidth: 2.5,
                    pointRadius: 0,
                    fill: false
                },
                ...sampleDatasets
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            if (context.dataset.label.startsWith("Path")) return null;
                            return `${context.dataset.label}: $${Math.round(context.raw).toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.04)" },
                    ticks: {
                        color: "#94a3b8",
                        maxTicksLimit: 12
                    }
                },
                y: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: {
                        color: "#94a3b8",
                        callback: (v) => `$${(v / 1000).toFixed(0)}k`
                    }
                }
            }
        }
    });
}

// Chart 2: Distribution Histogram
function renderDistributionChart(sim) {
    const ctx = document.getElementById("distributionChart").getContext("2d");
    if (charts.distribution) charts.distribution.destroy();

    const hist = sim.histogram;
    const initial = sim.initial_investment;
    const var95Value = initial - sim.metrics.var_95_dollar;

    const bgColors = hist.bin_centers.map(center => {
        if (center <= var95Value) return "rgba(244, 63, 94, 0.8)"; // VaR 95% tail
        if (center < initial) return "rgba(245, 158, 11, 0.65)"; // Moderate loss
        return "rgba(16, 185, 129, 0.7)"; // Gain
    });

    charts.distribution = new Chart(ctx, {
        type: "bar",
        data: {
            labels: hist.bin_centers.map(c => `$${Math.round(c).toLocaleString()}`),
            datasets: [{
                label: "Simulated Outcomes Count",
                data: hist.counts,
                backgroundColor: bgColors,
                borderRadius: 4,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `Valuation: ${items[0].label}`,
                        label: (item) => `Iterations: ${item.raw.toLocaleString()} paths`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.03)" },
                    ticks: { color: "#94a3b8", maxTicksLimit: 10 }
                },
                y: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8" }
                }
            }
        }
    });
}

// Chart 3: Efficient Frontier
function renderFrontierChart(opt) {
    const ctx = document.getElementById("frontierChart").getContext("2d");
    if (charts.frontier) charts.frontier.destroy();

    // 1. Random portfolio cloud points
    const randomPoints = opt.random_portfolios.volatilities.map((vol, idx) => ({
        x: vol * 100,
        y: opt.random_portfolios.returns[idx] * 100,
        sharpe: opt.random_portfolios.sharpe_ratios[idx]
    }));

    // 2. Frontier curve line
    const frontierPoints = opt.frontier.volatilities.map((vol, idx) => ({
        x: vol * 100,
        y: opt.frontier.returns[idx] * 100
    })).sort((a, b) => a.x - b.x);

    // 3. Highlighted key strategies
    const keyStrategies = [
        {
            name: "Your Portfolio",
            x: opt.actual.volatility * 100,
            y: opt.actual.expected_return * 100,
            color: "#6366f1",
            radius: 9,
            pointStyle: "circle"
        },
        {
            name: "Max Sharpe (Tangency)",
            x: opt.max_sharpe.volatility * 100,
            y: opt.max_sharpe.expected_return * 100,
            color: "#10b981",
            radius: 11,
            pointStyle: "triangle"
        },
        {
            name: "Min Volatility",
            x: opt.min_volatility.volatility * 100,
            y: opt.min_volatility.expected_return * 100,
            color: "#06b6d4",
            radius: 10,
            pointStyle: "rectRot"
        },
        {
            name: "Equal Weight (1/N)",
            x: opt.equal_weight.volatility * 100,
            y: opt.equal_weight.expected_return * 100,
            color: "#e2e8f0",
            radius: 8,
            pointStyle: "crossRot"
        }
    ];

    charts.frontier = new Chart(ctx, {
        type: "scatter",
        data: {
            datasets: [
                // Highlighted Portfolios
                ...keyStrategies.map(strat => ({
                    label: strat.name,
                    data: [{ x: strat.x, y: strat.y }],
                    backgroundColor: strat.color,
                    borderColor: "#ffffff",
                    borderWidth: 2,
                    pointRadius: strat.radius,
                    pointStyle: strat.pointStyle,
                    order: 1
                })),
                // Efficient Frontier Curve
                {
                    type: "line",
                    label: "Efficient Frontier",
                    data: frontierPoints,
                    borderColor: "#38bdf8",
                    borderWidth: 3,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                    order: 2
                },
                // Random portfolios cloud
                {
                    label: "Random Portfolios",
                    data: randomPoints,
                    backgroundColor: "rgba(148, 163, 184, 0.2)",
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    order: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#e2e8f0", usePointStyle: true, boxWidth: 10 }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const p = ctx.raw;
                            return `${ctx.dataset.label}: Return ${p.y.toFixed(1)}%, Vol ${p.x.toFixed(1)}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: "Annualized Volatility (%)", color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", callback: (v) => `${v.toFixed(0)}%` }
                },
                y: {
                    title: { display: true, text: "Expected Annual Return (%)", color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", callback: (v) => `${v.toFixed(0)}%` }
                }
            }
        }
    });
}

// Chart 4: Allocation Doughnut
function renderAllocationChart(stats) {
    const ctx = document.getElementById("allocationChart").getContext("2d");
    if (charts.allocation) charts.allocation.destroy();

    const colors = [
        "#6366f1", "#10b981", "#06b6d4", "#f59e0b", "#ec4899",
        "#8b5cf6", "#14b8a6", "#f97316", "#a855f7", "#3b82f6"
    ];

    charts.allocation = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: stats.tickers,
            datasets: [{
                data: stats.weights.map(w => Math.round(w * 1000) / 10),
                backgroundColor: colors.slice(0, stats.tickers.length),
                borderColor: "#0f172a",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "right",
                    labels: { color: "#e2e8f0", boxWidth: 12, font: { family: "JetBrains Mono", size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${ctx.raw}%`
                    }
                }
            }
        }
    });
}

// Correlation Matrix Table
function renderCorrelationMatrix(stats) {
    const container = document.getElementById("correlation-matrix-container");
    const { tickers, correlation_matrix } = stats;

    let html = `<table class="corr-table"><thead><tr><th></th>`;
    tickers.forEach(t => html += `<th>${t}</th>`);
    html += `</tr></thead><tbody>`;

    tickers.forEach((rowTicker, rIdx) => {
        html += `<tr><th>${rowTicker}</th>`;
        tickers.forEach((colTicker, cIdx) => {
            const val = correlation_matrix[rIdx][cIdx];
            let bgColor = "rgba(255, 255, 255, 0.03)";
            let textColor = "#e2e8f0";

            if (rIdx === cIdx) {
                bgColor = "rgba(99, 102, 241, 0.25)";
            } else if (val > 0.6) {
                bgColor = "rgba(244, 63, 94, 0.25)";
                textColor = "#fecdd3";
            } else if (val > 0.3) {
                bgColor = "rgba(245, 158, 11, 0.20)";
                textColor = "#fef3c7";
            } else if (val < 0) {
                bgColor = "rgba(16, 185, 129, 0.25)";
                textColor = "#a7f3d0";
            }

            html += `<td style="background: ${bgColor}; color: ${textColor};">${val.toFixed(2)}</td>`;
        });
        html += `</tr>`;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
}

// Benchmark Table
function renderBenchmarkTable(opt, stats) {
    const tbody = document.getElementById("benchmark-tbody");
    tbody.innerHTML = "";

    const rows = [
        { strat: "Your Current Allocation", data: opt.actual, badgeClass: "actual" },
        { strat: "Equal-Weighted Benchmark (1/N)", data: opt.equal_weight, badgeClass: "equal" },
        { strat: "Max Sharpe Ratio (Optimal)", data: opt.max_sharpe, badgeClass: "sharpe" },
        { strat: "Minimum Volatility", data: opt.min_volatility, badgeClass: "minvol" }
    ];

    rows.forEach(r => {
        const weightsStr = opt.tickers.map((t, idx) => {
            const w = r.data.weights[idx];
            return `${t}: ${(w * 100).toFixed(0)}%`;
        }).join(", ");

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><span class="strategy-badge ${r.badgeClass}">● ${r.strat}</span></td>
            <td><strong>${(r.data.expected_return * 100).toFixed(1)}%</strong></td>
            <td>${(r.data.volatility * 100).toFixed(1)}%</td>
            <td><strong>${r.data.sharpe_ratio.toFixed(2)}</strong></td>
            <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);">${weightsStr}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Asset Stats Table
function renderAssetStatsTable(stats) {
    const tbody = document.getElementById("asset-stats-tbody");
    tbody.innerHTML = "";

    stats.asset_stats.forEach(a => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="ticker-cell">${a.ticker}</td>
            <td style="font-family: var(--font-mono);">${(a.weight * 100).toFixed(1)}%</td>
            <td style="color: ${a.annual_return >= 0 ? 'var(--accent-emerald)' : 'var(--accent-danger)'}; font-weight: 600;">
                ${a.annual_return >= 0 ? '+' : ''}${(a.annual_return * 100).toFixed(1)}%
            </td>
            <td>${(a.annual_volatility * 100).toFixed(1)}%</td>
            <td style="font-weight: 700;">${a.sharpe_ratio.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Wealthsimple Ingestion & Modal Logic
const PRELOADED_WEALTHSIMPLE_CSV = `Account Name,Account Type,Account Classification,Account Number,Symbol,Exchange,MIC,Name,Security Type,Quantity,Position Direction,Market Price,Market Price Currency,Book Value (CAD),Book Value Currency (CAD),Book Value (Market),Book Value Currency (Market),Market Value,Market Value Currency,Market Unrealized Returns,Market Unrealized Returns Currency
"FHSA","FHSA","Trade","HQ76YB467CAD","AMD","NASDAQ","XNAS","Advanced Micro Devices Inc.","EQUITY","1","LONG","621.44","USD","757.1104357","CAD","538.03","USD","621.73","USD","83.7","USD"
"FHSA","FHSA","Trade","HQ76YB467CAD","MRNA","NASDAQ","XNAS","Moderna Inc","EQUITY","1","LONG","181.945","USD","244.0700125","CAD","173.87","USD","182.44","USD","8.57","USD"
"FHSA","FHSA","Trade","HQ76YB467CAD","NBIS","NASDAQ","XNAS","Nebius Group NV","EQUITY","1","LONG","237.175","USD","367.775519833333333333333333","CAD","264.656666666666666666666667","USD","237.215","USD","-27.441666666666666666666667","USD"
"FHSA","FHSA","Trade","HQ76YB467CAD","USD","","","USD","CURRENCY","1177.46","LONG","1","USD","1671.77710953398945","CAD","1177.46","USD","1177.46","USD","0","USD"
"Options shianigans 🤑","Non-registered","Trade","HQ7VYSN07CAD","CAD","","","CAD","CURRENCY","23.97","LONG","1","CAD","23.97","CAD","23.97","CAD","23.97","CAD","0","CAD"
"Options shianigans 🤑","Non-registered","Trade","HQ7VYSN07CAD","USD","","","USD","CURRENCY","1033.83","LONG","1","USD","1487.46281586","CAD","1033.83","USD","1033.83","USD","0","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","AAOI","NASDAQ","XNAS","Applied Optoelectronics Inc","EQUITY","3.5495","LONG","106.67","USD","679.3374475","CAD","485.97","USD","379.051105","USD","-106.918895","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","AAPL","NASDAQ","XNAS","Apple Inc","EQUITY","5.0024","LONG","340.4","USD","2219.546157421457094384821248","CAD","1591.699039610651339328924952","USD","1703.617344","USD","111.918304389348660671075048","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","APTX","TSX","XTSE","Apotex Health Corp.","EQUITY","1","LONG","33.005","CAD","24","CAD","24","CAD","33.005","CAD","9.005","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","AXTI","NASDAQ","XNAS","AXT Inc","EQUITY","15.2974","LONG","76.65","USD","1456.839419817661468974955601","CAD","1052.135932612576208908741444","USD","1173.9071786","USD","121.771245987423791091258556","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","CAD","","","CAD","CURRENCY","136.44","LONG","1","CAD","136.44","CAD","136.44","CAD","136.44","CAD","0","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","DELL","NYSE","XNYS","Dell Technologies Inc (Class C)","EQUITY","0.3455","LONG","547.995","USD","244.8645743","CAD","177.37","USD","189.4031","USD","12.0331","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","DLLL","NASDAQ","XNAS","GraniteShares ETF Trust - 2X Long Dell Daily ETF","EXCHANGE_TRADED_FUND","44.8973","LONG","34.01","USD","2477.112616242975166875133029","CAD","1770.913639025778617347177129","USD","1526.99758057","USD","-243.916058455778617347177129","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","LUNR","NASDAQ","XNAS","Intuitive Machines Inc (Class A)","EQUITY","1","LONG","16.17","USD","48.614158357142857142857143","CAD","35.004285714285714285714286","USD","16.175","USD","-18.829285714285714285714286","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","MDA.TO","TSX","XTSE","MDA Space Ltd.","EQUITY","10.5782","LONG","43.93","CAD","446.83696095868443304079074","CAD","446.83696095868443304079074","CAD","464.488762","CAD","17.65180104131556695920926","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","MDB","NASDAQ","XNAS","MongoDB Inc (Class A)","EQUITY","1.0004","LONG","430.97","USD","621.3131474","CAD","446.93","USD","431.082364","USD","-15.847636","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","MU","NASDAQ","XNAS","Micron Technology Inc.","EQUITY","0.4","LONG","1093.13","USD","539.687756770758184816984466","CAD","389.990268214073195842296838","USD","437.6","USD","47.609731785926804157703162","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","NVDA","TSX","XTSE","Nvidia CDR (CAD Hedged)","EQUITY","9.3034","LONG","51.17","CAD","379.80454097476743313062648","CAD","379.80454097476743313062648","CAD","476.054978","CAD","96.25043702523256686937352","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","RY.TO","TSX","XTSE","Royal Bank of Canada","EQUITY","12.104","LONG","287.18","CAD","344.89","CAD","344.89","CAD","347.469528","CAD","2.579528","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SIDU","NASDAQ","XNAS","Sidus Space Inc (Class A)","EQUITY","2","LONG","2.13","USD","10.532109135109717868338558","CAD","7.619968652037617554858934","USD","4.2798","USD","-3.340168652037617554858934","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SKHY","NASDAQ","XNAS","SK Hynix Inc.","EQUITY","2","LONG","194.66","USD","443.015757","CAD","319.74","USD","389.46","USD","69.72","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SNDK","NASDAQ","XNAS","Sandisk Corporation","EQUITY","0.4776","LONG","1895.94","USD","1050.424883031468490102841199","CAD","746.947848083288086669047456","USD","906.995832","USD","160.047983916711913330952544","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SNXX","BATS","BATS","Investment Managers Series Trust II - Tradr 2X Long Sndk Daily ETF","EXCHANGE_TRADED_FUND","33.1776","LONG","20.01","USD","808.678188658837620424691715","CAD","576.377185812814522839890047","USD","665.60569344","USD","89.228507627185477160109953","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SOXL","NYSE","XNYS","Direxion Daily Semiconductor Bull 3X Shares","EXCHANGE_TRADED_FUND","1","LONG","150.72","USD","201.891978215384615384615385","CAD","143.834615384615384615384615","USD","150.7911","USD","6.956484615384615384615385","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","SPCX","NASDAQ","XNAS","Space Exploration Technologies Corp.","EQUITY","4","LONG","153.59","USD","878.8269888","CAD","632.64","USD","614.6","USD","-18.04","USD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","UCU","TSX-V","XTSX","Ucore Rare Metals Inc.","EQUITY","0.3467","LONG","2.61","CAD","1.259917904275603682469063","CAD","1.259917904275603682469063","CAD","0.904887","CAD","-0.355030904275603682469063","CAD"
"TFSA","TFSA","Trade","HQ7SQGHK2CAD","USD","","","USD","CURRENCY","4755.01","LONG","1","USD","6804.48317227108218","CAD","4755.01","USD","4755.01","USD","0","USD"`;

let currentWsParsedData = null;

function setupWealthsimpleModal() {
    const wsModal = document.getElementById("ws-modal");
    const openWsBtn = document.getElementById("open-ws-modal-btn");
    const closeWsBtn = document.getElementById("close-ws-modal-btn");
    const parseCsvBtn = document.getElementById("parse-csv-btn");
    const textarea = document.getElementById("ws-csv-textarea");
    const dropZone = document.getElementById("ws-drop-zone");
    const fileInput = document.getElementById("ws-file-input");
    const quickLoadBtn = document.getElementById("load-preloaded-ws-btn");
    const accountSelect = document.getElementById("ws-account-select");
    const includeCashCheck = document.getElementById("ws-include-cash-checkbox");
    const applyHoldingsBtn = document.getElementById("apply-ws-holdings-btn");

    if (!wsModal || !openWsBtn) return;

    // Open / Close Modal
    openWsBtn.addEventListener("click", () => {
        wsModal.classList.remove("hidden");
    });

    closeWsBtn.addEventListener("click", () => {
        wsModal.classList.add("hidden");
    });

    wsModal.addEventListener("click", (e) => {
        if (e.target === wsModal) wsModal.classList.add("hidden");
    });

    // Tab Navigation inside modal
    document.querySelectorAll(".modal-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".modal-tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".modal-tab-pane").forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetPane = document.getElementById(btn.dataset.modaltab);
            if (targetPane) targetPane.classList.add("active");
        });
    });

    // Parse pasted CSV
    if (parseCsvBtn) {
        parseCsvBtn.addEventListener("click", async () => {
            const rawText = textarea.value.trim();
            if (!rawText) {
                showToast("Please paste CSV text before parsing.", true);
                return;
            }
            await handleProcessCsv(rawText);
        });
    }

    // Drag & Drop
    if (dropZone && fileInput) {
        dropZone.addEventListener("click", () => fileInput.click());
        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("dragover");
        });
        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                readAndProcessFile(file);
            }
        });
        fileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                readAndProcessFile(e.target.files[0]);
            }
        });
    }

    // Quick-Load Preloaded Button
    if (quickLoadBtn) {
        quickLoadBtn.addEventListener("click", async () => {
            await handleProcessCsv(PRELOADED_WEALTHSIMPLE_CSV);
        });
    }

    // Account Dropdown Change
    if (accountSelect) {
        accountSelect.addEventListener("change", async () => {
            const selectedAccount = accountSelect.value;
            const rawCsv = textarea.value.trim() || PRELOADED_WEALTHSIMPLE_CSV;
            await handleProcessCsv(rawCsv, selectedAccount);
        });
    }

    // Include Cash checkbox toggle
    if (includeCashCheck) {
        includeCashCheck.addEventListener("change", () => {
            updateCashDisplay();
        });
    }

    // Apply Holdings to Main Portfolio & Run Simulation
    if (applyHoldingsBtn) {
        applyHoldingsBtn.addEventListener("click", handleApplyWsHoldings);
    }
}

function readAndProcessFile(file) {
    const reader = new FileReader();
    reader.onload = async (e) => {
        const text = e.target.result;
        document.getElementById("ws-csv-textarea").value = text;
        await handleProcessCsv(text);
    };
    reader.readAsText(file);
}

async function handleProcessCsv(csvText, selectedAccount = "All Accounts") {
    try {
        const response = await fetch("/api/wealthsimple/parse", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                csv_text: csvText,
                selected_account: selectedAccount === "All Accounts" ? null : selectedAccount
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to parse CSV");
        }

        const res = await response.json();
        currentWsParsedData = res.data;
        renderWsPreview(currentWsParsedData);
    } catch (err) {
        showToast(`Error parsing Wealthsimple CSV: ${err.message}`, true);
    }
}

function renderWsPreview(data) {
    const previewSection = document.getElementById("ws-preview-container");
    const tbody = document.getElementById("ws-preview-tbody");
    const accountSelect = document.getElementById("ws-account-select");
    const totalInvestedEl = document.getElementById("ws-total-invested");
    const totalCashEl = document.getElementById("ws-total-cash");
    const totalWithCashEl = document.getElementById("ws-total-with-cash");

    if (!previewSection || !tbody) return;

    previewSection.classList.remove("hidden");

    // Populate Account Dropdown
    if (accountSelect && accountSelect.options.length <= 1) {
        accountSelect.innerHTML = '<option value="All Accounts">All Accounts (Consolidated)</option>';
        data.accounts.forEach(acc => {
            const opt = document.createElement("option");
            opt.value = acc;
            opt.textContent = acc;
            if (acc === data.selected_account) opt.selected = true;
            accountSelect.appendChild(opt);
        });
    }

    // Populate Totals
    totalInvestedEl.textContent = `Invested: $${data.total_invested_cad.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD`;
    totalCashEl.textContent = `Cash Reserves: $${data.cash_reserves_cad.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD`;
    totalWithCashEl.textContent = `$${data.total_portfolio_cad.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD`;

    // Populate Table Rows
    tbody.innerHTML = "";
    data.holdings.forEach((h, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>
                <input type="checkbox" class="ws-row-check" data-index="${idx}" checked>
            </td>
            <td class="ticker-font">${h.ticker}</td>
            <td>${h.name || h.raw_symbol}</td>
            <td style="font-size: 11px; color: var(--text-muted);">${h.accounts.join(", ")}</td>
            <td style="font-family: var(--font-mono);">$${h.market_value_cad.toLocaleString('en-CA', { minimumFractionDigits: 2 })}</td>
            <td style="font-family: var(--font-mono); font-weight: 600; color: #a5b4fc;">${h.weight_pct}%</td>
        `;
        tbody.appendChild(tr);
    });

    // Checkbox listener to dynamically re-weight
    document.querySelectorAll(".ws-row-check").forEach(cb => {
        cb.addEventListener("change", recalculateCheckedWsWeights);
    });
}

function recalculateCheckedWsWeights() {
    if (!currentWsParsedData) return;

    const checkboxes = document.querySelectorAll(".ws-row-check");
    let totalCheckedCad = 0;

    checkboxes.forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.dataset.index, 10);
            totalCheckedCad += currentWsParsedData.holdings[idx].market_value_cad;
        }
    });

    checkboxes.forEach(cb => {
        const idx = parseInt(cb.dataset.index, 10);
        const row = cb.closest("tr");
        const weightCell = row.querySelectorAll("td")[5];
        if (cb.checked && totalCheckedCad > 0) {
            const w = (currentWsParsedData.holdings[idx].market_value_cad / totalCheckedCad) * 100;
            weightCell.textContent = `${w.toFixed(2)}%`;
        } else {
            weightCell.textContent = "0.00%";
        }
    });
}

function updateCashDisplay() {
    if (!currentWsParsedData) return;
    const includeCash = document.getElementById("ws-include-cash-checkbox").checked;
    const val = includeCash ? currentWsParsedData.total_portfolio_cad : currentWsParsedData.total_invested_cad;
    document.getElementById("ws-total-invested").textContent = includeCash ? 
        `Capital: $${val.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD (inc. cash)` :
        `Invested: $${val.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD`;
}

function handleApplyWsHoldings() {
    if (!currentWsParsedData || !currentWsParsedData.holdings) {
        showToast("No parsed Wealthsimple holdings found to apply.", true);
        return;
    }

    const checkboxes = document.querySelectorAll(".ws-row-check");
    const selectedHoldings = [];
    let totalCad = 0;

    checkboxes.forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.dataset.index, 10);
            const h = currentWsParsedData.holdings[idx];
            selectedHoldings.push(h);
            totalCad += h.market_value_cad;
        }
    });

    if (selectedHoldings.length === 0) {
        showToast("Please select at least one holding to simulate.", true);
        return;
    }

    // Convert to application format with normalized integer/float weights summing to 100
    currentHoldings = selectedHoldings.map(h => {
        const weight = (h.market_value_cad / totalCad) * 100;
        return {
            ticker: h.ticker,
            weight: Math.round(weight * 100) / 100
        };
    });

    // Normalize precisely to 100%
    handleNormalizeWeights();

    // Set starting capital to actual portfolio value (either equity or total inc cash)
    const includeCash = document.getElementById("ws-include-cash-checkbox").checked;
    const startingCapital = includeCash ? currentWsParsedData.total_portfolio_cad : totalCad;
    const capitalInput = document.getElementById("initial-capital");
    if (capitalInput) {
        capitalInput.value = Math.max(500, Math.round(startingCapital));
    }

    // Adjust lookback period to 1y to accommodate newer listings (e.g. SKHY, APTX.TO)
    const lookbackSelect = document.getElementById("lookback-period");
    if (lookbackSelect) {
        lookbackSelect.value = "1y";
    }

    // Close Modal
    document.getElementById("ws-modal").classList.add("hidden");

    // Re-render holdings and run simulation
    renderHoldingsTable();
    showToast(`Successfully imported ${selectedHoldings.length} holdings ($${Math.round(startingCapital).toLocaleString()} CAD)!`);
    runSimulation();
}


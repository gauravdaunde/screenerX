from datetime import datetime

def get_portfolio_template(balance, total_invested, current_value, total_pnl, pnl_color, stocks_html, closed_trades_html="", realized_pnl=0.0, chart_data_json="{}", metrics={}, heatmap={}, strategy_capital={}, summary_json="{}"):
    """
    Returns the HTML content for the portfolio dashboard.
    """
    realized_pnl_color = "success" if realized_pnl >= 0 else "danger"
    
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Portfolio Manager</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
                .card {{ border: none; border-radius: 12px; }}
                .card-header {{ font-weight: 600; border-radius: 12px 12px 0 0 !important; }}
                .closed-trades-table th {{ background: #f8f9fa; position: sticky; top: 0; }}
                .profit {{ color: #198754; font-weight: 600; }}
                .loss {{ color: #dc3545; font-weight: 600; }}
            </style>
            <!-- Chart.js -->
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
            <meta http-equiv="refresh" content="60"> 
        </head>
        <body class="bg-light">
            <div class="container py-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 class="mb-0">🚀 Portfolio Dashboard</h2>
                    <span class="badge bg-white text-secondary shadow-sm p-2">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                </div>
                
                <!-- Navigation Tabs -->
                <ul class="nav nav-pills mb-4" id="portfolioTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active fw-bold" id="overview-tab" data-bs-toggle="pill" data-bs-target="#overview" type="button" role="tab">🚀 Overview & Live Positions</button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link fw-bold" id="analytics-tab" data-bs-toggle="pill" data-bs-target="#analytics" type="button" role="tab">📊 Strategy Analytics</button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link fw-bold" id="history-tab" data-bs-toggle="pill" data-bs-target="#history" type="button" role="tab">📜 Trade History</button>
                    </li>
                </ul>

                <div class="tab-content" id="portfolioTabsContent">
                    
                    <!-- TAB 1: OVERVIEW -->
                    <div class="tab-pane fade show active" id="overview" role="tabpanel">
                        <!-- Account Summary Cards -->
                        <div class="row g-3 mb-4">
                            <div class="col-md-3">
                                <div class="card bg-white shadow-sm h-100">
                                    <div class="card-body">
                                        <h6 class="text-muted text-uppercase small">Cash Balance</h6>
                                        <h3 class="text-primary mt-2" id="summary-balance">₹{balance:,.2f}</h3>
                                    </div>
                                </div>
                            </div>
                             <div class="col-md-3">
                                <div class="card bg-white shadow-sm h-100">
                                    <div class="card-body">
                                        <h6 class="text-muted text-uppercase small">Invested Amount</h6>
                                        <h3 class="text-dark mt-2" id="summary-invested">₹{total_invested:,.2f}</h3>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card bg-white shadow-sm h-100">
                                    <div class="card-body">
                                        <h6 class="text-muted text-uppercase small">Unrealized PnL</h6>
                                        <h3 class="text-{pnl_color} mt-2" id="summary-pnl">{total_pnl:+,.2f}</h3>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card bg-white shadow-sm h-100">
                                    <div class="card-body">
                                        <h6 class="text-muted text-uppercase small">Total Portfolio Value</h6>
                                        <h3 class="text-dark mt-2" id="summary-value">₹{(balance + current_value):,.2f}</h3>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- LIVE HOLDINGS -->
                        <div id="overviewFilters" class="mb-3 d-flex flex-wrap gap-2 justify-content-start">
                            <!-- JS will populate strategy filters here -->
                        </div>

                        <div class="card shadow-sm h-100 mb-4">
                            <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between">
                                <span class="text-success fw-bold">🟢 Active Positions</span>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    {stocks_html}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 2: ANALYTICS -->
                    <div class="tab-pane fade" id="analytics" role="tabpanel">
                        <!-- Strategy Equity Curve -->
                        <div class="card shadow-sm mb-4">
                            <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                                <span class="fw-bold"><span class="text-primary">📈</span> Strategy Equity Curve (Base 100k)</span>
                                <div class="text-muted small">Click filters to compare vs Benchmark</div>
                            </div>
                            <div class="card-body">
                                <div id="strategyFilters" class="mb-3 d-flex flex-wrap gap-2 justify-content-center"></div>
                                <canvas id="strategyChart" height="80"></canvas>
                            </div>
                        </div>

                        <!-- Strategy Capital Allocation -->
                        <div class="card shadow-sm mb-4">
                            <div class="card-header bg-white py-3 border-bottom">
                                <span class="fw-bold text-primary">💼 Strategy Book (Virtual Wallets)</span>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table table-hover align-middle mb-0">
                                        <thead class="bg-light">
                                            <tr>
                                                <th>Strategy</th>
                                                <th class="text-end">Base</th>
                                                <th class="text-end">Realized PnL</th>
                                                <th class="text-end">Current Bal</th>
                                                <th class="text-end">Invested</th>
                                                <th class="text-end">Available</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            """ + "".join([f"""
                                            <tr>
                                                <td class="fw-bold">
                                                    {s} 
                                                    {f'<span class="badge bg-warning text-dark ms-2">{d["open_positions"]} OPEN</span>' if d['open_positions'] > 0 else ''}
                                                </td>
                                                <td class="text-end text-muted">₹{d['base']:,.0f}</td>
                                                <td class="text-end {'text-success' if d['realized_pnl'] >= 0 else 'text-danger'}">
                                                    {'+' if d['realized_pnl'] >= 0 else ''}₹{d['realized_pnl']:,.2f}
                                                </td>
                                                <td class="text-end fw-bold">₹{d['current_balance']:,.2f}</td>
                                                <td class="text-end text-secondary">₹{d['invested']:,.2f}</td>
                                                <td class="text-end fw-bold {'text-success' if d['available_cash'] > 0 else 'text-danger'}">
                                                    ₹{d['available_cash']:,.2f}
                                                </td>
                                            </tr>
                                            """ for s, d in strategy_capital.items()]) + f"""
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <!-- Metrics & Heatmap split -->
                        <div class="row g-4">
                            <div class="col-lg-6">
                                <div class="card shadow-sm h-100">
                                    <div class="card-header bg-white py-3 border-bottom">
                                        <span class="text-info fw-bold">📊 Performance Metrics</span>
                                    </div>
                                    <div class="card-body p-0">
                                        <div class="table-responsive">
                                            <table class="table table-sm table-hover align-middle mb-0" style="font-size: 0.9rem;">
                                                <thead class="bg-light">
                                                    <tr>
                                                        <th>Strategy</th>
                                                        <th>Win%</th>
                                                        <th>PF</th>
                                                        <th>DD</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    """ + "".join([f"""
                                                    <tr>
                                                        <td class="fw-bold">{s}</td>
                                                        <td><span class="badge bg-{'success' if m['win_rate'] >= 50 else 'warning'}">{m['win_rate']}%</span></td>
                                                        <td>{m['profit_factor']}</td>
                                                        <td class="text-danger">{m['max_drawdown']}%</td>
                                                    </tr>
                                                    """ for s, m in metrics.items()]) + f"""
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-6">
                                <div class="card shadow-sm h-100">
                                    <div class="card-header bg-white py-3 border-bottom">
                                        <span class="text-secondary fw-bold">🗓️ Monthly Heatmap</span>
                                    </div>
                                    <div class="card-body p-0">
                                        <div class="table-responsive">
                                            <table class="table table-bordered text-center mb-0 table-sm" style="font-size: 0.8rem;">
                                                <thead class="bg-light">
                                                    <tr>
                                                        <th>Year</th><th>Jan</th><th>Feb</th><th>Mar</th><th>...</th><th>Total</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    """ + "".join([f"""
                                                    <tr>
                                                        <td class="fw-bold">{year}</td>
                                                        {f'<td class="text-success">₹'+str(sum(heatmap[year].values())/1000)+'k</td>' if sum(heatmap[year].values()) > 0 else f'<td class="text-danger">₹'+str(sum(heatmap[year].values())/1000)+'k</td>'}
                                                    </tr>
                                                    """ for year in sorted(heatmap.keys(), reverse=True)]) + f"""
                                                </tbody>
                                            </table>
                                            <div class="p-2 text-center text-muted small">Full heatmap available in detailed report</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 3: HISTORY -->
                    <div class="tab-pane fade" id="history" role="tabpanel">
                        <div class="card shadow-sm">
                            <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                                <span class="fw-bold">📜 Closed Trade History</span>
                                <span class="badge bg-{'success' if realized_pnl >= 0 else 'danger'} text-white">Total Realized: ₹{realized_pnl:+,.2f}</span>
                            </div>
                            <div class="card-body p-0">
                                <div id="historyFilters" class="p-3 border-bottom d-flex flex-wrap gap-2 justify-content-start bg-light">
                                    <span class="fw-bold my-auto me-2">Filter by Strategy:</span>
                                    <!-- JS will populate history filters here -->
                                </div>
                                <div class="table-responsive closed-trades-table" style="max-height: 600px; overflow-y: auto;">
                                    {closed_trades_html}
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
                
                <footer class="mt-5 text-center text-muted small">
                     Live Data provided by Yahoo Finance. <br>
                     Protected Dashboard • Auto-refreshes every 60s.
                </footer>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

            <script>
                // Chart Data
                const rawData = {chart_data_json};
                const summaryData = {summary_json};
                
                if (Object.keys(rawData).length > 0) {{
                    const ctx = document.getElementById('strategyChart').getContext('2d');
                    
                    const datasets = [];
                    const colors = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796', '#6f42c1', '#fd7e14'];
                    let colorIdx = 0;
                    
                    for (const [strategy, points] of Object.entries(rawData)) {{
                        datasets.push({{
                            label: strategy,
                            data: points,
                            borderColor: colors[colorIdx % colors.length],
                            backgroundColor: colors[colorIdx % colors.length] + '20', // transparent fill
                            borderWidth: 2,
                            tension: 0.1,
                            fill: false,
                            pointRadius: 3
                        }});
                        colorIdx++;
                    }}
                    
                    const chart = new Chart(ctx, {{
                        type: 'line',
                        data: {{ datasets: datasets }},
                        options: {{
                            responsive: true,
                            interaction: {{
                                mode: 'index',
                                intersect: false,
                            }},
                            plugins: {{
                                legend: {{
                                    display: false // Hide default legend, using custom filters
                                }},
                                tooltip: {{
                                    callbacks: {{
                                        label: function(context) {{
                                            let label = context.dataset.label || '';
                                            if (label) {{
                                                label += ': ';
                                            }}
                                            if (context.parsed.y !== null) {{
                                                label += new Intl.NumberFormat('en-IN', {{ style: 'currency', currency: 'INR', maximumFractionDigits: 0 }}).format(context.parsed.y);
                                            }}
                                            return label;
                                        }}
                                    }}
                                }}
                            }},
                            scales: {{
                                x: {{
                                    type: 'time',
                                    time: {{
                                        unit: 'day',
                                        displayFormats: {{
                                            day: 'MMM dd'
                                        }}
                                    }},
                                    title: {{
                                        display: true,
                                        text: 'Date'
                                    }}
                                }},
                                y: {{
                                    title: {{
                                        display: true,
                                        text: 'Equity Value (₹)'
                                    }},
                                     grid: {{
                                        color: function(context) {{
                                            if (context.tick.value === 100000) {{
                                                return '#666'; // Highlight base line
                                            }}
                                            return '#e0e0e0';
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});

                    // Generate Custom Filters
                    const filterContainer = document.getElementById('strategyFilters');
                    datasets.forEach((ds, index) => {{
                        const btn = document.createElement('button');
                        btn.className = 'btn btn-sm border shadow-sm d-flex align-items-center gap-2';
                        btn.style.borderColor = ds.borderColor;
                        btn.style.color = '#333';
                        btn.style.backgroundColor = '#fff'; // Active state style by default
                        
                        // Add Color Dot
                        const dot = document.createElement('span');
                        dot.style.width = '10px';
                        dot.style.height = '10px';
                        dot.style.borderRadius = '50%';
                        dot.style.backgroundColor = ds.borderColor;
                        dot.style.display = 'inline-block';
                        
                        btn.appendChild(dot);
                        btn.appendChild(document.createTextNode(ds.label));
                        
                        // Toggle Logic
                        btn.onclick = () => {{
                            const meta = chart.getDatasetMeta(index);
                            meta.hidden = meta.hidden === null ? !chart.data.datasets[index].hidden : null;
                            
                            // Visual toggle
                            if (meta.hidden) {{
                                btn.style.opacity = '0.4';
                                btn.classList.remove('shadow-sm');
                            }} else {{
                                btn.style.opacity = '1';
                                btn.classList.add('shadow-sm');
                            }}
                            
                            chart.update();
                        }};
                        
                        filterContainer.appendChild(btn);
                    }});
                    
                }} else {{
                    document.getElementById('strategyChart').parentElement.innerHTML = '<div class="alert alert-secondary m-3">Not enough data to generate graph.</div>';
                }}

                // -- Table Filtering Logic --
                function setupTableFilters(filterContainerId, tableContainerSelector, strategyColIndex, isOverview = false) {{
                    const container = document.getElementById(filterContainerId);
                    if (!container) return;

                    const tables = document.querySelectorAll(tableContainerSelector + ' table tbody');
                    
                    // Allow filtering even if no tables (for zero positions), but we need strategies from SummaryData if Overview
                    let strategies = new Set();
                    const rows = [];
                    
                    if (tables.length > 0) {{
                        tables.forEach(tbody => {{
                            Array.from(tbody.querySelectorAll('tr')).forEach(row => {{
                                const cells = row.cells;
                                if (cells.length > strategyColIndex) {{
                                    const uniqueStrat = cells[strategyColIndex].textContent.trim();
                                    if (uniqueStrat) {{
                                        strategies.add(uniqueStrat);
                                        row.dataset.strategy = uniqueStrat;
                                        rows.push(row);
                                    }}
                                }}
                            }});
                        }});
                    }}
                    
                    // If Overview, merge with summaryData keys to ensure we show controls for strategies that might just have Cash but no Open Positions
                    if (isOverview && typeof summaryData !== 'undefined') {{
                         Object.keys(summaryData).forEach(s => strategies.add(s));
                    }}

                    if (strategies.size === 0) {{
                        container.innerHTML = '<span class="text-muted small">No strategies found.</span>';
                        return;
                    }}

                    // "Select All" Checkbox
                    const allWrapper = document.createElement('div');
                    allWrapper.className = 'form-check';
                    const allInput = document.createElement('input');
                    allInput.type = 'checkbox';
                    allInput.className = 'form-check-input';
                    allInput.id = filterContainerId + '-all';
                    allInput.checked = true;
                    
                    const allLabel = document.createElement('label');
                    allLabel.className = 'form-check-label fw-bold small text-uppercase text-muted my-auto';
                    allLabel.htmlFor = allInput.id;
                    allLabel.textContent = 'All';
                    
                    allWrapper.appendChild(allInput);
                    allWrapper.appendChild(allLabel);
                    container.appendChild(allWrapper);

                    const checkboxes = [];

                    strategies.forEach(strat => {{
                        const wrapper = document.createElement('div');
                        wrapper.className = 'form-check';
                        const input = document.createElement('input');
                        input.type = 'checkbox';
                        input.className = 'form-check-input strategy-check';
                        input.value = strat;
                        input.id = filterContainerId + '-' + strat.replace(/\s+/g, ''); 
                        input.checked = true;
                        
                        const label = document.createElement('label');
                        label.className = 'form-check-label';
                        label.htmlFor = input.id;
                        label.textContent = strat;
                        
                        wrapper.appendChild(input);
                        wrapper.appendChild(label);
                        container.appendChild(wrapper);
                        checkboxes.push(input);
                        
                        input.addEventListener('change', () => {{
                             updateVisibility();
                             allInput.checked = checkboxes.every(c => c.checked);
                             allInput.indeterminate = checkboxes.some(c => c.checked) && !allInput.checked;
                        }});
                    }});
                    
                    allInput.addEventListener('change', () => {{
                        checkboxes.forEach(c => c.checked = allInput.checked);
                        updateVisibility();
                    }});
                    
                    function updateVisibility() {{
                        const activeStrats = new Set(checkboxes.filter(c => c.checked).map(c => c.value));
                        rows.forEach(row => {{
                            if (activeStrats.has(row.dataset.strategy)) {{
                                row.style.display = '';
                            }} else {{
                                row.style.display = 'none';
                            }}
                        }});
                        
                        // Update Summary Cards if Overview
                        if (isOverview && typeof summaryData !== 'undefined') {{
                            let totalCash = 0;
                            let totalInvested = 0;
                            let totalPnL = 0;
                            let totalValue = 0;
                            
                            activeStrats.forEach(strat => {{
                                if (summaryData[strat]) {{
                                    totalCash += summaryData[strat].cash;
                                    totalInvested += summaryData[strat].invested;
                                    totalPnL += summaryData[strat].pnl;
                                }}
                            }});
                            
                            totalValue = totalCash + (totalInvested + totalPnL); // CurrentValue = Invested + PnL
                            
                            // Update DOM
                            document.getElementById('summary-balance').textContent = '₹' + totalCash.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
                            document.getElementById('summary-invested').textContent = '₹' + totalInvested.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
                            
                            const pnlEl = document.getElementById('summary-pnl');
                            pnlEl.textContent = (totalPnL >= 0 ? '+' : '') + totalPnL.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
                            pnlEl.className = 'mt-2 text-' + (totalPnL >= 0 ? 'success' : 'danger');
                            
                            document.getElementById('summary-value').textContent = '₹' + totalValue.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
                        }}
                    }}
                }}

                // Initialize Filters
                // Overview: Live positions (Stocks/Options), Strategy is Col 0. Pass isOverview=true
                setupTableFilters('overviewFilters', '#overview', 0, true);
                
                // History: Closed trades, Strategy is Col 1 (after Symbol)
                setupTableFilters('historyFilters', '#history', 1);
            </script>
        </body>
    </html>
    """

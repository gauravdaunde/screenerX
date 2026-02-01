from datetime import datetime

def get_portfolio_template(balance, total_invested, current_value, total_pnl, pnl_color, stocks_html, options_html):
    """
    Returns the HTML content for the portfolio dashboard.
    """
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
            </style>
            <meta http-equiv="refresh" content="60"> 
        </head>
        <body class="bg-light">
            <div class="container py-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 class="mb-0">🚀 Portfolio Dashboard</h2>
                    <span class="badge bg-white text-secondary shadow-sm p-2">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                </div>
                
                <!-- Account Summary -->
                <div class="row g-3 mb-4">
                    <div class="col-md-3">
                        <div class="card bg-white shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="text-muted text-uppercase small">Cash Balance</h6>
                                <h3 class="text-primary mt-2">₹{balance:,.2f}</h3>
                            </div>
                        </div>
                    </div>
                     <div class="col-md-3">
                        <div class="card bg-white shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="text-muted text-uppercase small">Invested Amount</h6>
                                <h3 class="text-dark mt-2">₹{total_invested:,.2f}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-white shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="text-muted text-uppercase small">Unrealized PnL</h6>
                                <h3 class="text-{pnl_color} mt-2">{total_pnl:+,.2f}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-white shadow-sm h-100">
                            <div class="card-body">
                                <h6 class="text-muted text-uppercase small">Total Value</h6>
                                <h3 class="text-dark mt-2">₹{(balance + current_value):,.2f}</h3>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Holdings -->
                <div class="row g-4">
                    <div class="col-md-6">
                        <div class="card shadow-sm h-100">
                            <div class="card-header bg-white py-3 border-bottom">
                                <span class="text-success">🟢</span> Stocks Holdings
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    {stocks_html}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card shadow-sm h-100">
                            <div class="card-header bg-white py-3 border-bottom">
                                <span class="text-warning">⚡</span> Options Holdings
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    {options_html}
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
        </body>
    </html>
    """

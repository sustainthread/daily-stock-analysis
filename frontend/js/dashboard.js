// Sample data - In production, this would come from an API
const SAMPLE_DATA = {
    last_updated: new Date().toISOString(),
    stocks: [
        {
            ticker: "AAPL",
            name: "Apple Inc.",
            region: "US",
            current_price: 185.43,
            price_change: 2.34,
            price_change_percent: 1.28,
            confidence_score: 82,
            catalyst: "Strong Q4 earnings beat, new product launch imminent",
            analysis: "Breaking above 50-day MA on high volume. RSI showing strong momentum.",
            volume: 45678900,
            avg_volume: 34567000
        },
        {
            ticker: "MSFT",
            name: "Microsoft Corporation",
            region: "US", 
            current_price: 378.85,
            price_change: 5.21,
            price_change_percent: 1.39,
            confidence_score: 76,
            catalyst: "Azure cloud growth exceeding expectations",
            analysis: "Consolidating near all-time highs. Institutional accumulation detected.",
            volume: 23456700,
            avg_volume: 28901000
        },
        {
            ticker: "TSCO.L",
            name: "Tesco PLC",
            region: "UK",
            current_price: 295.60,
            price_change: 4.20,
            price_change_percent: 1.44,
            confidence_score: 68,
            catalyst: "Market share growth in grocery sector",
            analysis: "Bouncing from support level. Dividend yield attractive at current price.",
            volume: 15678900,
            avg_volume: 12345000
        },
        {
            ticker: "AIR.PA",
            name: "Airbus SE",
            region: "EU",
            current_price: 148.25,
            price_change: 1.85,
            price_change_percent: 1.26,
            confidence_score: 71,
            catalyst: "Record aircraft orders, strong travel demand",
            analysis: "Breaking out of 6-month consolidation pattern.",
            volume: 9876500,
            avg_volume: 8765400
        }
    ]
};

class StockDashboard {
    constructor() {
        this.stocks = [];
        this.filteredStocks = [];
        this.currentRegion = 'all';
        this.searchTerm = '';
        
        this.init();
    }

    async init() {
        await this.loadData();
        this.render();
        this.setupEventListeners();
    }

    async loadData() {
        try {
            // Try to load live data first
            const response = await fetch('/api/stocks');
            if (response.ok) {
                this.stocks = await response.json();
            } else {
                throw new Error('API not available');
            }
        } catch (error) {
            // Fall back to sample data
            console.log('Using sample data:', error);
            this.stocks = SAMPLE_DATA.stocks;
            document.getElementById('error-message').style.display = 'block';
        }
        
        this.filteredStocks = [...this.stocks];
        this.updateLastUpdated();
    }

    updateLastUpdated() {
        const now = new Date();
        document.getElementById('update-time').textContent = 
            now.toLocaleString('en-US', { 
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
    }

    setupEventListeners() {
        // Region filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentRegion = e.target.dataset.region;
                this.applyFilters();
            });
        });

        // Search input
        document.getElementById('stock-search').addEventListener('input', (e) => {
            this.searchTerm = e.target.value.toLowerCase();
            this.applyFilters();
        });
    }

    applyFilters() {
        this.filteredStocks = this.stocks.filter(stock => {
            const regionMatch = this.currentRegion === 'all' || stock.region === this.currentRegion;
            const searchMatch = !this.searchTerm || 
                stock.ticker.toLowerCase().includes(this.searchTerm) ||
                stock.name.toLowerCase().includes(this.searchTerm);
            return regionMatch && searchMatch;
        });
        this.render();
    }

    render() {
        this.renderStats();
        this.renderStockGrid();
        this.hideLoading();
    }

    renderStats() {
        const totalStocks = this.filteredStocks.length;
        const highConfidence = this.filteredStocks.filter(s => s.confidence_score >= 70).length;
        const avgScore = totalStocks > 0 
            ? Math.round(this.filteredStocks.reduce((sum, s) => sum + s.confidence_score, 0) / totalStocks)
            : 0;

        document.getElementById('total-stocks').textContent = totalStocks;
        document.getElementById('high-confidence').textContent = highConfidence;
        document.getElementById('avg-score').textContent = avgScore;
    }

    renderStockGrid() {
        const grid = document.getElementById('stock-grid');
        
        if (this.filteredStocks.length === 0) {
            grid.innerHTML = '<div class="no-results">No stocks match your filters</div>';
            grid.style.display = 'block';
            return;
        }

        grid.innerHTML = this.filteredStocks.map(stock => `
            <div class="stock-card" data-region="${stock.region}">
                <div class="stock-header">
                    <div class="stock-ticker">${stock.ticker}</div>
                    <div class="stock-region">${stock.region}</div>
                </div>
                <div class="stock-name">${stock.name}</div>
                
                <div class="stock-price">$${stock.current_price.toFixed(2)}</div>
                <div class="price-change ${stock.price_change >= 0 ? 'positive' : 'negative'}">
                    ${stock.price_change >= 0 ? '+' : ''}${stock.price_change.toFixed(2)} 
                    (${stock.price_change_percent.toFixed(2)}%)
                </div>

                <div class="confidence-score">
                    <div class="score-bar">
                        <div class="score-fill ${this.getScoreClass(stock.confidence_score)}" 
                             style="width: ${stock.confidence_score}%"></div>
                    </div>
                    <div class="score-text">
                        Confidence Score: <strong>${stock.confidence_score}/100</strong>
                    </div>
                </div>

                <div class="catalyst">
                    <div class="catalyst-title">📊 Primary Catalyst</div>
                    <div>${stock.catalyst}</div>
                </div>

                <div class="analysis">
                    <strong>Analysis:</strong> ${stock.analysis}
                </div>
            </div>
        `).join('');

        grid.style.display = 'grid';
    }

    getScoreClass(score) {
        if (score >= 70) return 'score-high';
        if (score >= 50) return 'score-medium';
        return 'score-low';
    }

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new StockDashboard();
});
